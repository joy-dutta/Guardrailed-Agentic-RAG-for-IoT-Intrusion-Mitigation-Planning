from __future__ import annotations

import argparse
import copy
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .action_evidence_binding import ACTION_QUERY_TERMS
from .common import append_jsonl, load_json, read_jsonl, write_json, write_jsonl
from .experiment import QUERY_TERMS
from .faithfulness_audit import LABELS, call_auditor
from .guardrails import bounded_parameters, full_policy_conformance
from .retrieval import StandardsRetriever, load_standards_corpus
from .schemas import ACTION_COMPATIBILITY, DISRUPTIVE_ACTIONS, FULL_INTENT_SCHEMA, validate


PROTOCOL_FIELDS = (
    "TCP",
    "UDP",
    "ICMP",
    "IGMP",
    "HTTP",
    "HTTPS",
    "DNS",
    "ARP",
    "DHCP",
    "Telnet",
    "SMTP",
    "SSH",
    "IRC",
    "IPv",
    "LLC",
)

FEATURE_QUERY_TERMS = {
    "Rate": "traffic packet rate volume frequency",
    "AVG": "average packet size traffic profile",
    "IAT": "inter arrival time traffic timing",
    "syn_count": "TCP SYN connection attempts",
    "syn_flag_number": "TCP SYN flag connection attempts",
    "ack_count": "TCP ACK responses",
    "ack_flag_number": "TCP ACK flag responses",
    "rst_count": "TCP reset events",
    "rst_flag_number": "TCP reset flag events",
}


def _positive_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0


def observed_context(observations: dict[str, Any]) -> str:
    protocols = [name for name in PROTOCOL_FIELDS if _positive_number(observations.get(name))]
    features = [
        text for name, text in FEATURE_QUERY_TERMS.items() if _positive_number(observations.get(name))
    ]
    return " ".join(
        [
            f"observed protocols {' '.join(protocols) if protocols else 'unspecified'}",
            f"observed indicators {' '.join(features[:5]) if features else 'network flow telemetry'}",
        ]
    )


def action_retrieval_query(alert: dict[str, Any], action: str) -> str:
    family = alert["detector"]["predicted_family"]
    return " ".join(
        [
            QUERY_TERMS[family],
            ACTION_QUERY_TERMS[action],
            f"IoT predicted family {family} proposed action {action}",
            observed_context(alert.get("observations", {})),
        ]
    )


def fallback_retrieval_query(alert: dict[str, Any], action: str) -> str:
    family = alert["detector"]["predicted_family"]
    action_terms = ACTION_QUERY_TERMS[action]
    return " ".join(
        [
            action_terms,
            action_terms,
            action_terms,
            f"incident response action {action} for an IoT gateway",
            f"predicted family context {family}",
            observed_context(alert.get("observations", {})),
        ]
    )


def fallback_candidates(record: dict[str, Any]) -> list[str]:
    intent = (
        record.get("normalized_intent")
        or record.get("gated_intent")
        or record["original_intent"]
    )
    route = intent["route"]
    family = record["alert"]["detector"]["predicted_family"]
    if route == "monitor":
        return ["MONITOR"]
    if route == "escalate":
        return ["CAPTURE_TRAFFIC", "MONITOR", "NOTIFY_OPERATOR"]
    return [
        action
        for action in ("CAPTURE_TRAFFIC", "MONITOR", "NOTIFY_OPERATOR")
        if action in ACTION_COMPATIBILITY[family]
    ]


