from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from .common import append_jsonl, load_json, read_jsonl, write_json, write_jsonl
from .experiment import QUERY_TERMS, usage_cost
from .faithfulness_audit import LABELS, call_auditor
from .guardrails import full_policy_conformance
from .retrieval import StandardsRetriever, load_standards_corpus
from .schemas import FULL_INTENT_SCHEMA, validate
from .shuffled_control import strengthening_usage


ACTION_QUERY_TERMS = {
    "NO_ACTION": "avoid unnecessary disruption continue observation",
    "MONITOR": "continuous monitoring detect anomalous behavior security events",
    "RATE_LIMIT": "rate limiting traffic filtering denial of service resource exhaustion",
    "BLOCK_TRAFFIC_PROFILE": "block filter validated malicious network traffic profile access control",
    "RESTRICT_EGRESS": "restrict outbound communication approved destinations network access policy MUD",
    "ISOLATE_SEGMENT": "isolate compromised device network segment containment",
    "INCREASE_LOGGING": "increase security event logging monitoring incident analysis",
    "CAPTURE_TRAFFIC": "collect network traffic evidence incident analysis monitoring",
    "REQUIRE_REAUTHENTICATION": "authentication failed attempts account access reauthentication",
    "NOTIFY_OPERATOR": "incident notification response escalation operator",
}


