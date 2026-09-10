from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from .common import write_json


PLAN_RATINGS = ["appropriate_1_to_5", "conservative_1_to_5", "useful_1_to_5"]
PLAN_CATEGORIES = ["unsafe_or_incompatible"]
EVIDENCE_CATEGORIES = [
    "support_label_direct_general_unsupported",
    "action_appropriate_yes_no_unclear",
]


def complete_pairs(
    left: pd.DataFrame, right: pd.DataFrame, column: str
) -> tuple[pd.Series, pd.Series]:
    paired = left[["audit_id", column]].merge(
        right[["audit_id", column]], on="audit_id", suffixes=("_A", "_B")
    )
    paired = paired.dropna()
    paired = paired.loc[
        paired[f"{column}_A"].astype(str).str.strip().ne("")
        & paired[f"{column}_B"].astype(str).str.strip().ne("")
    ]
    return paired[f"{column}_A"], paired[f"{column}_B"]


def agreement(left: pd.DataFrame, right: pd.DataFrame, column: str, ordinal: bool) -> dict[str, Any]:
    a, b = complete_pairs(left, right, column)
    if not len(a):
        return {"paired_labels": 0, "status": "incomplete"}
    weights = "quadratic" if ordinal else None
    return {
        "paired_labels": len(a),
        "exact_agreement": float((a.astype(str) == b.astype(str)).mean()),
        "cohen_kappa": float(cohen_kappa_score(a, b, weights=weights)),
        "kappa_weights": weights or "unweighted",
    }


def analyze_human_audit(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    plan_a = pd.read_csv(root / "reviewer_A_plan_audit.csv")
    plan_b = pd.read_csv(root / "reviewer_B_plan_audit.csv")
    evidence_a = pd.read_csv(root / "reviewer_A_evidence_audit.csv")
    evidence_b = pd.read_csv(root / "reviewer_B_evidence_audit.csv")
    output = {
        "plan_agreement": {
            column: agreement(plan_a, plan_b, column, ordinal=True)
            for column in PLAN_RATINGS
        }
        | {
            column: agreement(plan_a, plan_b, column, ordinal=False)
            for column in PLAN_CATEGORIES
        },
        "evidence_agreement": {
            column: agreement(evidence_a, evidence_b, column, ordinal=False)
            for column in EVIDENCE_CATEGORIES
        },
        "status": (
            "Agreement is computed only from nonblank labels entered independently by "
            "the two human reviewers. Condition keys must remain unopened until this step."
        ),
    }
    write_json(root / "inter_reviewer_agreement.json", output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure agreement between two completed blinded human audits."
    )
    parser.add_argument(
        "--directory", default="reports/journal_extension/human_audit"
    )
    args = parser.parse_args()
    print(json.dumps(analyze_human_audit(args.directory), indent=2))


if __name__ == "__main__":
    main()
