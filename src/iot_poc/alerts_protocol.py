from __future__ import annotations

import argparse

from .alerts import build_cases_from_predictions
from .common import load_json


def build_attack_type_aware_cases() -> list[dict]:
    detector_results = load_json("reports/tables/detector_split_protocols.json")
    threshold = float(detector_results["attack_type_aware"]["selected_threshold"])
    return build_cases_from_predictions(
        predictions_path="data/processed/test_predictions_protocol_attack_type_aware.csv",
        threshold=threshold,
        model_name="random_forest_leakage_controlled_attack_type_aware",
        output_path="data/processed/agent_cases_attack_type_aware.jsonl",
        case_prefix="iot-v2",
    )


def main() -> None:
    argparse.ArgumentParser(
        description="Build fixed agent cases from the attack-type-aware detector."
    ).parse_args()
    cases = build_attack_type_aware_cases()
    print(f"Prepared {len(cases)} attack-type-aware agent cases.")


if __name__ == "__main__":
    main()
