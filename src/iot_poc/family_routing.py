from __future__ import annotations

import argparse
import gc
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import load_json, write_json
from .detector import METADATA_COLUMNS, evaluate_feature_set
from .split_protocols import assign_attack_type_aware


def wilson_lower_bound(correct: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    proportion = correct / total
    denominator = 1.0 + z * z / total
    centre = proportion + z * z / (2.0 * total)
    margin = z * np.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    )
    return float((centre - margin) / denominator)


def choose_family_thresholds(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    classes: np.ndarray,
    target_accuracy: float,
    minimum_coverage: float,
) -> tuple[dict[str, float], dict[str, Any]]:
    confidence = probabilities.max(axis=1)
    thresholds: dict[str, float] = {}
    audit: dict[str, Any] = {}
    for family in classes:
        family = str(family)
        family_mask = y_pred == family
        family_total = int(family_mask.sum())
        candidates = []
        for threshold in np.linspace(0.0, 0.99, 100):
            covered = family_mask & (confidence >= threshold)
            count = int(covered.sum())
            coverage = count / family_total if family_total else 0.0
            accuracy = float((y_pred[covered] == y_true[covered]).mean()) if count else 1.0
            if coverage >= minimum_coverage and accuracy >= target_accuracy:
                candidates.append((float(round(threshold, 2)), coverage, accuracy, count))
        if candidates:
            threshold, coverage, accuracy, count = min(candidates, key=lambda item: item[0])
            status = "target_met"
        else:
            threshold, coverage, accuracy, count = 1.01, 0.0, 1.0, 0
            status = "fail_closed_no_calibration_threshold_met_target"
        thresholds[family] = threshold
        audit[family] = {
            "predicted_rows": family_total,
            "selected_threshold": threshold,
            "coverage_within_predicted_family": coverage,
            "selective_accuracy": accuracy,
            "covered_rows": count,
            "status": status,
        }
    return thresholds, audit