def build_bound_intents(config: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    chunks = load_standards_corpus(
        config["retrieval"]["standards_dir"],
        chunk_chars=int(config["retrieval"]["chunk_chars"]),
        chunk_overlap=int(config["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    records = [
        row
        for row in read_jsonl(
            "experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/results.jsonl"
        )
        if "error" not in row and row["condition"] == "rag"
    ]
    bound_records = []
    audit_items = []
    item_index = 0
    for record in records:
        intent = copy.deepcopy(record["normalized_intent"])
        family = record["alert"]["detector"]["predicted_family"]
        combined_evidence: dict[str, dict] = {}
        for action_index, action in enumerate(intent["actions"], start=1):
            action_name = action["action"]
            query = " ".join(
                [
                    QUERY_TERMS[family],
                    ACTION_QUERY_TERMS[action_name],
                    f"IoT predicted family {family} action {action_name}",
                ]
            )
            evidence = retriever.retrieve(query, top_k=2)
            action["evidence_refs"] = [item["chunk_id"] for item in evidence]
            for item in evidence:
                combined_evidence[item["chunk_id"]] = item
            item_index += 1
            audit_items.append(
                {
                    "audit_id": f"EB-{item_index:03d}",
                    "case_id": record["case_id"],
                    "action_index": action_index,
                    "predicted_family": family,
                    "action": action_name,
                    "rationale": action["rationale"],
                    "cited_evidence": [
                        {
                            "chunk_id": item["chunk_id"],
                            "source": Path(item["source"]).name,
                            "excerpt": item["excerpt"],
                        }
                        for item in evidence
                    ],
                }
            )
        available = list(combined_evidence)
        schema_valid, schema_errors = validate(intent, FULL_INTENT_SCHEMA)
        policy_valid, policy_errors = full_policy_conformance(
            intent, record["alert"], available
        )
        bound_records.append(
            {
                "case_id": record["case_id"],
                "alert": record["alert"],
                "evaluation": record["evaluation"],
                "intent": intent,
                "action_specific_evidence": list(combined_evidence.values()),
                "validity": {
                    "schema_valid": schema_valid,
                    "schema_errors": schema_errors,
                    "policy_valid": policy_valid,
                    "policy_errors": policy_errors,
                },
            }
        )
    write_jsonl(
        "experiments/runs/reference_evaluation/action_evidence_binding_audit/bound_intents.jsonl",
        bound_records,
    )
    packet = [
        {
            "audit_id": item["audit_id"],
            "predicted_family": item["predicted_family"],
            "action": item["action"],
            "rationale": item["rationale"],
            "cited_evidence": json.dumps(item["cited_evidence"], ensure_ascii=True),
            "human_label": "",
            "human_reason": "",
        }
        for item in audit_items
    ]
    pd.DataFrame(packet).to_csv(
        "reports/tables/action_evidence_binding_human_blind_packet.csv", index=False
    )
    return bound_records, audit_items


def run_binding_audit(config_path: str = "configs/experiment.json") -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the audit process.")
    from openai import OpenAI

    config = load_json(config_path)
    limits = config["strengthening_api"]
    audit_config = limits["faithfulness_audit"]
    agent_config = config["agent"]
    bound_records, items = build_bound_intents(config)
    families = sorted({item["predicted_family"] for item in items})
    batches = [
        [item for item in items if item["predicted_family"] == family]
        for family in families
    ]
    run_dir = Path("experiments/runs/reference_evaluation/action_evidence_binding_audit")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    existing = read_jsonl(results_path)
    completed = {row["batch_family"] for row in existing if "error" not in row}
    missing_batches = [
        (family, batch)
        for family, batch in zip(families, batches)
        if family not in completed
    ]
    local_used_calls = sum(int(row.get("api_attempts", 1)) for row in existing)
    local_used_cost = sum(float(row.get("estimated_cost_usd", 0.0)) for row in existing)
    per_batch_estimate = (
        int(audit_config["estimated_input_tokens_per_call"])
        / 1_000_000
        * float(agent_config["input_usd_per_million"])
        + int(audit_config["estimated_output_tokens_per_call"])
        / 1_000_000
        * float(agent_config["output_usd_per_million"])
    )
    full_preflight_cost = len(batches) * per_batch_estimate
    preflight_cost = len(missing_batches) * per_batch_estimate
    if local_used_calls + len(missing_batches) > int(audit_config["max_calls"]):
        raise RuntimeError("Evidence-binding audit exceeds its local call cap.")
    if local_used_cost + preflight_cost > float(audit_config["max_cost_usd"]):
        raise RuntimeError("Evidence-binding audit exceeds its local cost cap.")
    combined_calls, combined_cost = strengthening_usage()
    if combined_calls + len(missing_batches) > int(limits["combined_max_calls"]):
        raise RuntimeError("Evidence-binding audit would exceed the combined call cap.")
    if combined_cost + preflight_cost > float(limits["combined_max_cost_usd"]):
        raise RuntimeError("Evidence-binding audit would exceed the combined cost cap.")

    attempted = sum(int(row.get("api_attempts", 1)) for row in existing)
    client = OpenAI()
    for family, batch in zip(families, batches):
        if family in completed:
            continue
        if attempted >= int(audit_config["max_calls"]):
            raise RuntimeError("Evidence-binding audit hard call cap reached.")
        combined_calls, combined_cost = strengthening_usage()
        if combined_calls >= int(limits["combined_max_calls"]):
            raise RuntimeError("Combined strengthening hard call cap reached.")
        if combined_cost >= float(limits["combined_max_cost_usd"]):
            raise RuntimeError("Combined strengthening hard cost cap reached.")
        attempted += 1
        try:
            result = call_auditor(
                client,
                str(audit_config["model"]),
                int(audit_config["max_output_tokens"]),
                batch,
            )
            result.update(
                {
                    "batch_family": family,
                    "api_attempts": 1,
                    "estimated_cost_usd": usage_cost(
                        agent_config, result["input_tokens"], result["output_tokens"]
                    ),
                }
            )
            append_jsonl(results_path, result)
        except Exception as exc:
            append_jsonl(
                results_path,
                {
                    "batch_family": family,
                    "api_attempts": 1,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )

    records = [row for row in read_jsonl(results_path) if "error" not in row]
    judgments = {
        judgment["audit_id"]: judgment
        for record in records
        for judgment in record["judgments"]
    }
    if len(judgments) != len(items):
        raise RuntimeError("The evidence-binding action audit is incomplete.")
    labelled = []
    for item in items:
        judgment = judgments[item["audit_id"]]
        labelled.append(
            {
                **{key: value for key, value in item.items() if key != "cited_evidence"},
                "label": judgment["label"],
                "reason": judgment["reason"],
            }
        )
    pd.DataFrame(labelled).to_csv(
        "reports/tables/action_evidence_binding_items.csv", index=False
    )
    counts = pd.Series([row["label"] for row in labelled]).value_counts().to_dict()
    case_groups = {}
    for row in labelled:
        case_groups.setdefault(row["case_id"], []).append(row)
    all_supported = {
        case_id: all(row["label"] != "unsupported" for row in rows)
        for case_id, rows in case_groups.items()
    }
    cost = sum(float(record["estimated_cost_usd"]) for record in records)
    summary = {
        "method": "deterministic action-specific retrieval after guardrail normalization",
        "actions": len(labelled),
        "label_counts": {label: int(counts.get(label, 0)) for label in LABELS},
        "direct_support_rate": counts.get("directly_supported", 0) / len(labelled),
        "direct_or_general_support_rate": (
            counts.get("directly_supported", 0) + counts.get("generally_supported", 0)
        )
        / len(labelled),
        "unsupported_rate": counts.get("unsupported", 0) / len(labelled),
        "cases_with_all_actions_supported": int(sum(all_supported.values())),
        "case_all_actions_supported_rate": float(sum(all_supported.values()) / len(all_supported)),
        "bound_intent_schema_validity": float(
            sum(row["validity"]["schema_valid"] for row in bound_records) / len(bound_records)
        ),
        "bound_intent_policy_conformance": float(
            sum(row["validity"]["policy_valid"] for row in bound_records) / len(bound_records)
        ),
        "auditor_type": "blinded_model_based_action_to-evidence_audit",
        "calls": sum(int(record.get("api_attempts", 1)) for record in records),
        "estimated_cost_usd": cost,
        "hard_call_cap": int(audit_config["max_calls"]),
        "hard_cost_cap_usd": float(audit_config["max_cost_usd"]),
        "combined_hard_call_cap": int(limits["combined_max_calls"]),
        "combined_hard_cost_cap_usd": float(limits["combined_max_cost_usd"]),
        "preflight_cost_estimate_usd": full_preflight_cost,
        "additional_preflight_cost_estimate_usd": preflight_cost,
        "human_audit_status": "A label-free action-binding packet is available for human review.",
    }
    write_json("reports/tables/action_evidence_binding.json", summary)
    write_json(run_dir / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit deterministic action-evidence binding.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    print(json.dumps(run_binding_audit(args.config), indent=2))


if __name__ == "__main__":
    main()
