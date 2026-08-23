from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import load_json, stable_seed, write_json


WEB_ATTACKS = {
    "Backdoor_Malware",
    "BrowserHijacking",
    "CommandInjection",
    "SqlInjection",
    "Uploading_Attack",
    "VulnerabilityScan",
    "XSS",
}


def attack_family(folder: str) -> str:
    if folder == "Benign_Final":
        return "Benign"
    if folder.startswith("DDoS-"):
        return "DDoS"
    if folder.startswith("DoS-"):
        return "DoS"
    if folder.startswith("Recon-"):
        return "Recon"
    if folder.startswith("Mirai-"):
        return "Mirai"
    if folder == "DictionaryBruteForce":
        return "BruteForce"
    if folder in {"DNS_Spoofing", "MITM-ArpSpoofing"}:
        return "Spoofing"
    if folder in WEB_ATTACKS:
        return "Web"
    raise ValueError(f"Unmapped CICIoT2023 folder: {folder}")


def discover_csv_files(csv_root: str | Path) -> list[dict[str, Any]]:
    root = Path(csv_root)
    records = []
    for path in sorted(root.glob("*/*.csv")):
        attack = path.parent.name
        records.append(
            {
                "path": path,
                "source_file": str(path.relative_to(root)).replace("\\", "/"),
                "attack_type": attack,
                "family": attack_family(attack),
                "size_bytes": path.stat().st_size,
            }
        )
    if not records:
        raise FileNotFoundError(f"No CSV files found below {root}")
    return records


def _trim_priority_sample(
    samples: list[pd.DataFrame], priorities: list[np.ndarray], quota: int
) -> tuple[list[pd.DataFrame], list[np.ndarray]]:
    combined = pd.concat(samples, ignore_index=True)
    combined_priorities = np.concatenate(priorities)
    if len(combined) <= quota:
        return [combined], [combined_priorities]
    keep = np.argpartition(combined_priorities, quota - 1)[:quota]
    return [combined.iloc[keep].reset_index(drop=True)], [combined_priorities[keep]]


