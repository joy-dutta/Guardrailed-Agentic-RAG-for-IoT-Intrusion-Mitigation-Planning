from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from .common import load_json, read_jsonl, write_json, write_jsonl
from .experiment import retrieval_query
from .guardrails import canonical_action, full_policy_conformance, normalize_intent
from .retrieval import StandardsRetriever, load_standards_corpus
from .schemas import FULL_INTENT_SCHEMA, validate


def action_names(intent: dict[str, Any]) -> list[str]:
    return [str(item["action"]) for item in intent.get("actions", [])]


def raw_action_names(record: dict[str, Any]) -> set[str]:
    raw = record.get("raw_intent", {})
    actions = raw.get("recommended_actions", []) if isinstance(raw, dict) else []
    return {
        canonical_action(item.get("action"))
        for item in actions
        if isinstance(item, dict) and item.get("action")
    }


def jaccard(left: list[str], right: list[str]) -> float:
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def run_policy_baseline(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    planning = extension["planning"]
    run_dir = Path("experiments/runs") / str(planning["run_id"])
    agent_rows = [
        row for row in read_jsonl(run_dir / "results.jsonl") if "error" not in row
    ]
    rag_rows = {row["case_id"]: row for row in agent_rows if row["condition"] == "rag"}
    no_rag_rows = {
        row["case_id"]: row for row in agent_rows if row["condition"] == "no_rag"
    }
    cases = read_jsonl(planning["cases_path"])
    chunks = load_standards_corpus(
        base["retrieval"]["standards_dir"],
        int(base["retrieval"]["chunk_chars"]),
        int(base["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)

    records = []
    for case in cases:
        case_id = case["case_id"]
        rag = rag_rows.get(case_id)
        evidence = (
            rag["evidence"]
            if rag
            else retriever.retrieve(
                retrieval_query(case["alert"]), int(base["retrieval"]["top_k"])
            )
        )
        baseline = normalize_intent({}, case["alert"], evidence)
        schema_valid, schema_errors = validate(baseline, FULL_INTENT_SCHEMA)
        policy_valid, policy_errors = full_policy_conformance(
            baseline,
            case["alert"],
            [item["chunk_id"] for item in evidence],
        )
        rag_actions = action_names(rag["normalized_intent"]) if rag else []
        baseline_actions = action_names(baseline)
        raw_actions = raw_action_names(rag) if rag else set()
        retained = [action for action in rag_actions if action in raw_actions]
        no_rag_actions = (
            action_names(no_rag_rows[case_id]["normalized_intent"])
            if case_id in no_rag_rows
            else []
        )
        records.append(
            {
                "case_id": case_id,
                "true_family": case["evaluation"]["true_family"],
                "predicted_family": case["alert"]["detector"]["predicted_family"],
                "route": case["alert"]["routing_decision"],
                "policy_only_intent": baseline,
                "policy_only_schema_valid": schema_valid,
                "policy_only_schema_errors": schema_errors,
                "policy_only_policy_valid": policy_valid,
                "policy_only_policy_errors": policy_errors,
                "policy_only_actions": baseline_actions,
                "rag_guardrailed_actions": rag_actions,
                "no_rag_guardrailed_actions": no_rag_actions,
                "rag_raw_actions": sorted(raw_actions),
                "rag_actions_retained_from_llm": retained,
                "rag_policy_jaccard": jaccard(rag_actions, baseline_actions),
                "rag_matches_policy_only": rag_actions == baseline_actions,
                "no_rag_matches_policy_only": no_rag_actions == baseline_actions,
            }
        )

    write_jsonl(
        "reports/comprehensive_evaluation/tables/policy_only_baseline_records.jsonl",
        records,
    )
    routes = sorted({row["route"] for row in records})
    summary = {
        "cases": len(records),
        "policy_only_schema_validity": float(
            np.mean([row["policy_only_schema_valid"] for row in records])
        ),
        "policy_only_policy_conformance": float(
            np.mean([row["policy_only_policy_valid"] for row in records])
        ),
        "agent_comparison_cases": len(rag_rows),
        "rag_cases_with_at_least_one_llm_action_retained": int(
            sum(bool(row["rag_actions_retained_from_llm"]) for row in records)
        ) if rag_rows else None,
        "rag_case_retention_rate": float(
            np.mean([bool(row["rag_actions_retained_from_llm"]) for row in records])
        ) if rag_rows else None,
        "rag_exact_policy_only_match_rate": float(
            np.mean([row["rag_matches_policy_only"] for row in records])
        ) if rag_rows else None,
        "no_rag_exact_policy_only_match_rate": float(
            np.mean([row["no_rag_matches_policy_only"] for row in records])
        ) if no_rag_rows else None,
        "rag_mean_action_set_jaccard": float(
            np.mean([row["rag_policy_jaccard"] for row in records])
        ) if rag_rows else None,
        "unique_policy_only_action_sets": len(
            {tuple(row["policy_only_actions"]) for row in records}
        ),
        "unique_rag_action_sets": len(
            {tuple(row["rag_guardrailed_actions"]) for row in records}
        ) if rag_rows else None,
        "rag_retained_action_counts": dict(
            Counter(
                action
                for row in records
                for action in row["rag_actions_retained_from_llm"]
            )
        ) if rag_rows else None,
        "by_route": {
            route: {
                "cases": sum(row["route"] == route for row in records),
                "rag_case_retention_rate": float(
                    np.mean(
                        [
                            bool(row["rag_actions_retained_from_llm"])
                            for row in records
                            if row["route"] == route
                        ]
                    )
                ) if rag_rows else None,
                "rag_exact_policy_only_match_rate": float(
                    np.mean(
                        [
                            row["rag_matches_policy_only"]
                            for row in records
                            if row["route"] == route
                        ]
                    )
                ) if rag_rows else None,
            }
            for route in routes
        },
        "interpretation_guardrail": (
            "This ablation measures whether LLM-proposed action names survive deterministic "
            "validation and whether the final set differs from fixed defaults. It does not "
            "by itself establish that a different plan is operationally better."
        ),
    }
    write_json("reports/comprehensive_evaluation/tables/policy_only_baseline.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the guarded agent with a deterministic policy-only planner."
    )
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    print(json.dumps(run_policy_baseline(args.config), indent=2))


if __name__ == "__main__":
    main()
