from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
)


def expected_calibration_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    bins: int = 15,
) -> float:
    confidence = probabilities.max(axis=1)
    correctness = (y_pred == y_true).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if not np.any(mask):
            continue
        ece += mask.mean() * abs(correctness[mask].mean() - confidence[mask].mean())
    return float(ece)


def multiclass_brier_score(
    y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray
) -> float:
    class_to_index = {label: index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(probabilities, dtype=float)
    for row, label in enumerate(y_true):
        one_hot[row, class_to_index[label]] = 1.0
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    classes: np.ndarray,
) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "log_loss": float(log_loss(y_true, probabilities, labels=classes)),
        "multiclass_brier": multiclass_brier_score(y_true, probabilities, classes),
        "ece_15_bin": expected_calibration_error(y_true, y_pred, probabilities, bins=15),
        "per_class": {
            str(label): {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(classes)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=classes).tolist(),
        "classes": [str(label) for label in classes],
    }


def choose_confidence_threshold(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    target_accuracy: float,
    minimum_coverage: float,
) -> tuple[float, list[dict[str, float]]]:
    confidence = probabilities.max(axis=1)
    curve = []
    candidates = []
    for threshold in np.linspace(0.0, 0.99, 100):
        automated = confidence >= threshold
        coverage = float(automated.mean())
        selective_accuracy = float((y_pred[automated] == y_true[automated]).mean()) if automated.any() else 1.0
        point = {
            "threshold": float(round(threshold, 2)),
            "coverage": coverage,
            "selective_accuracy": selective_accuracy,
            "selective_risk": 1.0 - selective_accuracy,
        }
        curve.append(point)
        if coverage >= minimum_coverage and selective_accuracy >= target_accuracy:
            candidates.append(point)
    if candidates:
        selected = min(candidates, key=lambda item: item["threshold"])
    else:
        selected = max(curve, key=lambda item: (item["selective_accuracy"], item["coverage"]))
    return float(selected["threshold"]), curve


def routing_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, float | int]:
    confidence = probabilities.max(axis=1)
    automated = confidence >= threshold
    correct = y_pred == y_true
    return {
        "threshold": float(threshold),
        "coverage": float(automated.mean()),
        "escalation_rate": float((~automated).mean()),
        "selective_accuracy": float(correct[automated].mean()) if automated.any() else 1.0,
        "wrong_automatic_decisions": int((automated & ~correct).sum()),
        "wrong_automatic_decision_rate_all_cases": float((automated & ~correct).mean()),
        "automated_cases": int(automated.sum()),
        "escalated_cases": int((~automated).sum()),
    }
