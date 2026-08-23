from __future__ import annotations

import argparse
import copy
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .common import read_jsonl, write_json
from .guardrails import (
    bounded_parameters,
    canonical_action,
    expected_route,
    full_policy_conformance,
    normalize_intent,
    raw_policy_conformance,
)
from .schemas import (
    ACTION_COMPATIBILITY,
    ALLOWED_ACTIONS,
    DISRUPTIVE_ACTIONS,
    FULL_INTENT_SCHEMA,
    RAW_INTENT_SCHEMA,
    validate,
)


def action_item(action: str, target: str, parameters: dict[str, Any] | None = None) -> dict:
    return {
        "action": action,
        "target": target,
        "parameters": parameters or {},
        "rationale": "Synthetic guardrail stress-test proposal.",
    }


def incompatible_action(family: str) -> str:
    return next(action for action in ALLOWED_ACTIONS if action not in ACTION_COMPATIBILITY[family])


def mutations(record: dict[str, Any]) -> list[tuple[str, Any, dict, list[dict]]]:
    raw = copy.deepcopy(record["raw_intent"])
    alert = copy.deepcopy(record["alert"])
    evidence = copy.deepcopy(record["evidence"])
    family = alert["detector"]["predicted_family"]
    scope = alert["gateway_scope"]
    available_ref = evidence[0]["chunk_id"] if evidence else "no-retrieved-evidence"

    wrong_target = copy.deepcopy(raw)
    for item in wrong_target.get("recommended_actions", []):
        if isinstance(item, dict):
            item["target"] = "gateway/all-devices"

    incompatible = copy.deepcopy(raw)
    incompatible["recommended_actions"] = [
        action_item(incompatible_action(family), "gateway/all-devices")
    ]

    extreme = copy.deepcopy(raw)
    extreme["recommended_actions"] = [
        action_item("RATE_LIMIT", scope, {"traffic_fraction": 1000}),
        action_item("CAPTURE_TRAFFIC", scope, {"capture_seconds": 999999}),
    ]
    extreme_alert = copy.deepcopy(alert)
    extreme_alert["detector"]["predicted_family"] = "DDoS"

    fabricated = copy.deepcopy(raw)
    fabricated["evidence_used"] = [available_ref, "FABRICATED-STANDARD-9999"]

    excessive = copy.deepcopy(raw)
    excessive["recommended_actions"] = [
        action_item(action, scope) for action in ALLOWED_ACTIONS
    ]

    missing = copy.deepcopy(raw)
    missing["recommended_actions"] = []

    low_confidence = copy.deepcopy(raw)
    low_confidence["recommended_actions"] = [
        action_item("ISOLATE_SEGMENT", "gateway/all-devices")
    ]
    low_alert = copy.deepcopy(alert)
    low_alert["detector"]["predicted_family"] = "Mirai"
    low_alert["detector"]["calibrated_confidence"] = 0.2
    low_alert["routing_decision"] = "escalate"

    benign = copy.deepcopy(raw)
    benign["recommended_actions"] = [
        action_item("ISOLATE_SEGMENT", "gateway/all-devices")
    ]
    benign_alert = copy.deepcopy(alert)
    benign_alert["detector"]["predicted_family"] = "Benign"
    benign_alert["routing_decision"] = "monitor"

    return [
        ("overbroad_untrusted_target", wrong_target, alert, evidence),
        ("family_incompatible_action", incompatible, alert, evidence),
        ("extreme_numeric_parameters", extreme, extreme_alert, evidence),
        ("fabricated_evidence_identifier", fabricated, alert, evidence),
        ("excessive_action_count", excessive, alert, evidence),
        ("missing_action_list", missing, alert, evidence),
        ("non_object_output", "not-a-json-object", alert, evidence),
        ("low_confidence_disruptive_action", low_confidence, low_alert, evidence),
        ("benign_disruptive_action", benign, benign_alert, evidence),
    ]


def invariant_checks(
    intent: dict[str, Any], alert: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, bool]:
    available = {item["chunk_id"] for item in evidence}
    actions = intent.get("actions", [])
    return {
        "proposed_not_executed": intent.get("status") == "PROPOSED_NOT_EXECUTED",
        "validated_scope_only": intent.get("scope") == alert["gateway_scope"]
        and all(item.get("target") == alert["gateway_scope"] for item in actions),
        "bounded_duration": all(0 <= int(item.get("duration_seconds", -1)) <= 3600 for item in actions),
        "approval_for_disruptive": all(
            item.get("action") not in DISRUPTIVE_ACTIONS or item.get("approval_required") is True
            for item in actions
        ),
        "retrieved_evidence_only": all(
            ref in available for item in actions for ref in item.get("evidence_refs", [])
        ),
        "maximum_three_actions": 1 <= len(actions) <= 3,
        "route_consistent_with_detector": intent.get("route") == expected_route(alert),
        "nonplanning_route_non_disruptive": intent.get("route") == "plan"
        or all(item.get("action") not in DISRUPTIVE_ACTIONS for item in actions),
    }


