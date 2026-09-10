from __future__ import annotations

import argparse
import gc
import os
import time
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
from .detector_alternatives import build_estimators
from .journal_calibration import area_under_risk_coverage, nested_calibration_split
from .metrics import choose_confidence_threshold, classification_metrics, routing_metrics
from .split_protocols import assign_attack_type_aware


def evaluate_model(
    estimator: Any,
    method: str,
    train: pd.DataFrame,
    calibration_fit: pd.DataFrame,
    threshold_validation: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    detector_config: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    estimator.fit(train[features], train["family"])
    fit_seconds = time.perf_counter() - started
    classes = np.asarray(estimator.classes_)
    if method == "raw":
        validation_probabilities = estimator.predict_proba(
            threshold_validation[features]
        )
        test_probabilities = estimator.predict_proba(test[features])
        method_classes = classes
    else:
        calibrator = CalibratedClassifierCV(
            estimator=FrozenEstimator(estimator), method=method
        )
        calibrator.fit(calibration_fit[features], calibration_fit["family"])
        validation_probabilities = calibrator.predict_proba(
            threshold_validation[features]
        )
        test_probabilities = calibrator.predict_proba(test[features])
        method_classes = np.asarray(calibrator.classes_)
    validation_predictions = method_classes[
        np.argmax(validation_probabilities, axis=1)
    ]
    threshold, _ = choose_confidence_threshold(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        float(detector_config["target_selective_accuracy"]),
        float(detector_config["minimum_coverage"]),
    )
    predictions = method_classes[np.argmax(test_probabilities, axis=1)]
    metrics = classification_metrics(
        test["family"].to_numpy(), predictions, test_probabilities, method_classes
    )
    routing = routing_metrics(
        test["family"].to_numpy(), predictions, test_probabilities, threshold
    )
    return {
        "calibration_method": method,
        "fit_seconds": fit_seconds,
        "threshold": threshold,
        "metrics": metrics,
        "routing": routing,
        "aurc": area_under_risk_coverage(
            test["family"].to_numpy(), predictions, test_probabilities
        ),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    getters = {
        "macro_f1": lambda row: row["metrics"]["macro_f1"],
        "balanced_accuracy": lambda row: row["metrics"]["balanced_accuracy"],
        "ece": lambda row: row["metrics"]["ece_15_bin"],
        "brier": lambda row: row["metrics"]["multiclass_brier"],
        "nll": lambda row: row["metrics"]["log_loss"],
        "aurc": lambda row: row["aurc"],
        "coverage": lambda row: row["routing"]["coverage"],
        "selective_accuracy": lambda row: row["routing"]["selective_accuracy"],
    }
    output = {}
    for model in sorted({row["model"] for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        output[model] = {}
        for metric, getter in getters.items():
            values = np.asarray([getter(row) for row in model_rows], dtype=float)
            output[model][metric] = {
                "mean": float(values.mean()),
                "sample_std": float(values.std(ddof=1)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
    return output


def run_detector_sensitivity(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    calibration = load_json(
        "reports/comprehensive_evaluation/tables/calibration_benchmark.json"
    )
    method_by_seed = calibration["validation_selected_method_by_seed"]
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    features = [column for column in frame.columns if column not in METADATA_COLUMNS]
    features = [
        column
        for column in features
        if column not in set(base["dataset"]["leakage_control_drop"])
    ]
    rows = []
    for seed in [int(value) for value in base["detector_repeat_seeds"]]:
        working = frame.copy()
        working["split"], _ = assign_attack_type_aware(working, seed)
        train = working.loc[working["split"] == "train"]
        calibration_rows = working.loc[working["split"] == "calibration"]
        test = working.loc[working["split"] == "test"]
        calibration_fit, threshold_validation = nested_calibration_split(
            calibration_rows, float(extension["calibration"]["fit_fraction"]), seed
        )
        estimators = {
            "random_forest": build_model(base["detector"], seed),
            **build_estimators(base, seed),
        }
        for model_name, estimator in estimators.items():
            result = evaluate_model(
                estimator,
                str(method_by_seed[str(seed)]),
                train,
                calibration_fit,
                threshold_validation,
                test,
                features,
                base["detector"],
            )
            result.update({"seed": seed, "model": model_name})
            rows.append(result)
            del estimator
            gc.collect()
        del working, train, calibration_rows, test, calibration_fit, threshold_validation
        gc.collect()

    output = {
        "protocol": "attack_type_aware_nested_calibration",
        "runs": rows,
        "summary": summarize(rows),
        "interpretation_guardrail": (
            "The three predeclared detector families are sensitivity checks. The journal "
            "claim concerns guarded planning and does not claim a new detector."
        ),
    }
    write_json(
        "reports/comprehensive_evaluation/tables/detector_model_sensitivity.json",
        output,
    )
    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "seed": row["seed"],
                "model": row["model"],
                "calibration_method": row["calibration_method"],
                "macro_f1": row["metrics"]["macro_f1"],
                "balanced_accuracy": row["metrics"]["balanced_accuracy"],
                "ece": row["metrics"]["ece_15_bin"],
                "brier": row["metrics"]["multiclass_brier"],
                "nll": row["metrics"]["log_loss"],
                "aurc": row["aurc"],
                "threshold": row["threshold"],
                "coverage": row["routing"]["coverage"],
                "selective_accuracy": row["routing"]["selective_accuracy"],
                "fit_seconds": row["fit_seconds"],
            }
        )
    pd.DataFrame(table_rows).to_csv(
        "reports/comprehensive_evaluation/tables/detector_model_sensitivity.csv",
        index=False,
    )

    figure_dir = Path("reports/comprehensive_evaluation/figures")
    figure_dir.mkdir(parents=True, exist_ok=True)
    models = list(output["summary"])
    labels = [model.replace("_", " ").title() for model in models]
    x = np.arange(len(models))
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.8))
    for axis, metric, ylabel in [
        (axes[0], "macro_f1", "Macro-F1"),
        (axes[1], "selective_accuracy", "Selective accuracy"),
    ]:
        means = [output["summary"][model][metric]["mean"] for model in models]
        standard = [
            output["summary"][model][metric]["sample_std"] for model in models
        ]
        axis.bar(x, means, yerr=standard, capsize=4, color=["#287271", "#E07A5F", "#6C6B7B"])
        axis.set_xticks(x, labels, rotation=12)
        axis.set_ylim(0, 1.02)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "detector_model_sensitivity.pdf", bbox_inches="tight")
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repeat three detector families under the journal protocol."
    )
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    output = run_detector_sensitivity(args.config)
    for model, metrics in output["summary"].items():
        print(
            f"{model}: macro-F1={metrics['macro_f1']['mean']:.4f}, "
            f"selective_accuracy={metrics['selective_accuracy']['mean']:.4f}"
        )


if __name__ == "__main__":
    main()
