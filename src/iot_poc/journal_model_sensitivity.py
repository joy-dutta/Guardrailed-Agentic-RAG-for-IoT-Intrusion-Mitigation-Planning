from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import load_json, read_jsonl, stable_seed, write_json, write_jsonl


STRATA = [
    "correct_qualified",
    "correct_escalated",
    "error_qualified",
    "error_escalated",
]


def select_sensitivity_cases(
    cases: list[dict[str, Any]], cases_per_family: int, seed: int
) -> list[dict[str, Any]]:
    """Select a family-balanced, uncertainty-diverse subset before comparison."""
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_family[str(case["evaluation"]["true_family"])].append(case)

    selected: list[dict[str, Any]] = []
    for family in sorted(by_family):
        family_cases = by_family[family]
        chosen: list[dict[str, Any]] = []
        chosen_ids: set[str] = set()

        for stratum in STRATA:
            candidates = [
                case
                for case in family_cases
                if case["evaluation"]["selection_stratum"] == stratum
            ]
            random.Random(stable_seed(f"model:{family}:{stratum}", seed)).shuffle(
                candidates
            )
            if candidates and len(chosen) < cases_per_family:
                chosen.append(candidates[0])
                chosen_ids.add(str(candidates[0]["case_id"]))

        remaining = [
            case for case in family_cases if str(case["case_id"]) not in chosen_ids
        ]
        random.Random(stable_seed(f"model:{family}:fill", seed)).shuffle(remaining)
        chosen.extend(remaining[: cases_per_family - len(chosen)])
        if len(chosen) != cases_per_family:
            raise ValueError(
                f"Could not select {cases_per_family} cases for true family {family}."
            )
        selected.extend(chosen)

    return sorted(selected, key=lambda case: str(case["case_id"]))


def build_sensitivity_cases(config_path: str | Path) -> list[dict[str, Any]]:
    config = load_json(config_path)
    base = load_json(config["base_config"])
    planning = config["planning"]
    source = read_jsonl(planning["source_cases_path"])
    selected = select_sensitivity_cases(
        source,
        int(planning["cases_per_true_family"]),
        int(base["seed"]),
    )
    write_jsonl(planning["cases_path"], selected)

    family_counts: dict[str, int] = defaultdict(int)
    stratum_counts: dict[str, int] = defaultdict(int)
    for case in selected:
        family_counts[str(case["evaluation"]["true_family"])] += 1
        stratum_counts[str(case["evaluation"]["selection_stratum"])] += 1
    audit = {
        "selection_time": "prespecified before the primary model outcomes were analyzed",
        "source_cases_path": str(planning["source_cases_path"]),
        "cases_path": str(planning["cases_path"]),
        "seed": int(base["seed"]),
        "cases": len(selected),
        "cases_per_true_family": dict(sorted(family_counts.items())),
        "selection_strata": dict(sorted(stratum_counts.items())),
        "conditions": list(planning["conditions"]),
        "planned_calls": len(selected) * len(planning["conditions"]),
        "model": str(planning["model"]),
        "hard_call_cap": int(planning["max_calls"]),
        "hard_cost_cap_usd": float(planning["max_cost_usd"]),
        "purpose": (
            "A bounded sensitivity check of whether the main RAG, evidence, and "
            "guardrail findings persist with a stronger general-purpose model."
        ),
    }
    write_json(
        "reports/journal_extension/tables/gpt54_sensitivity_case_audit.json",
        audit,
    )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the prespecified GPT-5.4 model-sensitivity subset."
    )
    parser.add_argument(
        "--config", default="configs/ieee_access_model_sensitivity.json"
    )
    args = parser.parse_args()
    cases = build_sensitivity_cases(args.config)
    print(json.dumps({"prepared_cases": len(cases)}, indent=2))


if __name__ == "__main__":
    main()
