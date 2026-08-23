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
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .common import load_json, write_json
from .detector import METADATA_COLUMNS
from .metrics import choose_confidence_threshold, classification_metrics, routing_metrics


def build_estimators(config: dict[str, Any], seed: int) -> dict[str, Pipeline]:
    extra = config["detector_alternatives"]["extra_trees"]
    hist = config["detector_alternatives"]["hist_gradient_boosting"]
    return {
        "extra_trees": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "classifier",
                    ExtraTreesClassifier(
                        n_estimators=int(extra["n_estimators"]),
                        max_depth=int(extra["max_depth"]),
                        min_samples_leaf=int(extra["min_samples_leaf"]),
                        max_features=str(extra["max_features"]),
                        class_weight="balanced",
                        n_jobs=-1,
                        random_state=seed,
                    ),
                ),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        max_iter=int(hist["max_iter"]),
                        learning_rate=float(hist["learning_rate"]),
                        max_leaf_nodes=int(hist["max_leaf_nodes"]),
                        min_samples_leaf=int(hist["min_samples_leaf"]),
                        l2_regularization=float(hist["l2_regularization"]),
                        class_weight="balanced",
                        random_state=seed,
                    ),
                ),
            ]
        ),
    }


def evaluate_estimator(
    estimator: Pipeline,
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    detector_config: dict[str, Any],
) -> dict[str, Any]:
    start = time.perf_counter()
    estimator.fit(train[features], train["family"])
    fit_seconds = time.perf_counter() - start
    classes = np.asarray(estimator.classes_)

    start = time.perf_counter()
    calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(estimator),
        method=str(detector_config["calibration_method"]),
    )
    calibrator.fit(calibration[features], calibration["family"])
    calibration_seconds = time.perf_counter() - start

    calibration_probabilities = calibrator.predict_proba(calibration[features])
    calibration_predictions = classes[np.argmax(calibration_probabilities, axis=1)]
    threshold, _ = choose_confidence_threshold(
        calibration["family"].to_numpy(),
        calibration_predictions,
        calibration_probabilities,
        float(detector_config["target_selective_accuracy"]),
        float(detector_config["minimum_coverage"]),
    )

    start = time.perf_counter()
    probabilities = calibrator.predict_proba(test[features])
    inference_seconds = time.perf_counter() - start
    predictions = classes[np.argmax(probabilities, axis=1)]
    y_test = test["family"].to_numpy()
    result = classification_metrics(y_test, predictions, probabilities, classes)
    result.update(
        {
            "selected_threshold": threshold,
            "confidence_aware": routing_metrics(
                y_test, predictions, probabilities, threshold
            ),
            "fit_seconds": fit_seconds,
            "calibration_seconds": calibration_seconds,
            "test_inference_seconds": inference_seconds,
            "feature_count": len(features),
        }
    )
    return result


def run_alternatives(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    frame = pd.read_csv("data/processed/ciciot2023_split_protocols.csv")
    frame["split"] = frame["split_attack_type_aware"]
    excluded = METADATA_COLUMNS | {
        "split_strict_family_file",
        "split_attack_type_aware",
        "split_stratified_rows",
    }
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    features = [
        column for column in frame.columns if column not in excluded and column not in leakage_drop
    ]
    train = frame.loc[frame["split"] == "train"]
    calibration = frame.loc[frame["split"] == "calibration"]
    test = frame.loc[frame["split"] == "test"]
    primary = load_json("reports/tables/detector_split_protocols.json")["attack_type_aware"]
    results: dict[str, Any] = {
        "random_forest_primary": {
            **primary["calibrated"],
            "selected_threshold": primary["selected_threshold"],
            "confidence_aware": primary["confidence_aware"],
        }
    }
    for name, estimator in build_estimators(config, seed).items():
        results[name] = evaluate_estimator(
            estimator, train, calibration, test, features, config["detector"]
        )
        del estimator
        gc.collect()

    output = {
        "protocol": "attack_type_aware_selected_seed",
        "seed": seed,
        "selection_note": (
            "These are predeclared model-family sensitivity checks on the selected split. "
            "They do not replace the five-seed Random Forest primary result."
        ),
        "results": results,
    }
    write_json("reports/tables/detector_alternative_models.json", output)
    table = []
    for name, result in results.items():
        table.append(
            {
                "model": name,
                "macro_f1": result["macro_f1"],
                "balanced_accuracy": result["balanced_accuracy"],
                "accuracy": result["accuracy"],
                "threshold": result["selected_threshold"],
                "coverage": result["confidence_aware"]["coverage"],
                "selective_accuracy": result["confidence_aware"]["selective_accuracy"],
                "fit_seconds": result.get("fit_seconds"),
            }
        )
    pd.DataFrame(table).to_csv("reports/tables/detector_alternative_models.csv", index=False)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    labels = [row["model"].replace("_", " ").title() for row in table]
    x = np.arange(len(table))
    width = 0.34
    ax.bar(x - width / 2, [row["macro_f1"] for row in table], width, label="Macro-F1")
    ax.bar(
        x + width / 2,
        [row["balanced_accuracy"] for row in table],
        width,
        label="Balanced accuracy",
    )
    ax.set_xticks(x, labels, rotation=15)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_alternative_models.png", dpi=240)
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark detector alternatives.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    result = run_alternatives(args.config)
    print(
        {
            name: round(values["macro_f1"], 4)
            for name, values in result["results"].items()
        }
    )


if __name__ == "__main__":
    main()
