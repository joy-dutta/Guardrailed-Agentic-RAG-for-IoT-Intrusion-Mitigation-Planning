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
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.model_selection import train_test_split

from .common import load_json, write_json
from .detector import METADATA_COLUMNS, build_model
from .metrics import (
    choose_confidence_threshold,
    classification_metrics,
    routing_metrics,
)
from .split_protocols import assign_attack_type_aware


def area_under_risk_coverage(
    y_true: np.ndarray, y_pred: np.ndarray, probabilities: np.ndarray
) -> float:
    order = np.argsort(-probabilities.max(axis=1), kind="stable")
    errors = (y_pred[order] != y_true[order]).astype(float)
    risk = np.cumsum(errors) / np.arange(1, len(errors) + 1)
    coverage = np.arange(1, len(errors) + 1) / len(errors)
    return float(np.trapezoid(risk, coverage))


def reliability_bins(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    bins: int,
) -> list[dict[str, float | int]]:
    confidence = probabilities.max(axis=1)
    correct = y_pred == y_true
    edges = np.linspace(0.0, 1.0, bins + 1)
    output = []
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:]), start=1):
        mask = (confidence > lower) & (confidence <= upper)
        output.append(
            {
                "bin": index,
                "lower": float(lower),
                "upper": float(upper),
                "count": int(mask.sum()),
                "mean_confidence": float(confidence[mask].mean()) if mask.any() else 0.0,
                "accuracy": float(correct[mask].mean()) if mask.any() else 0.0,
            }
        )
    return output


def nested_calibration_split(
    calibration: pd.DataFrame, fit_fraction: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stratify = calibration["attack_type"].astype(str)
    fit, threshold = train_test_split(
        calibration,
        train_size=fit_fraction,
        random_state=seed,
        stratify=stratify,
    )
    return fit, threshold


def evaluate_method(
    method: str,
    model: Any,
    classes: np.ndarray,
    calibration_fit: pd.DataFrame,
    threshold_validation: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    detector_config: dict[str, Any],
    bins: int,
) -> dict[str, Any]:
    if method == "raw":
        validation_probabilities = model.predict_proba(threshold_validation[features])
        test_probabilities = model.predict_proba(test[features])
        method_classes = classes
    else:
        calibrator = CalibratedClassifierCV(
            estimator=FrozenEstimator(model), method=method
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
    test_predictions = method_classes[np.argmax(test_probabilities, axis=1)]
    threshold, curve = choose_confidence_threshold(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        float(detector_config["target_selective_accuracy"]),
        float(detector_config["minimum_coverage"]),
    )
    validation_routing = routing_metrics(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        threshold,
    )
    validation_metrics = classification_metrics(
        threshold_validation["family"].to_numpy(),
        validation_predictions,
        validation_probabilities,
        method_classes,
    )
    test_routing = routing_metrics(
        test["family"].to_numpy(),
        test_predictions,
        test_probabilities,
        threshold,
    )
    metrics = classification_metrics(
        test["family"].to_numpy(),
        test_predictions,
        test_probabilities,
        method_classes,
    )
    return {
        "method": method,
        "threshold": threshold,
        "threshold_validation": validation_routing,
        "threshold_validation_metrics": validation_metrics,
        "test": metrics,
        "test_routing": test_routing,
        "aurc": area_under_risk_coverage(
            test["family"].to_numpy(), test_predictions, test_probabilities
        ),
        "risk_coverage_curve": curve,
        "reliability_bins": reliability_bins(
            test["family"].to_numpy(), test_predictions, test_probabilities, bins
        ),
    }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "macro_f1": lambda row: row["test"]["macro_f1"],
        "ece": lambda row: row["test"]["ece_15_bin"],
        "brier": lambda row: row["test"]["multiclass_brier"],
        "nll": lambda row: row["test"]["log_loss"],
        "aurc": lambda row: row["aurc"],
        "coverage": lambda row: row["test_routing"]["coverage"],
        "selective_accuracy": lambda row: row["test_routing"]["selective_accuracy"],
    }
    output: dict[str, Any] = {}
    for method in sorted({row["method"] for row in runs}):
        rows = [row for row in runs if row["method"] == method]
        output[method] = {}
        for name, getter in fields.items():
            values = np.asarray([getter(row) for row in rows], dtype=float)
            output[method][name] = {
                "mean": float(values.mean()),
                "sample_std": float(values.std(ddof=1)),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
    return output


def validation_selected_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for seed in sorted({row["seed"] for row in runs}):
        candidates = [row for row in runs if row["seed"] == seed]
        winner = min(
            candidates,
            key=lambda row: (
                row["threshold_validation_metrics"]["ece_15_bin"],
                row["threshold_validation_metrics"]["multiclass_brier"],
            ),
        )
        selected.append(winner)
    return selected


def plot_results(output: dict[str, Any]) -> None:
    target = Path("reports/comprehensive_evaluation/figures")
    target.mkdir(parents=True, exist_ok=True)
    methods = list(output["summary"])
    labels = [method.title() for method in methods]

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8))
    metrics = [("ece", "ECE"), ("brier", "Brier"), ("nll", "NLL")]
    x = np.arange(len(metrics))
    width = 0.24
    for index, method in enumerate(methods):
        axes[0].bar(
            x + (index - (len(methods) - 1) / 2) * width,
            [output["summary"][method][key]["mean"] for key, _ in metrics],
            width,
            label=method.title(),
        )
    axes[0].set_xticks(x, [label for _, label in metrics])
    axes[0].set_ylabel("Five-seed mean (lower is better)")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)

    selected_seed = output["seeds"][0]
    for method, label in zip(methods, labels):
        row = next(
            item
            for item in output["runs"]
            if item["seed"] == selected_seed and item["method"] == method
        )
        bins = [item for item in row["reliability_bins"] if item["count"]]
        axes[1].plot(
            [item["mean_confidence"] for item in bins],
            [item["accuracy"] for item in bins],
            marker="o",
            linewidth=1.5,
            label=label,
        )
    axes[1].plot([0, 1], [0, 1], "--", color="#555555", linewidth=1)
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(0, 1)
    axes[1].set_xlabel("Mean score")
    axes[1].set_ylabel("Observed accuracy")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(target / "calibration_comparison.pdf", bbox_inches="tight")
    plt.close(fig)


