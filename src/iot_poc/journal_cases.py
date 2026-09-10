from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .alerts import OBSERVATION_FEATURES
from .common import load_json, stable_seed, write_json, write_jsonl


def route_for_row(row: pd.Series, threshold: float) -> str:
    if float(row["calibrated_confidence"]) < threshold:
        return "escalate"
    return "monitor" if str(row["predicted_family"]) == "Benign" else "plan"


def selection_stratum(row: pd.Series, threshold: float) -> str:
    qualified = float(row["calibrated_confidence"]) >= threshold
    correctness = "correct" if bool(row["correct"]) else "error"
    return f"{correctness}_{'qualified' if qualified else 'escalated'}"


def select_balanced_cases(
    predictions: pd.DataFrame,
    threshold: float,
    cases_per_family: int,
    seed: int,
) -> pd.DataFrame:
    frame = predictions.copy()
    frame["correct"] = frame["correct"].astype(str).str.lower().eq("true")
    frame["selection_stratum"] = frame.apply(
        lambda row: selection_stratum(row, threshold), axis=1
    )
    selected = []
    strata = [
        "correct_qualified",
        "correct_escalated",
        "error_qualified",
        "error_escalated",
    ]
    target_per_stratum = cases_per_family // len(strata)

    for family, family_rows in frame.groupby("family", sort=True):
        chosen_indices: list[int] = []
        for stratum in strata:
            candidates = family_rows.loc[
                family_rows["selection_stratum"] == stratum
            ]
            take = min(target_per_stratum, len(candidates))
            if take:
                chosen_indices.extend(
                    candidates.sample(
                        n=take,
                        random_state=stable_seed(f"{family}:{stratum}", seed),
                    ).index.tolist()
                )

        remaining = family_rows.drop(index=chosen_indices)
        shortfall = cases_per_family - len(chosen_indices)
        if shortfall:
            if len(remaining) < shortfall:
                raise ValueError(f"Not enough rows to select {cases_per_family} for {family}.")
            chosen_indices.extend(
                remaining.sample(
                    n=shortfall,
                    random_state=stable_seed(f"{family}:fill", seed),
                ).index.tolist()
            )
        selected.append(frame.loc[chosen_indices])

    output = pd.concat(selected, ignore_index=False)
    if output.index.duplicated().any():
        raise RuntimeError("The expanded planning sample contains duplicate source rows.")
    return output.sort_values(
        ["family", "selection_stratum", "calibrated_confidence"],
        ascending=[True, True, False],
    )


def row_to_case(row: pd.Series, case_id: str, threshold: float) -> dict[str, Any]:
    observations = {
        feature: float(row[feature])
        for feature in OBSERVATION_FEATURES
        if feature in row and np.isfinite(row[feature])
    }
    predicted = str(row["predicted_family"])
    return {
        "case_id": case_id,
        "selection_reason": str(row["selection_stratum"]),
        "alert": {
            "schema": "iot.security.alert.v1",
            "alert_id": case_id,
            "detector": {
                "model": "random_forest_leakage_controlled_attack_type_aware",
                "predicted_family": predicted,
                "calibrated_confidence": float(row["calibrated_confidence"]),
                "confidence_threshold": threshold,
            },
            "routing_decision": route_for_row(row, threshold),
            "gateway_scope": f"gateway/observed-flow-profile/{case_id}",
            "observations": observations,
            "limitations": [
                "The CSV features do not provide a validated device identifier.",
                "The output is mitigation intent only and cannot execute an action.",
            ],
        },
        "evaluation": {
            "true_family": str(row["family"]),
            "attack_type": str(row["attack_type"]),
            "source_file": str(row["source_file"]),
            "source_row": int(row["source_row"]),
            "detector_correct": bool(row["correct"]),
            "selection_stratum": str(row["selection_stratum"]),
        },
    }


def build_journal_cases(config_path: str | Path) -> list[dict[str, Any]]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    planning = extension["planning"]
    calibration = load_json(
        "reports/comprehensive_evaluation/tables/calibration_benchmark.json"
    )
    artifact = calibration["planning_prediction_artifact"]
    threshold = float(artifact["threshold"])
    predictions = pd.read_csv(planning["predictions_path"])
    selected = select_balanced_cases(
        predictions,
        threshold,
        int(planning["cases_per_true_family"]),
        int(base["seed"]),
    )
    cases = [
        row_to_case(row, f"ieee-access-{index:04d}", threshold)
        for index, (_, row) in enumerate(selected.iterrows(), start=1)
    ]
    write_jsonl(planning["cases_path"], cases)

    audit = {
        "seed": int(base["seed"]),
        "calibration_method": artifact["method"],
        "threshold": threshold,
        "cases": len(cases),
        "cases_per_true_family": {
            str(key): int(value)
            for key, value in selected["family"].value_counts().sort_index().items()
        },
        "selection_strata": {
            str(key): int(value)
            for key, value in selected["selection_stratum"].value_counts().sort_index().items()
        },
        "detector_errors": int((~selected["correct"]).sum()),
        "confidence_qualified": int(
            (selected["calibrated_confidence"] >= threshold).sum()
        ),
        "source_files": int(selected["source_file"].nunique()),
        "attack_types": int(selected["attack_type"].nunique()),
        "sampling_note": (
            "The sample is balanced by true family and deliberately represents correct, "
            "incorrect, confidence-qualified, and escalated detector outputs. It is an "
            "uncertainty stress sample, not a prevalence estimate for CICIoT2023."
        ),
    }
    write_json("reports/comprehensive_evaluation/tables/planning_case_audit.json", audit)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the expanded IEEE Access planning sample."
    )
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    cases = build_journal_cases(args.config)
    print(f"Prepared {len(cases)} expanded planning cases.")


if __name__ == "__main__":
    main()
