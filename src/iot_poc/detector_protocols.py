from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import joblib
import numpy as np
import pandas as pd

from .common import load_json, write_json
from .detector import METADATA_COLUMNS, evaluate_feature_set


PROTOCOLS = {
    "stratified_rows": "split_stratified_rows",
    "attack_type_aware": "split_attack_type_aware",
    "strict_family_file": "split_strict_family_file",
}


def plot_protocol_results(results: dict[str, Any]) -> None:
    labels = ["Stratified\nrows", "Attack-type\naware", "Strict file/subtype\nstress test"]
    names = list(PROTOCOLS)
    x = np.arange(len(names))
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.3, 4.3))
    ax.bar(
        x - width / 2,
        [results[name]["calibrated"]["macro_f1"] for name in names],
        width,
        color="#287271",
        label="Macro-F1",
    )
    ax.bar(
        x + width / 2,
        [results[name]["calibrated"]["balanced_accuracy"] for name in names],
        width,
        color="#E07A5F",
        label="Balanced accuracy",
    )
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_split_protocols.png", dpi=240)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.3, 4.3))
    coverage = [results[name]["confidence_aware"]["coverage"] for name in names]
    accuracy = [results[name]["confidence_aware"]["selective_accuracy"] for name in names]
    points = ax.scatter(coverage, accuracy, s=90, color=["#287271", "#E9C46A", "#E07A5F"])
    for index, label in enumerate(labels):
        ax.annotate(label.replace("\n", " "), (coverage[index], accuracy[index]), xytext=(7, 5), textcoords="offset points")
    ax.axhline(0.95, color="#555555", linestyle="--", linewidth=1, label="Planned 95% target")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.03)
    ax.set_xlabel("Fraction of test rows routed automatically")
    ax.set_ylabel("Accuracy among automatically routed rows")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_protocol_routing.png", dpi=240)
    plt.close(fig)


def run_protocol_detectors(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    frame = pd.read_csv("data/processed/ciciot2023_split_protocols.csv")
    split_columns = set(PROTOCOLS.values())
    excluded = METADATA_COLUMNS | split_columns
    feature_columns = [column for column in frame.columns if column not in excluded]
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    controlled_columns = [column for column in feature_columns if column not in leakage_drop]

    results: dict[str, Any] = {}
    for protocol_name, split_column in PROTOCOLS.items():
        protocol_frame = frame.copy()
        protocol_frame["split"] = protocol_frame[split_column]
        result, predictions, model, calibrator = evaluate_feature_set(
            protocol_frame,
            controlled_columns,
            "leakage_controlled",
            config["detector"],
            seed,
        )
        result["split_protocol"] = protocol_name
        result["split_column"] = split_column
        results[protocol_name] = result
        predictions.to_csv(
            f"data/processed/test_predictions_protocol_{protocol_name}.csv", index=False
        )
        joblib.dump(model, f"data/processed/detector_protocol_{protocol_name}.joblib")
        joblib.dump(
            calibrator, f"data/processed/calibrator_protocol_{protocol_name}.joblib"
        )

    write_json("reports/tables/detector_split_protocols.json", results)
    rows = []
    for name, result in results.items():
        rows.append(
            {
                "protocol": name,
                "train_rows": result["rows"]["train"],
                "calibration_rows": result["rows"]["calibration"],
                "test_rows": result["rows"]["test"],
                "macro_f1": result["calibrated"]["macro_f1"],
                "balanced_accuracy": result["calibrated"]["balanced_accuracy"],
                "accuracy": result["calibrated"]["accuracy"],
                "ece_15_bin": result["calibrated"]["ece_15_bin"],
                "threshold": result["selected_threshold"],
                "automatic_coverage": result["confidence_aware"]["coverage"],
                "selective_accuracy": result["confidence_aware"]["selective_accuracy"],
                "wrong_automatic_decisions": result["confidence_aware"]["wrong_automatic_decisions"],
            }
        )
    pd.DataFrame(rows).to_csv("reports/tables/detector_split_protocols.csv", index=False)
    plot_protocol_results(results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare detector split protocols.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    results = run_protocol_detectors(args.config)
    for name, result in results.items():
        print(
            f"{name}: macro-F1={result['calibrated']['macro_f1']:.4f}, "
            f"selective accuracy={result['confidence_aware']['selective_accuracy']:.4f}."
        )


if __name__ == "__main__":
    main()
