from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import load_json, stable_seed, write_json


def three_way_file_split(files: list[str], seed: int) -> dict[str, list[str]]:
    rng = np.random.default_rng(seed)
    shuffled = list(rng.permutation(sorted(files)))
    n_train = max(1, int(round(len(shuffled) * 0.60)))
    n_calibration = max(1, int(round(len(shuffled) * 0.20)))
    if n_train + n_calibration >= len(shuffled):
        n_train = max(1, len(shuffled) - 2)
        n_calibration = 1
    return {
        "train": shuffled[:n_train],
        "calibration": shuffled[n_train : n_train + n_calibration],
        "test": shuffled[n_train + n_calibration :],
    }


def assign_attack_type_aware(
    frame: pd.DataFrame, seed: int
) -> tuple[pd.Series, dict[str, Any]]:
    assignments = pd.Series("", index=frame.index, dtype="object")
    audit: dict[str, Any] = {}
    for attack_type, group in frame.groupby("attack_type", sort=True):
        files = sorted(group["source_file"].unique())
        if len(files) >= 3:
            file_splits = three_way_file_split(
                files, stable_seed(f"attack-type:{attack_type}", seed)
            )
            for split_name, split_files in file_splits.items():
                assignments.loc[group.index[group["source_file"].isin(split_files)]] = split_name
            audit[attack_type] = {"method": "file_disjoint_within_attack_type", **file_splits}
        else:
            ordered = group.sort_values(["source_file", "source_row"]).index.to_numpy()
            train_end = int(len(ordered) * 0.60)
            calibration_end = int(len(ordered) * 0.80)
            assignments.loc[ordered[:train_end]] = "train"
            assignments.loc[ordered[train_end:calibration_end]] = "calibration"
            assignments.loc[ordered[calibration_end:]] = "test"
            audit[attack_type] = {
                "method": "ordered_row_blocks_due_to_fewer_than_three_files",
                "files": files,
            }
    if (assignments == "").any():
        raise RuntimeError("Attack-type-aware split left rows unassigned.")
    return assignments, audit


def assign_stratified_rows(
    frame: pd.DataFrame, seed: int
) -> tuple[pd.Series, dict[str, Any]]:
    assignments = pd.Series("", index=frame.index, dtype="object")
    audit: dict[str, Any] = {}
    for attack_type, group in frame.groupby("attack_type", sort=True):
        rng = np.random.default_rng(stable_seed(f"row:{attack_type}", seed))
        shuffled = rng.permutation(group.index.to_numpy())
        train_end = int(len(shuffled) * 0.60)
        calibration_end = int(len(shuffled) * 0.80)
        assignments.loc[shuffled[:train_end]] = "train"
        assignments.loc[shuffled[train_end:calibration_end]] = "calibration"
        assignments.loc[shuffled[calibration_end:]] = "test"
        audit[attack_type] = {
            "method": "random_rows_stratified_by_attack_type",
            "rows": len(group),
        }
    if (assignments == "").any():
        raise RuntimeError("Stratified-row split left rows unassigned.")
    return assignments, audit


def build_split_protocols(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    seed = int(config["seed"])
    source = Path("data/processed/ciciot2023_family_sample.csv")
    frame = pd.read_csv(source)
    frame = frame.rename(columns={"split": "split_strict_family_file"})
    frame["split_attack_type_aware"], attack_audit = assign_attack_type_aware(frame, seed)
    frame["split_stratified_rows"], row_audit = assign_stratified_rows(frame, seed)

    output = Path("data/processed/ciciot2023_split_protocols.csv")
    frame.to_csv(output, index=False)
    protocol_columns = [
        "split_strict_family_file",
        "split_attack_type_aware",
        "split_stratified_rows",
    ]
    summary = {
        "input": str(source),
        "output": str(output),
        "rows": len(frame),
        "protocols": {
            column: {
                "rows_by_split": {
                    key: int(value) for key, value in frame[column].value_counts().items()
                },
                "rows_by_family_and_split": {
                    family: {
                        key: int(value)
                        for key, value in group[column].value_counts().items()
                    }
                    for family, group in frame.groupby("family", sort=True)
                },
            }
            for column in protocol_columns
        },
        "attack_type_aware_assignment": attack_audit,
        "stratified_row_assignment": row_audit,
        "interpretation": {
            "split_stratified_rows": "Within-source recognition benchmark; optimistic because rows from each source file can appear in every split.",
            "split_attack_type_aware": "Known-attack benchmark; preserves every attack subtype across splits and holds out files when enough files exist.",
            "split_strict_family_file": "Stress test; all source files are disjoint at family level and rare families may include unseen attack subtypes in test.",
        },
    }
    write_json("reports/tables/split_protocols.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create explicit CICIoT2023 split protocols.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    summary = build_split_protocols(args.config)
    print(f"Wrote three split protocols for {summary['rows']:,} globally unique rows.")


if __name__ == "__main__":
    main()
