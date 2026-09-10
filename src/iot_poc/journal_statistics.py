from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import load_json, read_jsonl, write_json


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def exact_mcnemar(left: dict[str, bool], right: dict[str, bool]) -> dict[str, Any]:
    common = sorted(set(left) & set(right))
    left_only = sum(left[key] and not right[key] for key in common)
    right_only = sum(right[key] and not left[key] for key in common)
    discordant = left_only + right_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(
            math.comb(discordant, index)
            for index in range(min(left_only, right_only) + 1)
        )
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "paired_cases": len(common),
        "left_only": left_only,
        "right_only": right_only,
        "discordant": discordant,
        "two_sided_exact_p": p_value,
    }


def binary_endpoint(rows: list[dict[str, Any]], getter: Any) -> dict[str, Any]:
    successes = sum(bool(getter(row)) for row in rows)
    lower, upper = wilson_interval(successes, len(rows))
    return {
        "successes": successes,
        "total": len(rows),
        "rate": successes / len(rows) if rows else 0.0,
        "wilson_95": [lower, upper],
    }


def run_statistics(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    planning = extension["planning"]
    run_path = Path("experiments/runs") / str(planning["run_id"]) / "results.jsonl"
    records = [row for row in read_jsonl(run_path) if "error" not in row]
    by_condition = {
        condition: [row for row in records if row["condition"] == condition]
        for condition in planning["conditions"]
    }
    endpoints = {}
    for condition, rows in by_condition.items():
        endpoints[condition] = {
            "raw_compact_schema_validity": binary_endpoint(
                rows, lambda row: row["validity"]["raw_compact_schema_valid"]
            ),
            "raw_full_schema_validity": binary_endpoint(
                rows, lambda row: row["validity"]["raw_full_schema_valid"]
            ),
            "valid_evidence_attachment": binary_endpoint(
                rows,
                lambda row: bool(row["raw_intent"].get("evidence_used"))
                and bool(row["validity"]["citation_ids_valid"]),
            ),
            "raw_policy_conformance": binary_endpoint(
                rows, lambda row: row["validity"]["raw_policy_valid"]
            ),
            "normalized_schema_validity": binary_endpoint(
                rows, lambda row: row["validity"]["normalized_full_schema_valid"]
            ),
            "normalized_policy_conformance": binary_endpoint(
                rows, lambda row: row["validity"]["normalized_policy_valid"]
            ),
        }

    attachment = {
        condition: {
            row["case_id"]: bool(row["raw_intent"].get("evidence_used"))
            and bool(row["validity"]["citation_ids_valid"])
            for row in rows
        }
        for condition, rows in by_condition.items()
    }
    compact_schema = {
        condition: {
            row["case_id"]: bool(row["validity"]["raw_compact_schema_valid"])
            for row in rows
        }
        for condition, rows in by_condition.items()
    }
    raw_policy = {
        condition: {
            row["case_id"]: bool(row["validity"]["raw_policy_valid"])
            for row in rows
        }
        for condition, rows in by_condition.items()
    }
    paired_tests = {
        "rag_vs_no_rag_valid_evidence": exact_mcnemar(
            attachment["rag"], attachment["no_rag"]
        ),
        "rag_vs_mismatched_valid_identifier": exact_mcnemar(
            attachment["rag"], attachment["mismatched_rag"]
        ),
        "rag_vs_no_rag_compact_schema": exact_mcnemar(
            compact_schema["rag"], compact_schema["no_rag"]
        ),
        "rag_vs_mismatched_compact_schema": exact_mcnemar(
            compact_schema["rag"], compact_schema["mismatched_rag"]
        ),
        "rag_vs_no_rag_raw_policy": exact_mcnemar(
            raw_policy["rag"], raw_policy["no_rag"]
        ),
        "rag_vs_mismatched_raw_policy": exact_mcnemar(
            raw_policy["rag"], raw_policy["mismatched_rag"]
        ),
    }
    output = {
        "records": len(records),
        "cases": len({row["case_id"] for row in records}),
        "endpoints": endpoints,
        "paired_tests": paired_tests,
        "interpretation_guardrail": (
            "A valid identifier measures traceability, not semantic support. Semantic support "
            "must be reported from the blinded evidence audit."
        ),
    }
    write_json("reports/journal_extension/tables/expanded_agent_statistics.json", output)

    table_rows = []
    for condition, condition_metrics in endpoints.items():
        for metric, values in condition_metrics.items():
            table_rows.append(
                {
                    "condition": condition,
                    "metric": metric,
                    "successes": values["successes"],
                    "total": values["total"],
                    "rate": values["rate"],
                    "ci_low": values["wilson_95"][0],
                    "ci_high": values["wilson_95"][1],
                }
            )
    pd.DataFrame(table_rows).to_csv(
        "reports/journal_extension/tables/expanded_agent_statistics.csv", index=False
    )

    figure_dir = Path("reports/journal_extension/figures")
    figure_dir.mkdir(parents=True, exist_ok=True)
    conditions = list(planning["conditions"])
    labels = [condition.replace("_", " ").title() for condition in conditions]
    values = [endpoints[condition]["valid_evidence_attachment"] for condition in conditions]
    rates = np.asarray([item["rate"] for item in values])
    lowers = rates - np.asarray([item["wilson_95"][0] for item in values])
    uppers = np.asarray([item["wilson_95"][1] for item in values]) - rates
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.bar(labels, rates, color=["#287271", "#7A7A7A", "#E07A5F"])
    ax.errorbar(
        np.arange(len(labels)), rates, yerr=[lowers, uppers], fmt="none", color="black", capsize=4
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Valid evidence attachment rate")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "expanded_rag_traceability.pdf", bbox_inches="tight")
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add confidence intervals and paired tests to journal agent runs."
    )
    parser.add_argument("--config", default="configs/ieee_access_extension.json")
    args = parser.parse_args()
    print(json.dumps(run_statistics(args.config), indent=2))


if __name__ == "__main__":
    main()