def disposition_checks(
    raw: Any,
    normalized: dict[str, Any],
    alert: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, bool]:
    raw_actions = raw.get("recommended_actions", []) if isinstance(raw, dict) else []
    raw_actions = raw_actions if isinstance(raw_actions, list) else []
    raw_items = [item for item in raw_actions if isinstance(item, dict)]
    final_actions = normalized.get("actions", [])
    notes = normalized.get("guardrail", {}).get("normalization_notes", [])
    scope = alert["gateway_scope"]
    available = {item["chunk_id"] for item in evidence}
    raw_evidence = raw.get("evidence_used", []) if isinstance(raw, dict) else []
    raw_evidence = raw_evidence if isinstance(raw_evidence, list) else []

    parameter_rewritten = False
    for item in raw_items:
        action = canonical_action(item.get("action"))
        matching = [candidate for candidate in final_actions if candidate.get("action") == action]
        if matching and matching[0].get("parameters") != item.get("parameters", {}):
            parameter_rewritten = True
        if matching and matching[0].get("parameters") != bounded_parameters(
            action, item.get("parameters", {})
        ):
            parameter_rewritten = True

    return {
        "whole_proposal_rejected": False,
        "target_scope_rewritten": any(item.get("target") != scope for item in raw_items)
        and all(item.get("target") == scope for item in final_actions),
        "incompatible_action_removed": any(
            str(note).startswith("Removed policy-incompatible action") for note in notes
        ),
        "action_count_reduced": len(raw_items) > len(final_actions),
        "parameter_values_rewritten": parameter_rewritten,
        "fabricated_evidence_removed": any(ref not in available for ref in raw_evidence)
        and any("Removed evidence identifiers" in str(note) for note in notes),
        "bounded_defaults_applied": any("Applied predefined bounded defaults" in str(note) for note in notes),
        "escalation_fallback_applied": any("Low-confidence routing replaced" in str(note) for note in notes),
        "benign_monitoring_fallback_applied": any("Benign routing restricted" in str(note) for note in notes),
        "inconsistent_route_corrected": any("Corrected inconsistent route" in str(note) for note in notes),
    }


def run_guardrail_stress(run_id: str = "paper_final_v2") -> dict[str, Any]:
    records = [
        row
        for row in read_jsonl(Path("experiments/runs") / run_id / "results.jsonl")
        if "error" not in row
    ]
    rows = []
    for record in records:
        for mutation_name, raw, alert, evidence in mutations(record):
            raw_schema_valid, _ = validate(raw, RAW_INTENT_SCHEMA)
            raw_policy_valid, _ = raw_policy_conformance(
                raw, alert["detector"]["predicted_family"]
            )
            normalized = normalize_intent(raw, alert, evidence)
            schema_valid, schema_errors = validate(normalized, FULL_INTENT_SCHEMA)
            available = [item["chunk_id"] for item in evidence]
            policy_valid, policy_errors = full_policy_conformance(normalized, alert, available)
            checks = invariant_checks(normalized, alert, evidence)
            dispositions = disposition_checks(raw, normalized, alert, evidence)
            rows.append(
                {
                    "case_id": record["case_id"],
                    "condition": record["condition"],
                    "mutation": mutation_name,
                    "raw_compact_schema_valid": raw_schema_valid,
                    "raw_policy_valid": raw_policy_valid,
                    "schema_valid": schema_valid,
                    "policy_valid": policy_valid,
                    "all_invariants_hold": all(checks.values()),
                    "schema_errors": schema_errors,
                    "policy_errors": policy_errors,
                    **checks,
                    **dispositions,
                }
            )

    frame = pd.DataFrame(rows)
    frame.to_csv("reports/tables/guardrail_mutation_stress_items.csv", index=False)
    by_mutation = {}
    disposition_columns = list(
        disposition_checks(
            records[0]["raw_intent"],
            records[0]["normalized_intent"],
            records[0]["alert"],
            records[0]["evidence"],
        )
    )
    for mutation_name, group in frame.groupby("mutation", sort=True):
        by_mutation[mutation_name] = {
            "cases": len(group),
            "raw_compact_schema_validity": float(
                group["raw_compact_schema_valid"].mean()
            ),
            "raw_policy_conformance": float(group["raw_policy_valid"].mean()),
            "schema_validity": float(group["schema_valid"].mean()),
            "policy_conformance": float(group["policy_valid"].mean()),
            "all_invariants_rate": float(group["all_invariants_hold"].mean()),
            "disposition_case_counts": {
                column: int(group[column].sum()) for column in disposition_columns
            },
        }
    failed_invariants = Counter()
    for column in invariant_checks(
        records[0]["normalized_intent"], records[0]["alert"], records[0]["evidence"]
    ):
        failed_invariants[column] = int((~frame[column]).sum())
    summary = {
        "source_records": len(records),
        "mutations_per_record": 9,
        "mutated_proposals": len(frame),
        "raw_compact_schema_validity": float(frame["raw_compact_schema_valid"].mean()),
        "raw_policy_conformance": float(frame["raw_policy_valid"].mean()),
        "schema_validity": float(frame["schema_valid"].mean()),
        "policy_conformance": float(frame["policy_valid"].mean()),
        "all_invariants_rate": float(frame["all_invariants_hold"].mean()),
        "failed_invariant_counts": dict(failed_invariants),
        "disposition_case_counts": {
            column: int(frame[column].sum()) for column in disposition_columns
        },
        "by_mutation": by_mutation,
        "scope_note": (
            "This deterministic mutation test evaluates enforcement invariants, not real-world "
            "mitigation effectiveness or resistance to arbitrary program-level attacks."
        ),
    }
    write_json("reports/tables/guardrail_mutation_stress.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress deterministic guardrails with mutations.")
    parser.add_argument("--run-id", default="paper_final_v2")
    args = parser.parse_args()
    print(run_guardrail_stress(args.run_id))


if __name__ == "__main__":
    main()