def deterministic_eligibility(item: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    family = item["predicted_family"]
    action = item["action"]
    route = item["route"]
    if action not in ACTION_COMPATIBILITY[family] and route != "escalate":
        reasons.append(f"{action} is not allowed for predicted family {family}.")
    if route in {"monitor", "escalate"} and action in DISRUPTIVE_ACTIONS:
        reasons.append(f"{action} is disruptive on the {route} route.")
    retrieved_ids = {row["chunk_id"] for row in item["cited_evidence"]}
    cited_ids = set(item["evidence_refs"])
    if not cited_ids:
        reasons.append("The action has no evidence reference.")
    if not cited_ids.issubset(retrieved_ids):
        reasons.append("At least one cited identifier is outside the action-specific retrieval set.")
    return not reasons, reasons


def checker_keeps_action(
    item: dict[str, Any], label: str, variant: str = "strict"
) -> tuple[bool, str]:
    eligible, reasons = deterministic_eligibility(item)
    if not eligible:
        return False, " ".join(reasons)
    if label == "directly_supported":
        return True, "The action has direct documentary support."
    if label == "generally_supported" and item["action"] not in DISRUPTIVE_ACTIONS:
        return True, "General support is sufficient for this non-disruptive action."
    if label == "generally_supported" and variant == "review_queue":
        return True, "The disruptive action remains proposed but requires human approval."
    if label == "generally_supported":
        return False, "General evidence is insufficient for a disruptive action without human approval."
    return False, "The independent checker found no useful support for the action."


def fallback_action_for(record: dict[str, Any]) -> str:
    route = record["normalized_intent"]["route"]
    family = record["alert"]["detector"]["predicted_family"]
    if route == "monitor":
        return "MONITOR"
    if route == "escalate":
        return "NOTIFY_OPERATOR"
    if "CAPTURE_TRAFFIC" in ACTION_COMPATIBILITY[family]:
        return "CAPTURE_TRAFFIC"
    return "NOTIFY_OPERATOR"


def _evidence_payload(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": row["chunk_id"],
            "source": Path(row["source"]).name,
            "excerpt": row["excerpt"],
        }
        for row in evidence
    ]


