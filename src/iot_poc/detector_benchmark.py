from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .common import load_json, write_json
from .detector import METADATA_COLUMNS
from .metrics import choose_confidence_threshold, classification_metrics, routing_metrics


def run_extra_trees_benchmark(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    model_config = config["detector_benchmarks"]["extra_trees"]
    detector_config = config["detector"]
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    feature_columns = [column for column in frame.columns if column not in METADATA_COLUMNS]
    dropped = set(config["dataset"]["leakage_control_drop"])
    feature_columns = [column for column in feature_columns if column not in dropped]

    train = frame.loc[frame["split"] == "train"]
    calibration = frame.loc[frame["split"] == "calibration"]
    test = frame.loc[frame["split"] == "test"]
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                ExtraTreesClassifier(
                    n_estimators=int(model_config["n_estimators"]),
                    min_samples_leaf=int(model_config["min_samples_leaf"]),
                    max_features=model_config["max_features"],
                    class_weight="balanced",
                    n_jobs=-1,
                    random_state=seed,
                ),
            ),
        ]
    )
    model.fit(train[feature_columns], train["family"])
    calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(model),
        method=str(detector_config["calibration_method"]),
    )
    calibrator.fit(calibration[feature_columns], calibration["family"])

    classes = np.asarray(calibrator.classes_)
    test_probabilities = calibrator.predict_proba(test[feature_columns])
    test_predictions = classes[np.argmax(test_probabilities, axis=1)]
    calibration_probabilities = calibrator.predict_proba(calibration[feature_columns])
    calibration_predictions = classes[np.argmax(calibration_probabilities, axis=1)]
    threshold, curve = choose_confidence_threshold(
        calibration["family"].to_numpy(),
        calibration_predictions,
        calibration_probabilities,
        target_accuracy=float(detector_config["target_selective_accuracy"]),
        minimum_coverage=float(detector_config["minimum_coverage"]),
    )
    result = {
        "model": "extra_trees",
        "feature_set": "leakage_controlled",
        "feature_count": len(feature_columns),
        "rows": {"train": len(train), "calibration": len(calibration), "test": len(test)},
        "calibrated": classification_metrics(
            test["family"].to_numpy(), test_predictions, test_probabilities, classes
        ),
        "selected_threshold": threshold,
        "confidence_aware": routing_metrics(
            test["family"].to_numpy(),
            test_predictions,
            test_probabilities,
            threshold,
        ),
        "risk_coverage_curve": curve,
    }
    write_json("reports/tables/detector_extra_trees_benchmark.json", result)
    joblib.dump(model, "data/processed/detector_extra_trees.joblib")
    joblib.dump(calibrator, "data/processed/calibrator_extra_trees.joblib")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed-split Extra Trees detector baseline.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    result = run_extra_trees_benchmark(args.config)
    print(
        f"Extra Trees macro-F1={result['calibrated']['macro_f1']:.4f}, "
        f"balanced accuracy={result['calibrated']['balanced_accuracy']:.4f}."
    )


if __name__ == "__main__":
    main()
