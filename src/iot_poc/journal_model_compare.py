from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import load_json, read_jsonl, write_json
from .journal_statistics import exact_mcnemar, wilson_interval


Endpoint = tuple[str, Callable[[dict[str, Any]], bool]]


ENDPOINTS: list[Endpoint] = [
    ("raw_compact_schema_valid", lambda row: row["validity"]["raw_compact_schema_valid"]),
    ("raw_policy_conformant", lambda row: row["validity"]["raw_policy_valid"]),
    (
        "valid_evidence_attachment",
        lambda row: bool(row["raw_intent"].get("evidence_used"))
        and bool(row["validity"]["citation_ids_valid"]),
    ),
    (
        "normalized_policy_conformant",
        lambda row: row["validity"]["normalized_policy_valid"],
    ),
]


def action_names(row: dict[str, Any]) -> set[str]:
    return {
        str(action["action"])
        for action in row["normalized_intent"].get("actions", [])
        if isinstance(action, dict) and "action" in action
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def endpoint_summary(
    rows: list[dict[str, Any]], getter: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    successes = sum(bool(getter(row)) for row in rows)
    lower, upper = wilson_interval(successes, len(rows))
    return {
        "successes": successes,
        "total": len(rows),
        "rate": successes / len(rows) if rows else 0.0,
        "wilson_95": [lower, upper],
    }


def plot_model_comparison(output: dict[str, Any]) -> None:
    metrics = [
        ("raw_compact_schema_valid", "Compact schema"),
        ("raw_policy_conformant", "Raw policy"),
        ("valid_evidence_attachment", "Evidence attached"),
    ]
    x = np.arange(len(metrics))
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for index, (model, label, color) in enumerate(
        [
            ("gpt_5_4_mini", "GPT-5.4 mini", "#287271"),
            ("gpt_5_4", "GPT-5.4", "#E07A5F"),
        ]
    ):
        values = [
            output["summaries"][model]["rag"][metric]["rate"]
            for metric, _ in metrics
        ]
        ax.bar(x + (index - 0.5) * width, values, width, label=label, color=color)
    ax.set_xticks(x, [label for _, label in metrics])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction of 32 paired RAG cases")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    target = Path("reports/comprehensive_evaluation/figures")
    target.mkdir(parents=True, exist_ok=True)
    fig.savefig(target / "llm_model_sensitivity.pdf", bbox_inches="tight")
    plt.close(fig)


def run_model_comparison(
    primary_config_path: str | Path,
    sensitivity_config_path: str | Path,
) -> dict[str, Any]:
    primary = load_json(primary_config_path)
    sensitivity = load_json(sensitivity_config_path)
    primary_run = Path("experiments/runs") / primary["planning"]["run_id"] / "results.jsonl"
    sensitivity_run = (
        Path("experiments/runs")
        / sensitivity["planning"]["run_id"]
        / "results.jsonl"
    )
    primary_rows = [row for row in read_jsonl(primary_run) if "error" not in row]
    sensitivity_rows = [
        row for row in read_jsonl(sensitivity_run) if "error" not in row
    ]
    selected_ids = {
        row["case_id"] for row in read_jsonl(sensitivity["planning"]["cases_path"])
    }
    primary_rows = [row for row in primary_rows if row["case_id"] in selected_ids]
    conditions = list(sensitivity["planning"]["conditions"])
    models = {
        "gpt_5_4_mini": primary_rows,
        "gpt_5_4": sensitivity_rows,
    }

    summaries: dict[str, Any] = {}
    csv_rows = []
    for model_name, records in models.items():
        summaries[model_name] = {}
        for condition in conditions:
            rows = [row for row in records if row["condition"] == condition]
            metrics = {
                name: endpoint_summary(rows, getter) for name, getter in ENDPOINTS
            }
            metrics["mean_llm_seconds"] = float(
                np.mean([row["latency_seconds"]["llm"] for row in rows])
            ) if rows else None
            metrics["estimated_cost_usd"] = float(
                sum(row["usage"]["estimated_cost_usd"] for row in rows)
            )
            summaries[model_name][condition] = metrics
            for endpoint, values in metrics.items():
                if isinstance(values, dict) and "rate" in values:
                    csv_rows.append(
                        {
                            "model": model_name,
                            "condition": condition,
                            "endpoint": endpoint,
                            "successes": values["successes"],
                            "total": values["total"],
                            "rate": values["rate"],
                            "ci_low": values["wilson_95"][0],
                            "ci_high": values["wilson_95"][1],
                        }
                    )

    primary_index = {
        (row["case_id"], row["condition"]): row for row in primary_rows
    }
    sensitivity_index = {
        (row["case_id"], row["condition"]): row for row in sensitivity_rows
    }
    paired_tests: dict[str, Any] = {}
    action_agreement: dict[str, Any] = {}
    for condition in conditions:
        common_ids = sorted(
            {
                case_id
                for case_id, row_condition in primary_index
                if row_condition == condition
            }
            & {
                case_id
                for case_id, row_condition in sensitivity_index
                if row_condition == condition
            }
        )
        paired_tests[condition] = {}
        for name, getter in ENDPOINTS:
            left = {
                case_id: bool(getter(primary_index[(case_id, condition)]))
                for case_id in common_ids
            }
            right = {
                case_id: bool(getter(sensitivity_index[(case_id, condition)]))
                for case_id in common_ids
            }
            paired_tests[condition][name] = exact_mcnemar(left, right)
        similarities = [
            jaccard(
                action_names(primary_index[(case_id, condition)]),
                action_names(sensitivity_index[(case_id, condition)]),
            )
            for case_id in common_ids
        ]
        action_agreement[condition] = {
            "paired_cases": len(common_ids),
            "mean_action_set_jaccard": float(np.mean(similarities))
            if similarities
            else None,
            "exact_action_set_matches": int(sum(value == 1.0 for value in similarities)),
        }

    output = {
        "prespecified_cases": len(selected_ids),
        "conditions": conditions,
        "models": {
            "gpt_5_4_mini": primary["planning"].get(
                "model", load_json(primary["base_config"])["agent"]["model"]
            ),
            "gpt_5_4": sensitivity["planning"]["model"],
        },
        "summaries": summaries,
        "paired_exact_mcnemar_tests": paired_tests,
        "normalized_action_set_agreement": action_agreement,
        "interpretation_guardrail": (
            "This bounded sensitivity analysis checks whether structural, evidence, and "
            "policy findings persist across two model capacities. It does not establish "
            "that either model's plans are operationally superior without human review."
        ),
    }
    output_dir = Path("reports/comprehensive_evaluation/tables")
    write_json(output_dir / "model_sensitivity_comparison.json", output)
    pd.DataFrame(csv_rows).to_csv(
        output_dir / "model_sensitivity_comparison.csv", index=False
    )
    plot_model_comparison(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the primary and stronger-model planning runs."
    )
    parser.add_argument("--primary", default="configs/planning_study_160_alerts.json")
    parser.add_argument(
        "--sensitivity", default="configs/planner_model_sensitivity.json"
    )
    args = parser.parse_args()
    print(json.dumps(run_model_comparison(args.primary, args.sensitivity), indent=2))


if __name__ == "__main__":
    main()
