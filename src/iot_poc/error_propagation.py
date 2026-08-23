from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .common import read_jsonl, write_json
from .guardrails import full_policy_conformance, normalize_intent
from .schemas import ACTION_COMPATIBILITY, DISRUPTIVE_ACTIONS, FULL_INTENT_SCHEMA, validate


ESCALATION_SAFE_ACTIONS = {"CAPTURE_TRAFFIC", "INCREASE_LOGGING", "NOTIFY_OPERATOR", "MONITOR"}
ACTION_PREFERENCE = [
    "MONITOR",
    "INCREASE_LOGGING",
    "CAPTURE_TRAFFIC",
    "NOTIFY_OPERATOR",
    "RATE_LIMIT",
    "REQUIRE_REAUTHENTICATION",
    "RESTRICT_EGRESS",
    "BLOCK_TRAFFIC_PROFILE",
    "ISOLATE_SEGMENT",
]


def prediction_lookup() -> dict[tuple[str, int], dict[str, Any]]:
    frame = pd.read_csv("data/processed/test_predictions_protocol_attack_type_aware.csv")
    probability_columns = [column for column in frame if column.startswith("probability_")]
    lookup = {}
    for _, row in frame.iterrows():
        probabilities = {
            column.removeprefix("probability_"): float(row[column])
            for column in probability_columns
        }
        ordered = sorted(probabilities, key=probabilities.get, reverse=True)
        lookup[(str(row["source_file"]), int(row["source_row"]))] = {
            "candidate_families": ordered[:2],
            "top_1_probability": probabilities[ordered[0]],
            "top_2_probability": probabilities[ordered[1]],
            "margin": probabilities[ordered[0]] - probabilities[ordered[1]],
        }
    return lookup


def true_family_safe(intent: dict[str, Any], true_family: str) -> tuple[bool, list[str]]:
    actions = [item.get("action") for item in intent.get("actions", [])]
    if intent.get("route") == "escalate":
        unsafe = [action for action in actions if action not in ESCALATION_SAFE_ACTIONS]
    else:
        unsafe = [action for action in actions if action not in ACTION_COMPATIBILITY[true_family]]
    return not unsafe, unsafe


def avoids_wrong_family_disruption(
    intent: dict[str, Any], true_family: str
) -> tuple[bool, list[str]]:
    unsafe = [
        item.get("action")
        for item in intent.get("actions", [])
        if item.get("action") in DISRUPTIVE_ACTIONS
        and item.get("action") not in ACTION_COMPATIBILITY[true_family]
    ]
    return not unsafe, unsafe


def conservative_normalize(
    raw: dict[str, Any],
    alert: dict[str, Any],
    evidence: list[dict[str, Any]],
    candidate_families: list[str],
) -> dict[str, Any]:
    if alert["routing_decision"] == "escalate" or alert["detector"]["predicted_family"] == "Benign":
        return normalize_intent(raw, alert, evidence)

    allowed = set.intersection(
        *(set(ACTION_COMPATIBILITY[family]) for family in candidate_families)
    )
    conservative_actions = [action for action in ACTION_PREFERENCE if action in allowed]
    if not conservative_actions:
        escalated_alert = copy.deepcopy(alert)
        escalated_alert["routing_decision"] = "escalate"
        intent = normalize_intent(raw, escalated_alert, evidence)
        intent["guardrail"]["normalization_notes"].append(
            "Top-two predicted families had no shared bounded action; routed to escalation."
        )
        return intent

    raw_by_action = {
        str(item.get("action")): item
        for item in raw.get("recommended_actions", [])
        if isinstance(item, dict)
    }
    proposal = copy.deepcopy(raw)
    proposal["recommended_actions"] = []
    for action in conservative_actions[:3]:
        proposal["recommended_actions"].append(
            raw_by_action.get(
                action,
                {
                    "action": action,
                    "target": alert["gateway_scope"],
                    "parameters": {},
                    "rationale": "Conservative action compatible with both leading detector hypotheses.",
                },
            )
        )
    intent = normalize_intent(proposal, alert, evidence)
    intent["guardrail"]["normalization_notes"].append(
        "Action set restricted to the intersection of the top-two predicted families."
    )
    return intent