def apply_family_thresholds(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    confidence = probabilities.max(axis=1)
    covered = np.asarray(
        [score >= thresholds[str(prediction)] for score, prediction in zip(confidence, y_pred)]
    )
    correct = y_true == y_pred

    by_predicted = {}
    for family in sorted(thresholds):
        group = y_pred == family
        selected = group & covered
        count = int(selected.sum())
        right = int((selected & correct).sum())
        by_predicted[family] = {
            "predicted_rows": int(group.sum()),
            "covered_rows": count,
            "coverage_within_predicted_family": float(count / group.sum()) if group.any() else 0.0,
            "selective_accuracy": float(right / count) if count else 1.0,
            "wilson_95_lower_bound": wilson_lower_bound(right, count),
            "wrong_covered_rows": int((selected & ~correct).sum()),
            "threshold": thresholds[family],
        }

    by_true = {}
    for family in sorted(set(map(str, y_true))):
        group = y_true == family
        selected = group & covered
        count = int(selected.sum())
        by_true[family] = {
            "test_rows": int(group.sum()),
            "covered_rows": count,
            "coverage_within_true_family": float(count / group.sum()),
            "selective_accuracy": float(correct[selected].mean()) if count else 1.0,
            "wrong_covered_rows": int((selected & ~correct).sum()),
        }

    covered_count = int(covered.sum())
    right_count = int((covered & correct).sum())
    return {
        "coverage": float(covered.mean()),
        "selective_accuracy": float(right_count / covered_count) if covered_count else 1.0,
        "wilson_95_lower_bound": wilson_lower_bound(right_count, covered_count),
        "covered_rows": covered_count,
        "escalated_rows": int((~covered).sum()),
        "wrong_covered_rows": int((covered & ~correct).sum()),
        "wrong_covered_rate_all_rows": float((covered & ~correct).mean()),
        "by_predicted_family": by_predicted,
        "by_true_family": by_true,
    }


def global_threshold_metrics(predictions: pd.DataFrame, threshold: float) -> dict[str, Any]:
    covered = predictions["calibrated_confidence"].to_numpy() >= threshold
    correct = predictions["correct"].astype(bool).to_numpy()
    return {
        "threshold": threshold,
        "coverage": float(covered.mean()),
        "selective_accuracy": float(correct[covered].mean()),
        "covered_rows": int(covered.sum()),
        "escalated_rows": int((~covered).sum()),
        "wrong_covered_rows": int((covered & ~correct).sum()),
    }


def evaluate_one_seed(frame: pd.DataFrame, config: dict[str, Any], seed: int) -> dict[str, Any]:
    working = frame.copy()
    working["split"], _ = assign_attack_type_aware(working, seed)
    excluded = METADATA_COLUMNS
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    feature_columns = [
        column for column in working.columns if column not in excluded and column not in leakage_drop
    ]
    detector_result, test_predictions, model, calibrator = evaluate_feature_set(
        working, feature_columns, "leakage_controlled", config["detector"], seed
    )
    calibration = working.loc[working["split"] == "calibration"]
    classes = np.asarray(calibrator.classes_)
    calibration_probabilities = calibrator.predict_proba(calibration[feature_columns])
    calibration_predictions = classes[np.argmax(calibration_probabilities, axis=1)]
    routing_config = config["family_routing"]
    thresholds, calibration_audit = choose_family_thresholds(
        calibration["family"].to_numpy(),
        calibration_predictions,
        calibration_probabilities,
        classes,
        float(routing_config["target_selective_accuracy"]),
        float(routing_config["minimum_predicted_family_coverage"]),
    )
    test_probabilities = test_predictions[
        [f"probability_{family}" for family in classes]
    ].to_numpy()
    family_result = apply_family_thresholds(
        test_predictions["family"].to_numpy(),
        test_predictions["predicted_family"].to_numpy(),
        test_probabilities,
        thresholds,
    )
    compact = {
        "seed": seed,
        "thresholds": thresholds,
        "calibration": calibration_audit,
        "test": family_result,
        "global_threshold_test": detector_result["confidence_aware"],
    }
    del working, detector_result, test_predictions, model, calibrator
    gc.collect()
    return compact


def plot_results(output: dict[str, Any]) -> None:
    runs = output["runs"]
    x = np.arange(len(runs))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.bar(
        x - width / 2,
        [run["global_threshold_test"]["coverage"] for run in runs],
        width,
        label="Global threshold",
        color="#6C757D",
    )
    ax.bar(
        x + width / 2,
        [run["test"]["coverage"] for run in runs],
        width,
        label="Family-specific thresholds",
        color="#287271",
    )
    ax.set_xticks(x, [str(run["seed"]) for run in runs], rotation=20)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Fraction eligible for planning")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/family_specific_routing_coverage.png", dpi=240)
    plt.close(fig)

    selected = runs[0]["test"]["by_predicted_family"]
    families = list(selected)
    fig, ax = plt.subplots(figsize=(8.2, 4.5))
    ax.bar(
        families,
        [selected[family]["selective_accuracy"] for family in families],
        color="#E9C46A",
    )
    ax.axhline(0.95, color="#333333", linestyle="--", linewidth=1)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Accuracy among retained predictions")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/family_specific_routing_accuracy.png", dpi=240)
    plt.close(fig)


def run_family_routing(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    runs = [
        evaluate_one_seed(frame, config, int(seed))
        for seed in config["detector_repeat_seeds"]
    ]
    output = {
        "method": "predicted-family-specific thresholds selected on calibration data only",
        "prepared_sample_held_fixed": True,
        "target_selective_accuracy": config["family_routing"]["target_selective_accuracy"],
        "minimum_predicted_family_coverage": config["family_routing"][
            "minimum_predicted_family_coverage"
        ],
        "runs": runs,
        "summary": {
            "global_threshold": {
                "mean_coverage": float(
                    np.mean([run["global_threshold_test"]["coverage"] for run in runs])
                ),
                "mean_selective_accuracy": float(
                    np.mean(
                        [run["global_threshold_test"]["selective_accuracy"] for run in runs]
                    )
                ),
            },
            "family_specific": {
                "mean_coverage": float(np.mean([run["test"]["coverage"] for run in runs])),
                "mean_selective_accuracy": float(
                    np.mean([run["test"]["selective_accuracy"] for run in runs])
                ),
                "mean_wrong_covered_rows": float(
                    np.mean([run["test"]["wrong_covered_rows"] for run in runs])
                ),
            },
        },
    }
    write_json("reports/tables/family_specific_routing.json", output)
    plot_results(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate family-specific confidence routing.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    result = run_family_routing(args.config)
    print(result["summary"])


if __name__ == "__main__":
    main()
