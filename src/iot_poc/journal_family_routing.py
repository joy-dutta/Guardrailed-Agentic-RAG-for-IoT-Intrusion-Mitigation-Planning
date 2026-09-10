from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

from .common import load_json, write_json
from .detector import METADATA_COLUMNS, build_model
from .family_routing import apply_family_thresholds, choose_family_thresholds
from .journal_calibration import nested_calibration_split
from .metrics import choose_confidence_threshold, routing_metrics
from .split_protocols import assign_attack_type_aware


def fit_probabilities(
    method: str,
    model: Any,
    calibration_fit: pd.DataFrame,
    threshold_validation: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if method == "raw":
        return (
            np.asarray(model.classes_),
            model.predict_proba(threshold_validation[features]),
            model.predict_proba(test[features]),
        )
    calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(model), method=method
    )
    calibrator.fit(calibration_fit[features], calibration_fit["family"])
    return (
        np.asarray(calibrator.classes_),
        calibrator.predict_proba(threshold_validation[features]),
        calibrator.predict_proba(test[features]),
    )


def evaluate_seed(
    frame: pd.DataFrame,
    base: dict[str, Any],
    extension: dict[str, Any],
    seed: int,
    method: str,
) -> dict[str, Any]:
    working = frame.copy()
    working["split"], _ = assign_attack_type_aware(working, seed)
    features = [
        column
        for column in working.columns
        if column not in METADATA_COLUMNS
        and column not in set(base["dataset"]["leakage_control_drop"])
    ]
    train = working.loc[working["split"] == "train"]
    calibration = working.loc[working["split"] == "calibration"]
    test = working.loc[working["split"] == "test"]
    calibration_fit, threshold_validation = nested_calibration_split(
        calibration, float(extension["calibration"]["fit_fraction"]), seed
    )
    model = build_model(base["detector"], seed)
    model.fit(train[features], train["family"])
    classes, validation_probabilities, test_probabilities = fit_probabilities(
        method,
        model,
        calibration_fit,
        threshold_validation,
        test,
        features,
    )
    validation_predictions = classes[np.argmax(validation_probabilities, axis=1)]
    test_predictions = classes[np.argmax(test_probabilities, axis=1)]

    global_threshold, _ = choose_confidence_threshold(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        float(base["family_routing"]["target_selective_accuracy"]),
        float(base["detector"]["minimum_coverage"]),
    )
    global_result = routing_metrics(
        test["family"].to_numpy(),
        test_predictions,
        test_probabilities,
        global_threshold,
    )
    family_thresholds, calibration_audit = choose_family_thresholds(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        classes,
        float(base["family_routing"]["target_selective_accuracy"]),
        float(base["family_routing"]["minimum_predicted_family_coverage"]),
    )
    family_result = apply_family_thresholds(
        test["family"].to_numpy(),
        test_predictions,
        test_probabilities,
        family_thresholds,
    )
    result = {
        "seed": seed,
        "calibration_method": method,
        "calibration_fit_rows": len(calibration_fit),
        "threshold_validation_rows": len(threshold_validation),
        "test_rows": len(test),
        "global": global_result,
        "family_specific": family_result,
        "family_thresholds": family_thresholds,
        "family_threshold_selection": calibration_audit,
        "families_meeting_target_on_validation": int(
            sum(item["status"] == "target_met" for item in calibration_audit.values())
        ),
    }
    del working, train, calibration, test, calibration_fit, threshold_validation, model
    gc.collect()
    return result


def summarize(runs: list[dict[str, Any]], key: str) -> dict[str, Any]:
    fields = {
        "coverage": "coverage",
        "selective_accuracy": "selective_accuracy",
        "wrong_covered_rows": (
            "wrong_automatic_decisions" if key == "global" else "wrong_covered_rows"
        ),
    }
    output = {}
    for output_name, source_name in fields.items():
        values = np.asarray([run[key][source_name] for run in runs], dtype=float)
        output[output_name] = {
            "mean": float(values.mean()),
            "sample_std": float(values.std(ddof=1)),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
        }
    return output


def plot_results(output: dict[str, Any]) -> None:
    runs = output["runs"]
    x = np.arange(len(runs))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8))
    axes[0].bar(
        x - width / 2,
        [run["global"]["coverage"] for run in runs],
        width,
        label="Global",
        color="#6C757D",
    )
    axes[0].bar(
        x + width / 2,
        [run["family_specific"]["coverage"] for run in runs],
        width,
        label="Family-aware",
        color="#287271",
    )
    axes[0].set_xticks(x, [str(run["seed"]) for run in runs], rotation=20)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Fraction eligible for planning")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y", alpha=0.25)

    first = runs[0]["family_specific"]["by_predicted_family"]
    families = list(first)
    axes[1].bar(
        families,
        [first[family]["selective_accuracy"] for family in families],
        color="#E9C46A",
    )
    axes[1].axhline(0.95, color="#333333", linestyle="--", linewidth=1)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Accuracy among retained predictions")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    target = Path("reports/comprehensive_evaluation/figures")
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / "nested_family_aware_routing.pdf", bbox_inches="tight")
    plt.close(fig)


def run_family_routing(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    calibration = load_json(
        "reports/comprehensive_evaluation/tables/calibration_benchmark.json"
    )
    method_by_seed = calibration["validation_selected_method_by_seed"]
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    runs = [
        evaluate_seed(frame, base, extension, int(seed), method_by_seed[str(seed)])
        for seed in base["detector_repeat_seeds"]
    ]
    output = {
        "protocol": "attack_type_aware_nested_calibration_and_threshold_selection",
        "target_selective_accuracy": base["family_routing"][
            "target_selective_accuracy"
        ],
        "minimum_predicted_family_coverage": base["family_routing"][
            "minimum_predicted_family_coverage"
        ],
        "runs": runs,
        "summary": {
            "global": summarize(runs, "global"),
            "family_specific": summarize(runs, "family_specific"),
            "mean_families_meeting_target_on_validation": float(
                np.mean([run["families_meeting_target_on_validation"] for run in runs])
            ),
        },
        "interpretation_guardrail": (
            "Thresholds are selected using only the held-out threshold-validation half. "
            "A predicted family is failed closed when no threshold meets the target and "
            "minimum coverage there. Final test labels are used only for evaluation."
        ),
    }
    write_json(
        "reports/comprehensive_evaluation/tables/nested_family_aware_routing.json",
        output,
    )
    plot_results(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare global and predicted-family routing without test leakage."
    )
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    result = run_family_routing(args.config)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