def sample_file(
    path: Path,
    quota: int,
    chunksize: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    samples: list[pd.DataFrame] = []
    priorities: list[np.ndarray] = []
    total_rows = 0
    missing_cells = 0
    nonfinite_cells = 0
    columns: list[str] | None = None

    for chunk in pd.read_csv(path, chunksize=chunksize, dtype=np.float32):
        if columns is None:
            columns = list(chunk.columns)
        elif list(chunk.columns) != columns:
            raise ValueError(f"Column mismatch in {path}")

        values = chunk.to_numpy(copy=False)
        missing_cells += int(np.isnan(values).sum())
        nonfinite_cells += int((~np.isfinite(values)).sum())
        row_numbers = np.arange(total_rows, total_rows + len(chunk), dtype=np.int64)
        total_rows += len(chunk)

        local_priorities = rng.random(len(chunk))
        local_keep_count = min(quota, len(chunk))
        if local_keep_count < len(chunk):
            local_keep = np.argpartition(local_priorities, local_keep_count - 1)[:local_keep_count]
        else:
            local_keep = np.arange(len(chunk))
        selected = chunk.iloc[local_keep].copy()
        selected["source_row"] = row_numbers[local_keep]
        samples.append(selected)
        priorities.append(local_priorities[local_keep])

        if sum(len(frame) for frame in samples) > max(quota * 4, quota + chunksize):
            samples, priorities = _trim_priority_sample(samples, priorities, quota)

    samples, priorities = _trim_priority_sample(samples, priorities, min(quota, total_rows))
    sampled = samples[0]
    return sampled, {
        "rows": total_rows,
        "sampled_rows": len(sampled),
        "missing_cells": missing_cells,
        "nonfinite_cells": nonfinite_cells,
        "columns": columns or [],
    }


def assign_splits(sample: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = sample.copy()
    result["split"] = ""
    assignments: dict[str, Any] = {}
    rng = np.random.default_rng(seed)

    for family, family_frame in result.groupby("family", sort=True):
        files = sorted(family_frame["source_file"].unique())
        if len(files) >= 3:
            shuffled = list(rng.permutation(files))
            n_train = max(1, int(round(len(files) * 0.60)))
            n_calibration = max(1, int(round(len(files) * 0.20)))
            if n_train + n_calibration >= len(files):
                n_train = max(1, len(files) - 2)
                n_calibration = 1
            file_splits = {
                "train": shuffled[:n_train],
                "calibration": shuffled[n_train : n_train + n_calibration],
                "test": shuffled[n_train + n_calibration :],
            }
            for split_name, split_files in file_splits.items():
                result.loc[
                    (result["family"] == family) & result["source_file"].isin(split_files),
                    "split",
                ] = split_name
            assignments[family] = {"method": "file_disjoint", **file_splits}
        else:
            ordered_index = family_frame.sort_values(["source_file", "source_row"]).index.to_numpy()
            train_end = int(len(ordered_index) * 0.60)
            calibration_end = int(len(ordered_index) * 0.80)
            result.loc[ordered_index[:train_end], "split"] = "train"
            result.loc[ordered_index[train_end:calibration_end], "split"] = "calibration"
            result.loc[ordered_index[calibration_end:], "split"] = "test"
            assignments[family] = {
                "method": "ordered_row_blocks_due_to_insufficient_files",
                "files": files,
            }

    if (result["split"] == "").any():
        raise RuntimeError("Some rows did not receive a dataset split.")
    return result, assignments


def remove_cross_split_duplicates(
    frame: pd.DataFrame, feature_columns: list[str]
) -> tuple[pd.DataFrame, dict[str, int]]:
    result_parts: list[pd.DataFrame] = []
    seen: set[int] = set()
    removals: dict[str, int] = {}
    for split_name in ["train", "calibration", "test"]:
        part = frame.loc[frame["split"] == split_name].copy()
        hashes = pd.util.hash_pandas_object(part[feature_columns], index=False).astype("uint64")
        keep = ~hashes.duplicated(keep="first")
        if seen:
            keep &= ~hashes.isin(seen)
        removals[split_name] = int((~keep).sum())
        kept = part.loc[keep].copy()
        kept_hashes = pd.util.hash_pandas_object(kept[feature_columns], index=False).astype("uint64")
        seen.update(int(value) for value in kept_hashes)
        result_parts.append(kept)
    return pd.concat(result_parts, ignore_index=True), removals


def prepare_dataset(config_path: str | Path) -> dict[str, Any]:
    config = load_json(config_path)
    dataset_config = config["dataset"]
    seed = int(config["seed"])
    files = discover_csv_files(dataset_config["csv_root"])
    by_family: dict[str, list[dict[str, Any]]] = {}
    for record in files:
        by_family.setdefault(record["family"], []).append(record)

    sampled_parts: list[pd.DataFrame] = []
    file_audit: list[dict[str, Any]] = []
    expected_columns: list[str] | None = None
    target = int(dataset_config["sample_rows_per_family"])
    chunksize = int(dataset_config["chunksize"])

    for family, family_files in sorted(by_family.items()):
        quota = max(1, math.ceil(target / len(family_files)))
        family_parts = []
        for record in family_files:
            sampled, stats = sample_file(
                record["path"],
                quota=quota,
                chunksize=chunksize,
                seed=stable_seed(record["source_file"], seed),
            )
            if expected_columns is None:
                expected_columns = stats["columns"]
            elif stats["columns"] != expected_columns:
                raise ValueError(f"Feature columns differ in {record['source_file']}")
            sampled["source_file"] = record["source_file"]
            sampled["attack_type"] = record["attack_type"]
            sampled["family"] = family
            family_parts.append(sampled)
            file_audit.append({**{k: v for k, v in record.items() if k != "path"}, **stats})
        family_sample = pd.concat(family_parts, ignore_index=True)
        if len(family_sample) > target:
            family_sample = family_sample.sample(n=target, random_state=stable_seed(family, seed))
        sampled_parts.append(family_sample)

    feature_columns = expected_columns or []
    complete_sample = pd.concat(sampled_parts, ignore_index=True)
    sampled_infinite_cells = int(
        np.isinf(complete_sample[feature_columns].to_numpy(copy=False)).sum()
    )
    complete_sample[feature_columns] = complete_sample[feature_columns].replace(
        [np.inf, -np.inf], np.nan
    )
    complete_sample, split_assignments = assign_splits(complete_sample, seed)
    deduplicated, duplicate_removals = remove_cross_split_duplicates(complete_sample, feature_columns)

    output_path = Path("data/processed/ciciot2023_family_sample.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    deduplicated.to_csv(output_path, index=False)

    audit = {
        "source_csv_files": len(files),
        "source_size_bytes": int(sum(record["size_bytes"] for record in files)),
        "feature_count": len(feature_columns),
        "feature_columns": feature_columns,
        "family_file_counts": {family: len(records) for family, records in sorted(by_family.items())},
        "sample_rows_before_deduplication": len(complete_sample),
        "sample_rows_after_deduplication": len(deduplicated),
        "sampled_infinite_cells_replaced_with_nan": sampled_infinite_cells,
        "sampled_missing_cells_after_cleaning": int(
            deduplicated[feature_columns].isna().sum().sum()
        ),
        "rows_by_family": {k: int(v) for k, v in deduplicated["family"].value_counts().sort_index().items()},
        "rows_by_split": {k: int(v) for k, v in deduplicated["split"].value_counts().items()},
        "cross_split_duplicate_removals": duplicate_removals,
        "split_assignments": split_assignments,
        "leakage_control_drop": dataset_config["leakage_control_drop"],
        "file_audit": file_audit,
        "output": str(output_path),
    }
    write_json("reports/tables/dataset_audit.json", audit)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a reproducible CICIoT2023 family sample.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    audit = prepare_dataset(args.config)
    print(
        f"Prepared {audit['sample_rows_after_deduplication']:,} rows from "
        f"{audit['source_csv_files']} source CSV files."
    )


if __name__ == "__main__":
    main()