def run_error_propagation(run_id: str = "paper_final_v2") -> dict[str, Any]:
    records = [
        row
        for row in read_jsonl(Path("experiments/runs") / run_id / "results.jsonl")
        if "error" not in row
    ]
    lookup = prediction_lookup()
    rows = []
    for record in records:
        evaluation = record["evaluation"]
        key = (str(evaluation["source_file"]), int(evaluation["source_row"]))
        uncertainty = lookup[key]
        true_family = evaluation["true_family"]
        current = record["normalized_intent"]
        current_safe, current_unsafe = true_family_safe(current, true_family)
        current_nonharmful, current_wrong_disruptive = avoids_wrong_family_disruption(
            current, true_family
        )
        conservative = conservative_normalize(
            record["raw_intent"],
            record["alert"],
            record["evidence"],
            uncertainty["candidate_families"],
        )
        conservative_safe, conservative_unsafe = true_family_safe(conservative, true_family)
        conservative_nonharmful, conservative_wrong_disruptive = (
            avoids_wrong_family_disruption(conservative, true_family)
        )
        schema_valid, schema_errors = validate(conservative, FULL_INTENT_SCHEMA)
        policy_valid, policy_errors = full_policy_conformance(
            conservative,
            {**record["alert"], "routing_decision": conservative["route"]},
            [item["chunk_id"] for item in record["evidence"]],
        )
        rows.append(
            {
                "case_id": record["case_id"],
                "condition": record["condition"],
                "detector_correct": bool(evaluation["detector_correct"]),
                "true_family": true_family,
                "predicted_family": record["alert"]["detector"]["predicted_family"],
                "top_2_family": uncertainty["candidate_families"][1],
                "probability_margin": uncertainty["margin"],
                "current_route": current["route"],
                "current_actions": [item["action"] for item in current["actions"]],
                "current_true_family_safe": current_safe,
                "current_unsafe_actions": current_unsafe,
                "current_avoids_wrong_family_disruption": current_nonharmful,
                "current_wrong_family_disruptive_actions": current_wrong_disruptive,
                "conservative_route": conservative["route"],
                "conservative_actions": [item["action"] for item in conservative["actions"]],
                "conservative_true_family_safe": conservative_safe,
                "conservative_unsafe_actions": conservative_unsafe,
                "conservative_avoids_wrong_family_disruption": conservative_nonharmful,
                "conservative_wrong_family_disruptive_actions": conservative_wrong_disruptive,
                "conservative_schema_valid": schema_valid,
                "conservative_schema_errors": schema_errors,
                "conservative_predicted_policy_valid": policy_valid,
                "conservative_predicted_policy_errors": policy_errors,
                "current_disruptive_actions": sum(
                    item["action"] in DISRUPTIVE_ACTIONS for item in current["actions"]
                ),
                "conservative_disruptive_actions": sum(
                    item["action"] in DISRUPTIVE_ACTIONS for item in conservative["actions"]
                ),
            }
        )

    frame = pd.DataFrame(rows)
    frame.to_csv("reports/tables/detector_error_propagation_items.csv", index=False)
    errors = frame.loc[~frame["detector_correct"]]
    summary = {
        "records": len(frame),
        "unique_cases": int(frame["case_id"].nunique()),
        "intentionally_misclassified_cases": int(errors["case_id"].nunique()),
        "current": {
            "strict_true_family_action_compatibility_all_records": float(
                frame["current_true_family_safe"].mean()
            ),
            "strict_true_family_action_compatibility_misclassified_records": float(
                errors["current_true_family_safe"].mean()
            ),
            "avoids_wrong_family_disruption_misclassified_records": float(
                errors["current_avoids_wrong_family_disruption"].mean()
            ),
            "all_record_true_family_safety": float(frame["current_true_family_safe"].mean()),
            "misclassified_record_true_family_safety": float(errors["current_true_family_safe"].mean()),
            "disruptive_actions": int(frame["current_disruptive_actions"].sum()),
        },
        "top_two_conservative": {
            "strict_true_family_action_compatibility_all_records": float(
                frame["conservative_true_family_safe"].mean()
            ),
            "strict_true_family_action_compatibility_misclassified_records": float(
                errors["conservative_true_family_safe"].mean()
            ),
            "avoids_wrong_family_disruption_misclassified_records": float(
                errors["conservative_avoids_wrong_family_disruption"].mean()
            ),
            "all_record_true_family_safety": float(frame["conservative_true_family_safe"].mean()),
            "misclassified_record_true_family_safety": float(
                errors["conservative_true_family_safe"].mean()
            ),
            "schema_validity": float(frame["conservative_schema_valid"].mean()),
            "predicted_policy_conformance": float(
                frame["conservative_predicted_policy_valid"].mean()
            ),
            "disruptive_actions": int(frame["conservative_disruptive_actions"].sum()),
            "escalated_records": int((frame["conservative_route"] == "escalate").sum()),
        },
        "interpretation_boundary": (
            "Strict true-family compatibility measures whether an action is appropriate for "
            "the hidden dataset label; harmless observation may therefore count as insufficient. "
            "Wrong-family disruption separately asks whether a detector error caused an "
            "incompatible disruptive action. The deployable policy uses only top-two predictions."
        ),
    }
    write_json("reports/tables/detector_error_propagation.json", summary)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.bar(
        ["Current\nnormalization", "Top-two\nconservative"],
        [
            summary["current"]["misclassified_record_true_family_safety"],
            summary["top_two_conservative"]["misclassified_record_true_family_safety"],
        ],
        color=["#E07A5F", "#287271"],
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("True-family-safe intents on detector errors")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_error_propagation.png", dpi=240)
    plt.close(fig)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate detector-error propagation.")
    parser.add_argument("--run-id", default="paper_final_v2")
    args = parser.parse_args()
    print(run_error_propagation(args.run_id))


if __name__ == "__main__":
    main()