def build_action_items(
    experiment_config: dict[str, Any], gate_config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_condition = str(gate_config.get("source_condition", "rag"))
    records = [
        row
        for row in read_jsonl(gate_config["source_results"])
        if "error" not in row and row.get("condition") == source_condition
    ]
    records.sort(key=lambda row: row["case_id"])
    chunks = load_standards_corpus(
        experiment_config["retrieval"]["standards_dir"],
        chunk_chars=int(experiment_config["retrieval"]["chunk_chars"]),
        chunk_overlap=int(experiment_config["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    top_k = int(gate_config["retrieval"]["top_k"])
    items: list[dict[str, Any]] = []
    for record in records:
        intent = record["normalized_intent"]
        family = record["alert"]["detector"]["predicted_family"]
        for action_index, action in enumerate(intent["actions"], start=1):
            query = action_retrieval_query(record["alert"], action["action"])
            evidence = retriever.retrieve(query, top_k=top_k)
            item = {
                "audit_id": f"EG-O-{len(items) + 1:04d}",
                "item_type": "original",
                "case_id": record["case_id"],
                "action_index": action_index,
                "predicted_family": family,
                "route": intent["route"],
                "action": action["action"],
                "rationale": action["rationale"],
                "approval_required": bool(action["approval_required"]),
                "retrieval_query": query,
                "evidence_refs": [row["chunk_id"] for row in evidence],
                "cited_evidence": _evidence_payload(evidence),
            }
            eligible, reasons = deterministic_eligibility(item)
            item["deterministic_eligible"] = eligible
            item["eligibility_reasons"] = reasons
            items.append(item)
    return records, items


def _cost(config: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * float(config["input_usd_per_million"])
        + output_tokens / 1_000_000 * float(config["output_usd_per_million"])
    )


def _saved_usage(paths: Iterable[Path]) -> tuple[int, float]:
    rows = [row for path in paths for row in read_jsonl(path)]
    calls = sum(int(row.get("api_attempts", 1)) for row in rows)
    cost = sum(float(row.get("estimated_cost_usd", 0.0)) for row in rows)
    return calls, cost


def _preflight_cost(config: dict[str, Any], calls: int) -> float:
    return _cost(
        config,
        calls * int(config["estimated_input_tokens_per_call"]),
        calls * int(config["estimated_output_tokens_per_call"]),
    )


def _checker_batches(items: list[dict[str, Any]], prefix: str) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["predicted_family"]].append(item)
    return [(f"{prefix}:{family}", grouped[family]) for family in sorted(grouped)]


def run_checker(
    client: Any,
    checker_name: str,
    checker_config: dict[str, Any],
    batches: list[tuple[str, list[dict]]],
    output_path: Path,
    all_result_paths: list[Path],
    combined_config: dict[str, Any],
) -> dict[str, dict[str, str]]:
    existing = read_jsonl(output_path)
    completed = {row["batch_id"] for row in existing if "error" not in row}
    missing = [(batch_id, batch) for batch_id, batch in batches if batch_id not in completed]
    local_calls, local_cost = _saved_usage([output_path])
    combined_calls, combined_cost = _saved_usage(all_result_paths)
    reserve = _preflight_cost(checker_config, len(missing))
    if local_calls + len(missing) > int(checker_config["max_calls"]):
        raise RuntimeError(f"{checker_name} would exceed its hard call cap.")
    if local_cost + reserve > float(checker_config["max_cost_usd"]):
        raise RuntimeError(f"{checker_name} would exceed its hard dollar cap.")
    if combined_calls + len(missing) > int(combined_config["combined_max_calls"]):
        raise RuntimeError("The evidence-gate run would exceed its combined hard call cap.")
    if combined_cost + reserve > float(combined_config["combined_max_cost_usd"]):
        raise RuntimeError("The evidence-gate run would exceed its combined hard dollar cap.")

    for batch_id, batch in missing:
        local_calls, local_cost = _saved_usage([output_path])
        combined_calls, combined_cost = _saved_usage(all_result_paths)
        if local_calls >= int(checker_config["max_calls"]):
            raise RuntimeError(f"{checker_name} reached its hard call cap.")
        if local_cost >= float(checker_config["max_cost_usd"]):
            raise RuntimeError(f"{checker_name} reached its hard dollar cap.")
        if combined_calls >= int(combined_config["combined_max_calls"]):
            raise RuntimeError("The evidence-gate run reached its combined hard call cap.")
        if combined_cost >= float(combined_config["combined_max_cost_usd"]):
            raise RuntimeError("The evidence-gate run reached its combined hard dollar cap.")
        try:
            result = call_auditor(
                client,
                str(checker_config["model"]),
                int(checker_config["max_output_tokens"]),
                batch,
            )
            result.update(
                {
                    "checker": checker_name,
                    "batch_id": batch_id,
                    "api_attempts": 1,
                    "estimated_cost_usd": _cost(
                        checker_config, result["input_tokens"], result["output_tokens"]
                    ),
                }
            )
            append_jsonl(output_path, result)
        except Exception as exc:
            append_jsonl(
                output_path,
                {
                    "checker": checker_name,
                    "batch_id": batch_id,
                    "api_attempts": 1,
                    "estimated_cost_usd": 0.0,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            raise

    judgments = {
        judgment["audit_id"]: judgment
        for row in read_jsonl(output_path)
        if "error" not in row
        for judgment in row["judgments"]
    }
    expected = {item["audit_id"] for _, batch in batches for item in batch}
    if not expected.issubset(judgments):
        missing_ids = sorted(expected - set(judgments))
        raise RuntimeError(f"{checker_name} is incomplete; missing {len(missing_ids)} judgments.")
    return {item_id: judgments[item_id] for item_id in expected}


def provisional_survivors(
    records: list[dict[str, Any]],
    items: list[dict[str, Any]],
    judgments: dict[str, dict[str, str]],
    variant: str,
) -> dict[str, list[str]]:
    survivors: dict[str, list[str]] = {record["case_id"]: [] for record in records}
    for item in items:
        keep, _ = checker_keeps_action(item, judgments[item["audit_id"]]["label"], variant)
        if keep:
            survivors[item["case_id"]].append(item["audit_id"])
    return survivors


def build_fallback_items(
    records: list[dict[str, Any]],
    original_items: list[dict[str, Any]],
    checker_a: dict[str, dict[str, str]],
    experiment_config: dict[str, Any],
    gate_config: dict[str, Any],
) -> list[dict[str, Any]]:
    strict = provisional_survivors(records, original_items, checker_a, "strict")
    review = provisional_survivors(records, original_items, checker_a, "review_queue")
    needs_fallback = {
        case_id for case_id in strict if not strict[case_id] or not review[case_id]
    }
    chunks = load_standards_corpus(
        experiment_config["retrieval"]["standards_dir"],
        chunk_chars=int(experiment_config["retrieval"]["chunk_chars"]),
        chunk_overlap=int(experiment_config["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    top_k = int(gate_config["retrieval"]["top_k"])
    fallbacks = []
    for record in records:
        if record["case_id"] not in needs_fallback:
            continue
        action = fallback_action_for(record)
        query = action_retrieval_query(record["alert"], action)
        evidence = retriever.retrieve(query, top_k=top_k)
        item = {
            "audit_id": f"EG-F-{len(fallbacks) + 1:04d}",
            "item_type": "fallback",
            "case_id": record["case_id"],
            "action_index": 0,
            "predicted_family": record["alert"]["detector"]["predicted_family"],
            "route": record["normalized_intent"]["route"],
            "action": action,
            "rationale": "Use a bounded, non-disruptive fallback because no evidence-eligible action remained.",
            "approval_required": False,
            "retrieval_query": query,
            "evidence_refs": [row["chunk_id"] for row in evidence],
            "cited_evidence": _evidence_payload(evidence),
        }
        eligible, reasons = deterministic_eligibility(item)
        item["deterministic_eligible"] = eligible
        item["eligibility_reasons"] = reasons
        fallbacks.append(item)
    return fallbacks


def _fallback_action_object(record: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    action = item["action"]
    return {
        "action": action,
        "target": record["alert"]["gateway_scope"],
        "parameters": bounded_parameters(action, {}),
        "duration_seconds": 0 if action == "NOTIFY_OPERATOR" else 900,
        "rollback": "Expire the temporary gateway policy and restore the previous validated configuration.",
        "approval_required": False,
        "evidence_refs": item["evidence_refs"],
        "rationale": item["rationale"],
    }


def apply_gate(
    records: list[dict[str, Any]],
    original_items: list[dict[str, Any]],
    fallback_items: list[dict[str, Any]],
    checker_a: dict[str, dict[str, str]],
    variant: str,
) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in original_items:
        by_case[item["case_id"]].append(item)
    fallback_by_case = {item["case_id"]: item for item in fallback_items}
    output = []
    for record in records:
        intent = copy.deepcopy(record["normalized_intent"])
        source_actions = intent["actions"]
        final_actions = []
        decisions = []
        final_item_ids = []
        for item, action_object in zip(by_case[record["case_id"]], source_actions):
            judgment = checker_a[item["audit_id"]]
            keep, reason = checker_keeps_action(item, judgment["label"], variant)
            decisions.append(
                {
                    "audit_id": item["audit_id"],
                    "action": item["action"],
                    "checker_a_label": judgment["label"],
                    "decision": "keep" if keep else "remove",
                    "reason": reason,
                }
            )
            if keep:
                revised = copy.deepcopy(action_object)
                revised["evidence_refs"] = item["evidence_refs"]
                final_actions.append(revised)
                final_item_ids.append(item["audit_id"])
        fallback_used = False
        if not final_actions:
            fallback = fallback_by_case[record["case_id"]]
            final_actions = [_fallback_action_object(record, fallback)]
            final_item_ids = [fallback["audit_id"]]
            fallback_used = True
            fallback_label = checker_a[fallback["audit_id"]]["label"]
            decisions.append(
                {
                    "audit_id": fallback["audit_id"],
                    "action": fallback["action"],
                    "checker_a_label": fallback_label,
                    "decision": "fallback",
                    "reason": "Inserted a bounded, non-disruptive action after the gate removed every original action.",
                }
            )
        intent["actions"] = final_actions[:3]
        intent["guardrail"]["normalization_notes"].append(
            f"Applied the {variant} action-to-evidence support gate."
        )
        available = [ref for action in intent["actions"] for ref in action["evidence_refs"]]
        schema_valid, schema_errors = validate(intent, FULL_INTENT_SCHEMA)
        policy_valid, policy_errors = full_policy_conformance(intent, record["alert"], available)
        intent["guardrail"]["schema_validated"] = schema_valid
        intent["guardrail"]["policy_validated"] = policy_valid
        output.append(
            {
                "case_id": record["case_id"],
                "variant": variant,
                "alert": record["alert"],
                "evaluation": record["evaluation"],
                "original_intent": record["normalized_intent"],
                "gated_intent": intent,
                "original_item_ids": [item["audit_id"] for item in by_case[record["case_id"]]],
                "final_item_ids": final_item_ids,
                "fallback_used": fallback_used,
                "gate_decisions": decisions,
                "validity": {
                    "schema_valid": schema_valid,
                    "schema_errors": schema_errors,
                    "policy_valid": policy_valid,
                    "policy_errors": policy_errors,
                },
            }
        )
    return output


def _label_counts(ids: list[str], judgments: dict[str, dict[str, str]]) -> dict[str, int]:
    counts = Counter(judgments[item_id]["label"] for item_id in ids)
    return {label: int(counts[label]) for label in LABELS}


def _case_all_supported(
    records: list[dict[str, Any]], id_key: str, judgments: dict[str, dict[str, str]]
) -> dict[str, bool]:
    return {
        row["case_id"]: all(judgments[item_id]["label"] != "unsupported" for item_id in row[id_key])
        for row in records
    }


def exact_paired_test(before: dict[str, bool], after: dict[str, bool]) -> dict[str, Any]:
    improved = sum(not before[key] and after[key] for key in before)
    worsened = sum(before[key] and not after[key] for key in before)
    discordant = improved + worsened
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(improved, worsened) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "improved_cases": improved,
        "worsened_cases": worsened,
        "discordant_cases": discordant,
        "two_sided_exact_mcnemar_p": p_value,
    }


def cohen_kappa(
    first: dict[str, dict[str, str]], second: dict[str, dict[str, str]], ids: list[str]
) -> dict[str, Any]:
    pairs = [(first[item_id]["label"], second[item_id]["label"]) for item_id in ids]
    agreement = sum(a == b for a, b in pairs) / len(pairs)
    first_counts = Counter(a for a, _ in pairs)
    second_counts = Counter(b for _, b in pairs)
    expected = sum(first_counts[label] * second_counts[label] for label in LABELS) / len(pairs) ** 2
    kappa = (agreement - expected) / (1 - expected) if expected < 1 else 1.0
    confusion = {
        first_label: {
            second_label: sum(a == first_label and b == second_label for a, b in pairs)
            for second_label in LABELS
        }
        for first_label in LABELS
    }
    return {"exact_agreement": agreement, "cohen_kappa": kappa, "confusion": confusion}


def summarize_variant(
    gated_records: list[dict[str, Any]],
    original_items: list[dict[str, Any]],
    all_items: list[dict[str, Any]],
    checker_b: dict[str, dict[str, str]],
) -> dict[str, Any]:
    original_ids = [item["audit_id"] for item in original_items]
    final_ids = [item_id for row in gated_records for item_id in row["final_item_ids"]]
    before_counts = _label_counts(original_ids, checker_b)
    after_counts = _label_counts(final_ids, checker_b)
    before_cases = _case_all_supported(gated_records, "original_item_ids", checker_b)
    after_cases = _case_all_supported(gated_records, "final_item_ids", checker_b)
    item_by_id = {item["audit_id"]: item for item in all_items}
    before_disruptive = [item_id for item_id in original_ids if item_by_id[item_id]["action"] in DISRUPTIVE_ACTIONS]
    after_disruptive = [item_id for item_id in final_ids if item_by_id[item_id]["action"] in DISRUPTIVE_ACTIONS]
    before_unsupported = before_counts["unsupported"] / len(original_ids)
    after_unsupported = after_counts["unsupported"] / len(final_ids)
    return {
        "cases": len(gated_records),
        "original_actions": len(original_ids),
        "final_actions": len(final_ids),
        "removed_actions": sum(
            decision["decision"] == "remove"
            for row in gated_records
            for decision in row["gate_decisions"]
        ),
        "fallback_cases": sum(row["fallback_used"] for row in gated_records),
        "schema_validity": sum(row["validity"]["schema_valid"] for row in gated_records) / len(gated_records),
        "policy_conformance": sum(row["validity"]["policy_valid"] for row in gated_records) / len(gated_records),
        "independent_evaluator": {
            "before_label_counts": before_counts,
            "after_label_counts": after_counts,
            "before_unsupported_rate": before_unsupported,
            "after_unsupported_rate": after_unsupported,
            "absolute_unsupported_rate_reduction": before_unsupported - after_unsupported,
            "relative_unsupported_rate_reduction": (
                (before_unsupported - after_unsupported) / before_unsupported
                if before_unsupported
                else 0.0
            ),
            "before_direct_or_general_rate": 1.0 - before_unsupported,
            "after_direct_or_general_rate": 1.0 - after_unsupported,
            "before_cases_all_actions_supported": sum(before_cases.values()),
            "after_cases_all_actions_supported": sum(after_cases.values()),
            "before_case_all_actions_supported_rate": sum(before_cases.values()) / len(before_cases),
            "after_case_all_actions_supported_rate": sum(after_cases.values()) / len(after_cases),
            "paired_case_test": exact_paired_test(before_cases, after_cases),
            "before_disruptive_actions": len(before_disruptive),
            "after_disruptive_actions": len(after_disruptive),
            "before_unsupported_disruptive_actions": sum(
                checker_b[item_id]["label"] == "unsupported" for item_id in before_disruptive
            ),
            "after_unsupported_disruptive_actions": sum(
                checker_b[item_id]["label"] == "unsupported" for item_id in after_disruptive
            ),
        },
    }


def _write_item_table(
    all_items: list[dict[str, Any]],
    checker_a: dict[str, dict[str, str]],
    checker_b: dict[str, dict[str, str]],
    gated: dict[str, list[dict[str, Any]]],
    path: Path,
) -> None:
    decisions = {
        (variant, row["case_id"], decision["audit_id"]): decision
        for variant, records in gated.items()
        for row in records
        for decision in row["gate_decisions"]
    }
    rows = []
    for item in all_items:
        row = {
            key: value
            for key, value in item.items()
            if key not in {"cited_evidence", "eligibility_reasons"}
        }
        row.update(
            {
                "sources": "; ".join(evidence["source"] for evidence in item["cited_evidence"]),
                "checker_a_label": checker_a[item["audit_id"]]["label"],
                "checker_a_reason": checker_a[item["audit_id"]]["reason"],
                "checker_b_label": checker_b[item["audit_id"]]["label"],
                "checker_b_reason": checker_b[item["audit_id"]]["reason"],
            }
        )
        for variant in gated:
            decision = decisions.get((variant, item["case_id"], item["audit_id"]), {})
            row[f"{variant}_decision"] = decision.get("decision", "not_used")
            row[f"{variant}_reason"] = decision.get("reason", "")
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _interpretation(summary: dict[str, Any]) -> str:
    strict = summary["variants"]["strict"]
    evaluation = strict["independent_evaluator"]
    improved = evaluation["after_unsupported_rate"] < evaluation["before_unsupported_rate"]
    verdict = (
        "The evidence gate improved action-to-evidence support under the independent evaluator."
        if improved
        else "The evidence gate did not improve action-to-evidence support under the independent evaluator."
    )
    return f"""# Evidence-Support Gate: Result and Meaning

## Plain-language result

{verdict}

The comparison starts from {strict['original_actions']} mitigation actions across {strict['cases']} real planning cases. The gate checks each action against a fresh, action-specific retrieval result. It removes actions that are incompatible with the predicted attack family, unsupported by the cited passage, or too disruptive for only general evidence. If a case is left with no useful action, the system inserts a bounded monitoring, evidence-collection, or operator-notification fallback.

An independent model, which did not make the gate decisions, judged the actions before and after filtering. Its unsupported rate changed from {evaluation['before_unsupported_rate']:.1%} to {evaluation['after_unsupported_rate']:.1%}. Cases in which every final action had at least general support changed from {evaluation['before_case_all_actions_supported_rate']:.1%} to {evaluation['after_case_all_actions_supported_rate']:.1%}.

## What this means in practice

The gate turns a valid citation identifier into a checked relationship between one proposed action and the passage cited for it. This is stronger than merely showing that the citation exists. It is still not proof that the action is operationally correct. The detector may be wrong, the standards corpus or policy table may be incomplete, and disruptive actions still require human approval before execution.

## Paper-safe interpretation

Use the independent-evaluator result as the main evidence. The checker used inside the gate will naturally show fewer unsupported actions because the gate was built from its labels. That construction-by-design result is useful for implementation auditing, but it should not be presented as independent performance evidence.
"""


def prepare_summary(gate_config: dict[str, Any], records: list[dict], items: list[dict]) -> dict[str, Any]:
    families = sorted({item["predicted_family"] for item in items})
    expected_gate_calls = len(families) + 1
    expected_evaluator_calls = len(families)
    gate_cost = _preflight_cost(gate_config["gate_checker"], expected_gate_calls)
    evaluator_cost = _preflight_cost(
        gate_config["independent_evaluator"], expected_evaluator_calls
    )
    return {
        "source_condition": str(gate_config.get("source_condition", "rag")),
        "source_cases": len(records),
        "source_actions": len(items),
        "predicted_families": families,
        "expected_gate_checker_calls": expected_gate_calls,
        "expected_independent_evaluator_calls": expected_evaluator_calls,
        "expected_total_calls": expected_gate_calls + expected_evaluator_calls,
        "preflight_cost_estimate_usd": gate_cost + evaluator_cost,
        "combined_hard_call_cap": int(gate_config["combined_max_calls"]),
        "combined_hard_cost_cap_usd": float(gate_config["combined_max_cost_usd"]),
    }


def run_evidence_gate(
    config_path: str | Path = "configs/ieee_access_evidence_gate.json",
    prepare_only: bool = False,
) -> dict[str, Any]:
    gate_config = load_json(config_path)
    experiment_config = load_json(gate_config["base_config"])
    report_prefix = str(gate_config.get("report_prefix", "evidence_gate"))
    records, original_items = build_action_items(experiment_config, gate_config)
    run_dir = Path("experiments/runs") / gate_config["run_id"]
    report_dir = Path("reports/journal_extension/tables")
    run_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "original_action_items.jsonl", original_items)
    preflight = prepare_summary(gate_config, records, original_items)
    write_json(run_dir / "preflight.json", preflight)
    if prepare_only:
        return preflight
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the evidence-gate process.")
    from openai import OpenAI

    client = OpenAI()
    checker_a_path = run_dir / "checker_a_results.jsonl"
    checker_b_path = run_dir / "checker_b_results.jsonl"
    all_result_paths = [checker_a_path, checker_b_path]
    checker_a = run_checker(
        client,
        "gate_checker",
        gate_config["gate_checker"],
        _checker_batches(original_items, "original"),
        checker_a_path,
        all_result_paths,
        gate_config,
    )
    fallback_items = build_fallback_items(
        records, original_items, checker_a, experiment_config, gate_config
    )
    write_jsonl(run_dir / "fallback_action_items.jsonl", fallback_items)
    if fallback_items:
        fallback_judgments = run_checker(
            client,
            "gate_checker",
            gate_config["gate_checker"],
            [("fallback:all", fallback_items)],
            checker_a_path,
            all_result_paths,
            gate_config,
        )
        checker_a.update(fallback_judgments)
    all_items = original_items + fallback_items
    checker_b = run_checker(
        client,
        "independent_evaluator",
        gate_config["independent_evaluator"],
        _checker_batches(all_items, "all"),
        checker_b_path,
        all_result_paths,
        gate_config,
    )
    gated = {
        variant: apply_gate(records, original_items, fallback_items, checker_a, variant)
        for variant in ("strict", "review_queue")
    }
    for variant, gated_records in gated.items():
        write_jsonl(run_dir / f"gated_{variant}.jsonl", gated_records)
    original_ids = [item["audit_id"] for item in original_items]
    total_calls, total_cost = _saved_usage(all_result_paths)
    summary = {
        **preflight,
        "method": (
            "Action-specific re-retrieval, deterministic eligibility checks, an independent "
            "three-level support gate, bounded fallbacks, and a separate-model evaluation."
        ),
        "checker_a": {
            "model": gate_config["gate_checker"]["model"],
            "label_counts_original": _label_counts(original_ids, checker_a),
        },
        "checker_b": {
            "model": gate_config["independent_evaluator"]["model"],
            "label_counts_original": _label_counts(original_ids, checker_b),
        },
        "inter_checker_agreement_on_original_actions": cohen_kappa(
            checker_a, checker_b, original_ids
        ),
        "variants": {
            variant: summarize_variant(records_for_variant, original_items, all_items, checker_b)
            for variant, records_for_variant in gated.items()
        },
        "actual_api_calls": total_calls,
        "actual_estimated_cost_usd": total_cost,
        "limitations": [
            "The gate and independent evaluator are both model-based; a blinded human audit remains necessary for a strong semantic-support claim.",
            "Support-checked evidence does not prove detector correctness or operational suitability.",
            "Disruptive actions remain proposals and require explicit human approval before any executor is considered.",
        ],
    }
    write_json(run_dir / "summary.json", summary)
    write_json(report_dir / f"{report_prefix}_ablation.json", summary)
    _write_item_table(
        all_items,
        checker_a,
        checker_b,
        gated,
        report_dir / f"{report_prefix}_items.csv",
    )
    interpretation_path = Path("reports/journal_extension") / f"{report_prefix.upper()}_INTERPRETATION.md"
    interpretation_path.write_text(_interpretation(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the IEEE Access action-to-evidence support-gate experiment."
    )
    parser.add_argument("--config", default="configs/ieee_access_evidence_gate.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_evidence_gate(args.config, args.prepare_only), indent=2))


if __name__ == "__main__":
    main()
