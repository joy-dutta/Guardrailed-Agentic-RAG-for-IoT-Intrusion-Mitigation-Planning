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
from .dataset import assign_splits
from .detector import METADATA_COLUMNS, evaluate_feature_set
from .split_protocols import assign_attack_type_aware


def compact_result(seed: int, protocol: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed": seed,
        "protocol": protocol,
        "macro_f1": result["calibrated"]["macro_f1"],
        "balanced_accuracy": result["calibrated"]["balanced_accuracy"],
        "accuracy": result["calibrated"]["accuracy"],
        "ece_15_bin": result["calibrated"]["ece_15_bin"],
        "threshold": result["selected_threshold"],
        "coverage": result["confidence_aware"]["coverage"],
        "selective_accuracy": result["confidence_aware"]["selective_accuracy"],
        "wrong_automatic_decisions": result["confidence_aware"]["wrong_automatic_decisions"],
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    metric_names = [
        "macro_f1",
        "balanced_accuracy",
        "accuracy",
        "ece_15_bin",
        "threshold",
        "coverage",
        "selective_accuracy",
        "wrong_automatic_decisions",
    ]
    for protocol in sorted({row["protocol"] for row in rows}):
        protocol_rows = [row for row in rows if row["protocol"] == protocol]
        summary[protocol] = {
            metric: {
                "mean": float(np.mean([row[metric] for row in protocol_rows])),
                "sample_std": float(np.std([row[metric] for row in protocol_rows], ddof=1)),
                "minimum": float(np.min([row[metric] for row in protocol_rows])),
                "maximum": float(np.max([row[metric] for row in protocol_rows])),
            }
            for metric in metric_names
        }
    return summary


def plot_repeats(rows: list[dict[str, Any]]) -> None:
    protocols = ["attack_type_aware", "strict_family_file"]
    labels = ["Attack-type-aware\nprimary", "Strict file/subtype\nstress test"]
    x = np.arange(len(protocols))
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.0))
    for axis, metric, ylabel in [
        (axes[0], "macro_f1", "Macro-F1"),
        (axes[1], "selective_accuracy", "Accuracy after confidence gate"),
    ]:
        for index, protocol in enumerate(protocols):
            values = [row[metric] for row in rows if row["protocol"] == protocol]
            offsets = np.linspace(-0.06, 0.06, len(values))
            axis.scatter(
                np.full(len(values), index) + offsets,
                values,
                s=45,
                color="#287271" if index == 0 else "#E07A5F",
                zorder=3,
            )
            axis.plot(
                [index - 0.12, index + 0.12],
                [np.mean(values), np.mean(values)],
                color="#222222",
                linewidth=2,
            )
        axis.set_xticks(x, labels)
        axis.set_ylim(0, 1.02)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.25)
    axes[1].axhline(0.95, color="#555555", linestyle="--", linewidth=1)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_repeated_seeds.png", dpi=240)
    plt.close(fig)


def run_repeated_seeds(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seeds = [int(seed) for seed in config["detector_repeat_seeds"]]
    frame = pd.read_csv("data/processed/ciciot2023_family_sample.csv")
    feature_columns = [column for column in frame.columns if column not in METADATA_COLUMNS]
    leakage_drop = set(config["dataset"]["leakage_control_drop"])
    feature_columns = [column for column in feature_columns if column not in leakage_drop]
    rows: list[dict[str, Any]] = []

    for seed in seeds:
        attack_frame = frame.copy()
        attack_frame["split"], _ = assign_attack_type_aware(attack_frame, seed)
        result, predictions, model, calibrator = evaluate_feature_set(
            attack_frame,
            feature_columns,
            "leakage_controlled",
            config["detector"],
            seed,
        )
        rows.append(compact_result(seed, "attack_type_aware", result))
        del attack_frame, result, predictions, model, calibrator
        gc.collect()

        strict_frame, _ = assign_splits(frame, seed)
        result, predictions, model, calibrator = evaluate_feature_set(
            strict_frame,
            feature_columns,
            "leakage_controlled",
            config["detector"],
            seed,
        )
        rows.append(compact_result(seed, "strict_family_file", result))
        del strict_frame, result, predictions, model, calibrator
        gc.collect()

    output = {"seeds": seeds, "runs": rows, "summary": summarize(rows)}
    write_json("reports/tables/detector_repeated_seeds.json", output)
    pd.DataFrame(rows).to_csv("reports/tables/detector_repeated_seeds.csv", index=False)
    plot_repeats(rows)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeat detector protocols over fixed seeds.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    output = run_repeated_seeds(args.config)
    for protocol, metrics in output["summary"].items():
        print(
            f"{protocol}: macro-F1={metrics['macro_f1']['mean']:.4f} "
            f"+/- {metrics['macro_f1']['sample_std']:.4f}."
        )


if __name__ == "__main__":
    main()
