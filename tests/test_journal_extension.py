import numpy as np
import pandas as pd

from iot_poc.journal_calibration import area_under_risk_coverage, validation_selected_runs
from iot_poc.journal_cases import select_balanced_cases
from iot_poc.journal_model_sensitivity import select_sensitivity_cases
from iot_poc.journal_statistics import exact_mcnemar, wilson_interval


def test_area_under_risk_coverage_rewards_confident_correct_predictions() -> None:
    true = np.asarray(["A", "A", "B", "B"])
    predicted = np.asarray(["A", "A", "B", "A"])
    good_order = np.asarray([[0.99, 0.01], [0.9, 0.1], [0.1, 0.9], [0.6, 0.4]])
    bad_order = np.asarray([[0.6, 0.4], [0.55, 0.45], [0.45, 0.55], [0.99, 0.01]])
    assert area_under_risk_coverage(true, predicted, good_order) < area_under_risk_coverage(
        true, predicted, bad_order
    )


def test_balanced_case_selection_has_no_duplicate_rows() -> None:
    rows = []
    for family in ["A", "B"]:
        for index in range(40):
            rows.append(
                {
                    "family": family,
                    "correct": index % 2 == 0,
                    "calibrated_confidence": 0.9 if index % 4 < 2 else 0.4,
                    "predicted_family": family,
                }
            )
    selected = select_balanced_cases(pd.DataFrame(rows), 0.8, 20, 42)
    assert len(selected) == 40
    assert not selected.index.duplicated().any()
    assert selected.groupby("family").size().to_dict() == {"A": 20, "B": 20}


def test_wilson_interval_and_exact_pairing() -> None:
    lower, upper = wilson_interval(8, 10)
    assert lower < 0.8 < upper
    result = exact_mcnemar(
        {"a": True, "b": True, "c": False},
        {"a": False, "b": True, "c": False},
    )
    assert result["left_only"] == 1
    assert result["right_only"] == 0
    assert result["two_sided_exact_p"] == 1.0


def test_calibration_method_selection_uses_validation_ece() -> None:
    rows = [
        {
            "seed": 1,
            "method": "raw",
            "threshold_validation_metrics": {"ece_15_bin": 0.1, "multiclass_brier": 0.2},
        },
        {
            "seed": 1,
            "method": "isotonic",
            "threshold_validation_metrics": {"ece_15_bin": 0.05, "multiclass_brier": 0.3},
        },
    ]
    assert validation_selected_runs(rows)[0]["method"] == "isotonic"


def test_model_sensitivity_selection_is_balanced_and_deterministic() -> None:
    cases = []
    for family in ["DDoS", "DoS"]:
        for index, stratum in enumerate(
            [
                "correct_qualified",
                "correct_escalated",
                "error_qualified",
                "error_escalated",
                "correct_qualified",
            ]
        ):
            cases.append(
                {
                    "case_id": f"{family}-{index}",
                    "evaluation": {
                        "true_family": family,
                        "selection_stratum": stratum,
                    },
                }
            )
    first = select_sensitivity_cases(cases, cases_per_family=4, seed=7)
    second = select_sensitivity_cases(cases, cases_per_family=4, seed=7)
    assert first == second
    assert len(first) == 8
    assert {case["evaluation"]["true_family"] for case in first} == {
        "DDoS",
        "DoS",
    }
