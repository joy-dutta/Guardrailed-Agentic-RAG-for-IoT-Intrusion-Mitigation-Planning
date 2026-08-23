from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from .common import load_json, write_json
from .detector import METADATA_COLUMNS, build_model
from .detector_protocols import PROTOCOLS
from .metrics import choose_confidence_threshold, classification_metrics, routing_metrics


def binary_metrics(y_true_family: np.ndarray, y_pred_family: np.ndarray) -> dict[str, Any]:
    y_true = y_true_family != "Benign"
    y_pred = y_pred_family != "Benign"
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()
    return {
        "attack_precision": float(precision),
        "attack_recall": float(recall),
        "attack_f1": float(f1),
        "benign_specificity": float(tn / (tn + fp)),
        "false_positive_rate": float(fp / (tn + fp)),
        "true_attack_rows": int(tp + fn),
        "true_benign_rows": int(tn + fp),
        "true_positives": int(tp),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
    }


def combined_probabilities(
    binary_calibrator: Any,
    family_calibrator: Any,
    features: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    binary = binary_calibrator.predict_proba(features)
    binary_classes = list(binary_calibrator.classes_)
    attack_probability = binary[:, binary_classes.index("Attack")]
    attack_family = family_calibrator.predict_proba(features)
    attack_classes = list(family_calibrator.classes_)
    classes = np.asarray(["Benign", *attack_classes])
    probabilities = np.column_stack(
        [1.0 - attack_probability, attack_probability[:, None] * attack_family]
    )
    return classes, probabilities


def run_hierarchical_detector(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    frame = pd.read_csv("data/processed/ciciot2023_split_protocols.csv")
    frame["split"] = frame[PROTOCOLS["attack_type_aware"]]
    split_columns = set(PROTOCOLS.values())
    excluded = METADATA_COLUMNS | split_columns
    features = [column for column in frame.columns if column not in excluded]
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    features = [column for column in features if column not in leakage_drop]

    train = frame.loc[frame["split"] == "train"].copy()
    calibration = frame.loc[frame["split"] == "calibration"].copy()
    test = frame.loc[frame["split"] == "test"].copy()
    train["binary_label"] = np.where(train["family"] == "Benign", "Benign", "Attack")
    calibration["binary_label"] = np.where(
        calibration["family"] == "Benign", "Benign", "Attack"
    )

    binary_model = build_model(config["detector"], seed)
    binary_model.fit(train[features], train["binary_label"])
    binary_calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(binary_model),
        method=str(config["detector"]["calibration_method"]),
    )
    binary_calibrator.fit(calibration[features], calibration["binary_label"])

    attack_train = train.loc[train["family"] != "Benign"]
    attack_calibration = calibration.loc[calibration["family"] != "Benign"]
    family_model = build_model(config["detector"], seed + 1)
    family_model.fit(attack_train[features], attack_train["family"])
    family_calibrator = CalibratedClassifierCV(
        estimator=FrozenEstimator(family_model),
        method=str(config["detector"]["calibration_method"]),
    )
    family_calibrator.fit(attack_calibration[features], attack_calibration["family"])

    classes, calibration_probabilities = combined_probabilities(
        binary_calibrator, family_calibrator, calibration[features]
    )
    calibration_predictions = classes[np.argmax(calibration_probabilities, axis=1)]
    threshold, curve = choose_confidence_threshold(
        calibration["family"].to_numpy(),
        calibration_predictions,
        calibration_probabilities,
        target_accuracy=float(config["detector"]["target_selective_accuracy"]),
        minimum_coverage=float(config["detector"]["minimum_coverage"]),
    )
    _, test_probabilities = combined_probabilities(
        binary_calibrator, family_calibrator, test[features]
    )
    test_predictions = classes[np.argmax(test_probabilities, axis=1)]
    result = {
        "model": "hierarchical_random_forest",
        "split_protocol": "attack_type_aware",
        "feature_set": "leakage_controlled",
        "feature_count": len(features),
        "rows": {"train": len(train), "calibration": len(calibration), "test": len(test)},
        "calibrated": classification_metrics(
            test["family"].to_numpy(), test_predictions, test_probabilities, classes
        ),
        "binary_attack_detection": binary_metrics(
            test["family"].to_numpy(), test_predictions
        ),
        "selected_threshold": threshold,
        "confidence_aware": routing_metrics(
            test["family"].to_numpy(), test_predictions, test_probabilities, threshold
        ),
        "risk_coverage_curve": curve,
    }
    write_json("reports/tables/hierarchical_detector.json", result)
    joblib.dump(binary_model, "data/processed/hierarchical_binary_detector.joblib")
    joblib.dump(binary_calibrator, "data/processed/hierarchical_binary_calibrator.joblib")
    joblib.dump(family_model, "data/processed/hierarchical_family_detector.joblib")
    joblib.dump(family_calibrator, "data/processed/hierarchical_family_calibrator.joblib")

    metadata = ["source_row", "source_file", "attack_type", "family"]
    predictions = test[metadata].copy()
    predictions["predicted_family"] = test_predictions
    predictions["calibrated_confidence"] = test_probabilities.max(axis=1)
    predictions["correct"] = predictions["family"] == predictions["predicted_family"]
    predictions.to_csv(
        "data/processed/test_predictions_hierarchical_attack_type_aware.csv",
        index=False,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the hierarchical attack/family detector.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    result = run_hierarchical_detector(args.config)
    print(
        f"Hierarchical macro-F1={result['calibrated']['macro_f1']:.4f}, "
        f"attack F1={result['binary_attack_detection']['attack_f1']:.4f}."
    )


if __name__ == "__main__":
    main()
