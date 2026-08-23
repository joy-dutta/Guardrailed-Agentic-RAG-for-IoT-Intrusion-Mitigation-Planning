from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import load_json, write_jsonl


OBSERVATION_FEATURES = [
    "Protocol Type",
    "Time_To_Live",
    "Rate",
    "TCP",
    "UDP",
    "ICMP",
    "HTTP",
    "HTTPS",
    "DNS",
    "ARP",
    "syn_flag_number",
    "ack_flag_number",
    "rst_flag_number",
    "syn_count",
    "ack_count",
    "rst_count",
    "AVG",
    "Std",
    "IAT",
]


def select_family_cases(group: pd.DataFrame) -> list[tuple[pd.Series, str]]:
    selected: list[tuple[pd.Series, str]] = []
    used: set[int] = set()
    correct = group.loc[group["correct"].astype(bool)].sort_values(
        "calibrated_confidence", ascending=False
    )
    for _, row in correct.head(2).iterrows():
        selected.append((row, "high_confidence_correct"))
        used.add(int(row.name))
    for _, row in correct.sort_values("calibrated_confidence").iterrows():
        if int(row.name) not in used:
            selected.append((row, "low_confidence_correct"))
            used.add(int(row.name))
            break
    errors = group.loc[~group["correct"].astype(bool)].sort_values(
        "calibrated_confidence", ascending=False
    )
    if not errors.empty:
        row = errors.iloc[0]
        selected.append((row, "highest_confidence_error"))
        used.add(int(row.name))
    for _, row in group.sort_values("calibrated_confidence").iterrows():
        if len(selected) >= 4:
            break
        if int(row.name) not in used:
            selected.append((row, "additional_boundary_case"))
            used.add(int(row.name))
    return selected[:4]


def build_cases_from_predictions(
    predictions_path: str | Path,
    threshold: float,
    model_name: str,
    output_path: str | Path,
    case_prefix: str = "iot",
) -> list[dict[str, Any]]:
    predictions = pd.read_csv(predictions_path)
    predictions["correct"] = predictions["correct"].astype(str).str.lower().eq("true")

    selected: list[tuple[pd.Series, str]] = []
    for family, group in predictions.groupby("family", sort=True):
        selected.extend(select_family_cases(group))

    cases = []
    for case_number, (row, reason) in enumerate(selected, start=1):
        confidence = float(row["calibrated_confidence"])
        predicted = str(row["predicted_family"])
        route = "escalate" if confidence < threshold else ("monitor" if predicted == "Benign" else "plan")
        observations = {
            feature: float(row[feature])
            for feature in OBSERVATION_FEATURES
            if feature in row and np.isfinite(row[feature])
        }
        case_id = f"{case_prefix}-{case_number:03d}"
        alert = {
            "schema": "iot.security.alert.v1",
            "alert_id": case_id,
            "detector": {
                "model": model_name,
                "predicted_family": predicted,
                "calibrated_confidence": confidence,
                "confidence_threshold": threshold,
            },
            "routing_decision": route,
            "gateway_scope": f"gateway/observed-flow-profile/{case_id}",
            "observations": observations,
            "limitations": [
                "The CSV features do not provide a validated device identifier.",
                "The output is mitigation intent only and cannot execute an action.",
            ],
        }
        cases.append(
            {
                "case_id": case_id,
                "selection_reason": reason,
                "alert": alert,
                "evaluation": {
                    "true_family": str(row["family"]),
                    "attack_type": str(row["attack_type"]),
                    "source_file": str(row["source_file"]),
                    "source_row": int(row["source_row"]),
                    "detector_correct": bool(row["correct"]),
                },
            }
        )

    output = Path(output_path)
    write_jsonl(output, cases)
    return cases


def build_cases(config_path: str | Path) -> list[dict[str, Any]]:
    load_json(config_path)
    detector_results = load_json("reports/tables/detector_results.json")
    threshold = float(detector_results["leakage_controlled"]["selected_threshold"])
    return build_cases_from_predictions(
        predictions_path="data/processed/test_predictions_leakage_controlled.csv",
        threshold=threshold,
        model_name="random_forest_leakage_controlled_strict_family_file",
        output_path="data/processed/agent_cases.jsonl",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Select fixed detector outputs for agent evaluation.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    cases = build_cases(args.config)
    print(f"Prepared {len(cases)} fixed agent-evaluation cases.")


if __name__ == "__main__":
    main()