def persist_selected_seed_predictions(
    frame: pd.DataFrame,
    features: list[str],
    base: dict[str, Any],
    extension: dict[str, Any],
    seed: int,
    method: str,
) -> dict[str, Any]:
    working = frame.copy()
    working["split"], _ = assign_attack_type_aware(working, seed)
    train = working.loc[working["split"] == "train"]
    calibration = working.loc[working["split"] == "calibration"]
    test = working.loc[working["split"] == "test"].copy()
    calibration_fit, threshold_validation = nested_calibration_split(
        calibration, float(extension["calibration"]["fit_fraction"]), seed
    )
    model = build_model(base["detector"], seed)
    model.fit(train[features], train["family"])
    classes = np.asarray(model.classes_)
    if method == "raw":
        validation_probabilities = model.predict_proba(threshold_validation[features])
        test_probabilities = model.predict_proba(test[features])
        method_classes = classes
    else:
        calibrator = CalibratedClassifierCV(
            estimator=FrozenEstimator(model), method=method
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
        float(base["detector"]["target_selective_accuracy"]),
        float(base["detector"]["minimum_coverage"]),
    )
    predictions = method_classes[np.argmax(test_probabilities, axis=1)]
    test["predicted_family"] = predictions
    test["calibrated_confidence"] = test_probabilities.max(axis=1)
    test["correct"] = test["family"].to_numpy() == predictions
    for index, label in enumerate(method_classes):
        test[f"probability_{label}"] = test_probabilities[:, index]
    output_path = extension["planning"]["predictions_path"]
    test.to_csv(output_path, index=False)
    return {
        "seed": seed,
        "method": method,
        "threshold": threshold,
        "rows": len(test),
        "path": output_path,
    }


