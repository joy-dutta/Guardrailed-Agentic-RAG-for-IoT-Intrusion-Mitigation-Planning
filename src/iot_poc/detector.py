from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import joblib
os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .common import load_json, write_json
from .metrics import (
    choose_confidence_threshold,
    classification_metrics,
    routing_metrics,
)


METADATA_COLUMNS = {"source_row", "source_file", "attack_type", "family", "split"}


def build_model(config: dict[str, Any], seed: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=int(config["n_estimators"]),
                    max_depth=int(config["max_depth"]),
                    min_samples_leaf=int(config["min_samples_leaf"]),
                    class_weight="balanced_subsample",
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )


def evaluate_feature_set(
    frame: pd.DataFrame,
    feature_columns: list[str],
    feature_set_name: str,
    config: dict[str, Any],
    seed: int,
) -> tuple[dict[str, Any], pd.DataFrame, Any, Any]:
    train = frame.loc[frame["split"] == "train"]
    calibration = frame.loc[frame["split"] == "calibration"]
    test = frame.loc[frame["split"] == "test"]

    model = build_model(config, seed)
    model.fit(train[feature_columns], train["family"])
    classes = np.asarray(model.classes_)

    calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(model),
        method=str(config["calibration_method"]),
    )
    calibrator.fit(calibration[feature_columns], calibration["family"])

    base_probabilities = model.predict_proba(test[feature_columns])
    base_predictions = classes[np.argmax(base_probabilities, axis=1)]
    calibrated_probabilities = calibrator.predict_proba(test[feature_columns])
    calibrated_predictions = classes[np.argmax(calibrated_probabilities, axis=1)]
    y_test = test["family"].to_numpy()

    calibration_probabilities = calibrator.predict_proba(calibration[feature_columns])
    calibration_predictions = classes[np.argmax(calibration_probabilities, axis=1)]
    threshold, risk_coverage_curve = choose_confidence_threshold(
        calibration["family"].to_numpy(),
        calibration_predictions,
        calibration_probabilities,
        target_accuracy=float(config["target_selective_accuracy"]),
        minimum_coverage=float(config["minimum_coverage"]),
    )

    result = {
        "feature_set": feature_set_name,
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "rows": {
            "train": len(train),
            "calibration": len(calibration),
            "test": len(test),
        },
        "uncalibrated": classification_metrics(
            y_test, base_predictions, base_probabilities, classes
        ),
        "calibrated": classification_metrics(
            y_test, calibrated_predictions, calibrated_probabilities, classes
        ),
        "selected_threshold": threshold,
        "always_automatic": routing_metrics(
            y_test, calibrated_predictions, calibrated_probabilities, threshold=0.0
        ),
        "confidence_aware": routing_metrics(
            y_test, calibrated_predictions, calibrated_probabilities, threshold=threshold
        ),
        "risk_coverage_curve": risk_coverage_curve,
    }

    classifier = model.named_steps["classifier"]
    result["feature_importance"] = [
        {"feature": feature, "importance": float(importance)}
        for feature, importance in sorted(
            zip(feature_columns, classifier.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    metadata_columns = [
        column
        for column in ["source_row", "source_file", "attack_type", "family", "split"]
        if column in test.columns
    ]
    predictions = test[metadata_columns + feature_columns].copy()
    predictions["predicted_family"] = calibrated_predictions
    predictions["calibrated_confidence"] = calibrated_probabilities.max(axis=1)
    predictions["uncalibrated_confidence"] = base_probabilities.max(axis=1)
    predictions["correct"] = predictions["family"] == predictions["predicted_family"]
    predictions["operational_route"] = np.where(
        predictions["calibrated_confidence"] < threshold,
        "escalate",
        np.where(predictions["predicted_family"] == "Benign", "monitor", "plan"),
    )
    for index, label in enumerate(classes):
        predictions[f"probability_{label}"] = calibrated_probabilities[:, index]

    return result, predictions, model, calibrator


def plot_detector_results(results: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = list(results)
    x = np.arange(len(names))
    width = 0.34

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    macro_f1 = [results[name]["calibrated"]["macro_f1"] for name in names]
    balanced = [results[name]["calibrated"]["balanced_accuracy"] for name in names]
    ax.bar(x - width / 2, macro_f1, width, label="Macro-F1")
    ax.bar(x + width / 2, balanced, width, label="Balanced accuracy")
    ax.set_xticks(x, [name.replace("_", " ").title() for name in names])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "detector_feature_ablation.png", dpi=220)
    plt.close(fig)

    primary = results["leakage_controlled"]
    curve = primary["risk_coverage_curve"]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.plot(
        [point["coverage"] for point in curve],
        [point["selective_risk"] for point in curve],
        color="#2f6f68",
        linewidth=2,
    )
    selected = primary["confidence_aware"]
    ax.scatter(
        [selected["coverage"]],
        [1.0 - selected["selective_accuracy"]],
        color="#c34a36",
        label=f"Selected threshold = {primary['selected_threshold']:.2f}",
        zorder=3,
    )
    ax.set_xlabel("Fraction handled automatically")
    ax.set_ylabel("Error among automatically handled cases")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "confidence_risk_coverage.png", dpi=220)
    plt.close(fig)


def run_detector(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    feature_columns = [column for column in frame.columns if column not in METADATA_COLUMNS]
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    controlled_columns = [column for column in feature_columns if column not in leakage_drop]

    all_results: dict[str, Any] = {}
    for name, columns in [
        ("full_features", feature_columns),
        ("leakage_controlled", controlled_columns),
    ]:
        result, predictions, model, calibrator = evaluate_feature_set(
            frame,
            columns,
            name,
            config["detector"],
            seed,
        )
        all_results[name] = result
        predictions.to_csv(f"data/processed/test_predictions_{name}.csv", index=False)
        joblib.dump(model, f"data/processed/detector_{name}.joblib")
        joblib.dump(calibrator, f"data/processed/calibrator_{name}.joblib")

    write_json("reports/tables/detector_results.json", all_results)
    plot_detector_results(all_results, Path("reports/figures"))
    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and calibrate CICIoT2023 detectors.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    results = run_detector(args.config)
    primary = results["leakage_controlled"]
    print(
        "Leakage-controlled detector: "
        f"macro-F1={primary['calibrated']['macro_f1']:.4f}, "
        f"ECE={primary['calibrated']['ece_15_bin']:.4f}, "
        f"threshold={primary['selected_threshold']:.2f}."
    )


if __name__ == "__main__":
    main()