def run_calibration_benchmark(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    calibration_config = extension["calibration"]
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    features = [column for column in frame.columns if column not in METADATA_COLUMNS]
    features = [
        column
        for column in features
        if column not in set(base["dataset"]["leakage_control_drop"])
    ]
    runs = []
    seeds = [int(seed) for seed in base["detector_repeat_seeds"]]
    for seed in seeds:
        working = frame.copy()
        working["split"], _ = assign_attack_type_aware(working, seed)
        train = working.loc[working["split"] == "train"]
        calibration = working.loc[working["split"] == "calibration"]
        test = working.loc[working["split"] == "test"]
        calibration_fit, threshold_validation = nested_calibration_split(
            calibration, float(calibration_config["fit_fraction"]), seed
        )
        model = build_model(base["detector"], seed)
        model.fit(train[features], train["family"])
        classes = np.asarray(model.classes_)
        for method in calibration_config["methods"]:
            result = evaluate_method(
                str(method),
                model,
                classes,
                calibration_fit,
                threshold_validation,
                test,
                features,
                base["detector"],
                int(calibration_config["reliability_bins"]),
            )
            result.update(
                {
                    "seed": seed,
                    "train_rows": len(train),
                    "calibration_fit_rows": len(calibration_fit),
                    "threshold_validation_rows": len(threshold_validation),
                    "test_rows": len(test),
                }
            )
            runs.append(result)
        del working, train, calibration, test, calibration_fit, threshold_validation, model
        gc.collect()

    selected = validation_selected_runs(runs)
    output = {
        "protocol": "attack_type_aware_with_nested_calibration_partition",
        "seeds": seeds,
        "methods": calibration_config["methods"],
        "runs": runs,
        "summary": summarize_runs(runs),
        "validation_selected_method_by_seed": {
            str(row["seed"]): row["method"] for row in selected
        },
        "validation_selected_test_summary": summarize_runs(selected),
        "interpretation_guardrail": (
            "Calibration methods are compared without using final test labels for fitting, "
            "method selection, or threshold selection. For each seed, the method with the "
            "lowest threshold-validation ECE is selected, with Brier score as a tie-breaker. "
            "Final test results are evaluation only."
        ),
    }
    selected_seed = seeds[0]
    selected_method = output["validation_selected_method_by_seed"][str(selected_seed)]
    output["planning_prediction_artifact"] = persist_selected_seed_predictions(
        frame, features, base, extension, selected_seed, selected_method
    )
    write_json("reports/comprehensive_evaluation/tables/calibration_benchmark.json", output)
    rows = []
    for run in runs:
        rows.append(
            {
                "seed": run["seed"],
                "method": run["method"],
                "macro_f1": run["test"]["macro_f1"],
                "ece": run["test"]["ece_15_bin"],
                "brier": run["test"]["multiclass_brier"],
                "nll": run["test"]["log_loss"],
                "aurc": run["aurc"],
                "threshold": run["threshold"],
                "coverage": run["test_routing"]["coverage"],
                "selective_accuracy": run["test_routing"]["selective_accuracy"],
            }
        )
    table_path = Path("reports/comprehensive_evaluation/tables/calibration_benchmark.csv")
    table_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(table_path, index=False)
    plot_results(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare raw, sigmoid, and isotonic confidence scores."
    )
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    output = run_calibration_benchmark(args.config)
    for method, metrics in output["summary"].items():
        print(
            f"{method}: ECE={metrics['ece']['mean']:.4f}, "
            f"AURC={metrics['aurc']['mean']:.4f}, "
            f"coverage={metrics['coverage']['mean']:.3f}, "
            f"selective_accuracy={metrics['selective_accuracy']['mean']:.3f}"
        )


if __name__ == "__main__":
    main()
