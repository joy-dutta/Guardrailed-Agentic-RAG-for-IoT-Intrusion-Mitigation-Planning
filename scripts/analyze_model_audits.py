from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact, friedmanchisquare, spearmanr, wilcoxon
from sklearn.metrics import cohen_kappa_score


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "journal_extension"
MODEL_DIR = REPORT_ROOT / "model_audit"
BLIND_DIR = REPORT_ROOT / "human_audit"

PLAN_RATINGS = ["appropriate_1_to_5", "conservative_1_to_5", "useful_1_to_5"]
PLAN_JUDGMENTS = PLAN_RATINGS + ["unsafe_or_incompatible", "reviewer_note"]
EVIDENCE_JUDGMENTS = [
    "support_label_direct_general_unsupported",
    "action_appropriate_yes_no_unclear",
    "reviewer_note",
]


def native(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    return value


def kappa(left: pd.Series, right: pd.Series, weights: str | None = None) -> float | None:
    value = cohen_kappa_score(left, right, weights=weights)
    return None if np.isnan(value) else float(value)


def merge_judgments(
    master: pd.DataFrame,
    judgments: pd.DataFrame,
    columns: list[str],
    expected_rows: int,
) -> pd.DataFrame:
    if len(master) != expected_rows or len(judgments) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows in both files")
    if master["audit_id"].duplicated().any() or judgments["audit_id"].duplicated().any():
        raise ValueError("Duplicate audit IDs found")
    if master["audit_id"].tolist() != judgments["audit_id"].tolist():
        raise ValueError("Judgment IDs do not exactly match the blinded master order")
    missing = judgments[columns].isna().sum().sum()
    if missing:
        raise ValueError(f"Judgment file contains {missing} missing values")
    completed = master.copy()
    for column in columns:
        completed[column] = judgments[column].to_numpy()
    return completed


def ordinal_agreement(left: pd.Series, right: pd.Series) -> dict[str, Any]:
    a = left.astype(int)
    b = right.astype(int)
    difference = (a - b).abs()
    rho = spearmanr(a, b).statistic
    return {
        "n": len(a),
        "exact_agreement": float((a == b).mean()),
        "within_one_point": float((difference <= 1).mean()),
        "mean_absolute_difference": float(difference.mean()),
        "quadratic_weighted_kappa": kappa(a, b, weights="quadratic"),
        "spearman_rho": None if np.isnan(rho) else float(rho),
        "reviewer_A_mean": float(a.mean()),
        "reviewer_B_mean": float(b.mean()),
    }


def categorical_agreement(left: pd.Series, right: pd.Series) -> dict[str, Any]:
    a = left.astype(str).str.strip().str.lower()
    b = right.astype(str).str.strip().str.lower()
    return {
        "n": len(a),
        "exact_agreement": float((a == b).mean()),
        "cohen_kappa": kappa(a, b),
        "reviewer_A_counts": a.value_counts().to_dict(),
        "reviewer_B_counts": b.value_counts().to_dict(),
    }


def holm_adjust(values: list[float]) -> list[float]:
    order = np.argsort(values)
    adjusted = np.zeros(len(values), dtype=float)
    previous = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (len(values) - rank) * values[index])
        previous = max(previous, candidate)
        adjusted[index] = previous
    return adjusted.tolist()


def plan_tests(frame: pd.DataFrame) -> dict[str, Any]:
    conditions = ["no_rag", "policy_only", "rag"]
    pairs = [("rag", "no_rag"), ("rag", "policy_only"), ("no_rag", "policy_only")]
    output: dict[str, Any] = {}
    for metric in PLAN_RATINGS:
        pivot = frame.pivot(index="case_id", columns="condition", values=metric)[conditions]
        omnibus = friedmanchisquare(*(pivot[condition] for condition in conditions))
        comparisons = []
        raw_p = []
        for left, right in pairs:
            difference = pivot[left] - pivot[right]
            test = wilcoxon(
                pivot[left], pivot[right], zero_method="pratt", method="approx"
            )
            raw_p.append(float(test.pvalue))
            comparisons.append(
                {
                    "left": left,
                    "right": right,
                    "mean_difference": float(difference.mean()),
                    "left_higher": int((difference > 0).sum()),
                    "ties": int((difference == 0).sum()),
                    "left_lower": int((difference < 0).sum()),
                    "wilcoxon_p_raw": float(test.pvalue),
                }
            )
        for comparison, adjusted in zip(comparisons, holm_adjust(raw_p), strict=True):
            comparison["wilcoxon_p_holm"] = adjusted
        output[metric] = {
            "friedman_statistic": float(omnibus.statistic),
            "friedman_p": float(omnibus.pvalue),
            "pairwise": comparisons,
        }
    return output


def summarize_plan(frame: pd.DataFrame, reviewer: str) -> pd.DataFrame:
    rows = []
    for condition, group in frame.groupby("condition", sort=True):
        for metric in PLAN_RATINGS:
            rows.append(
                {
                    "reviewer": reviewer,
                    "condition": condition,
                    "metric": metric,
                    "n": len(group),
                    "mean": group[metric].mean(),
                    "median": group[metric].median(),
                    "score_4_or_5_percent": 100 * group[metric].ge(4).mean(),
                    "unsafe_count": group["unsafe_or_incompatible"]
                    .astype(str)
                    .str.lower()
                    .eq("yes")
                    .sum(),
                }
            )
    return pd.DataFrame(rows)


def summarize_evidence(frame: pd.DataFrame, reviewer: str) -> pd.DataFrame:
    rows = []
    for condition, group in frame.groupby("condition", sort=True):
        support = group["support_label_direct_general_unsupported"].str.lower()
        action = group["action_appropriate_yes_no_unclear"].str.lower()
        rows.append(
            {
                "reviewer": reviewer,
                "condition": condition,
                "n": len(group),
                "direct": int(support.eq("direct").sum()),
                "general": int(support.eq("general").sum()),
                "unsupported": int(support.eq("unsupported").sum()),
                "action_yes": int(action.eq("yes").sum()),
                "action_no": int(action.eq("no").sum()),
                "action_unclear": int(action.eq("unclear").sum()),
            }
        )
    return pd.DataFrame(rows)


def evidence_test(frame: pd.DataFrame) -> dict[str, Any]:
    support = frame["support_label_direct_general_unsupported"].str.lower()
    conditions = frame["condition"]
    contingency = pd.crosstab(conditions, support).reindex(
        index=["rag", "mismatched_rag"],
        columns=["direct", "general", "unsupported"],
        fill_value=0,
    )
    nonzero = contingency.loc[:, contingency.sum(axis=0).gt(0)]
    chi2, chi2_p, _, _ = chi2_contingency(nonzero)
    unsupported = np.array(
        [
            [contingency.loc["rag", "unsupported"], contingency.loc["rag"].sum() - contingency.loc["rag", "unsupported"]],
            [contingency.loc["mismatched_rag", "unsupported"], contingency.loc["mismatched_rag"].sum() - contingency.loc["mismatched_rag", "unsupported"]],
        ]
    )
    odds, fisher_p = fisher_exact(unsupported)
    return {
        "support_contingency": contingency.to_dict(orient="index"),
        "chi_square": float(chi2),
        "chi_square_p": float(chi2_p),
        "unsupported_vs_other_table": unsupported.tolist(),
        "fisher_odds_ratio": float(odds),
        "fisher_p": float(fisher_p),
        "note": "The 64 items per condition were sampled independently, so this is an unpaired comparison.",
    }


def note_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    counts = frame["reviewer_note"].fillna("").value_counts()
    return {
        "rows": len(frame),
        "unique_notes_including_blank": int(len(counts)),
        "blank_notes": int(frame["reviewer_note"].fillna("").eq("").sum()),
        "largest_repeated_note_count": int(counts.iloc[0]),
        "largest_repeated_note_fraction": float(counts.iloc[0] / len(frame)),
    }


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    plan_master = pd.read_csv(BLIND_DIR / "reviewer_B_plan_audit.csv")
    evidence_master = pd.read_csv(BLIND_DIR / "reviewer_B_evidence_audit.csv")
    plan_b_judgments = pd.read_csv(MODEL_DIR / "gemini_B_plan_judgments_final.csv")
    evidence_b_judgments = pd.read_csv(MODEL_DIR / "gemini_B_evidence_judgments_final.csv")
    plan_b = merge_judgments(plan_master, plan_b_judgments, PLAN_JUDGMENTS, 192)
    evidence_b = merge_judgments(evidence_master, evidence_b_judgments, EVIDENCE_JUDGMENTS, 128)
    plan_b.to_csv(MODEL_DIR / "gemini_B_plan_completed.csv", index=False)
    evidence_b.to_csv(MODEL_DIR / "gemini_B_evidence_completed.csv", index=False)

    plan_a = pd.read_csv(MODEL_DIR / "chatgpt_A_plan_completed.csv")
    evidence_a = pd.read_csv(MODEL_DIR / "chatgpt_A_evidence_completed.csv")
    plan_pair = plan_a.merge(plan_b_judgments, on="audit_id", suffixes=("_A", "_B"), validate="one_to_one")
    evidence_pair = evidence_a.merge(
        evidence_b_judgments, on="audit_id", suffixes=("_A", "_B"), validate="one_to_one"
    )
    agreement = {
        "reviewer_A": "GPT-5.6 Sol Ultra",
        "reviewer_B": "Gemini Pro Extended",
        "audit_type": "independent model-based audit; not human validation",
        "plan": {
            metric: ordinal_agreement(plan_pair[f"{metric}_A"], plan_pair[f"{metric}_B"])
            for metric in PLAN_RATINGS
        }
        | {
            "unsafe_or_incompatible": categorical_agreement(
                plan_pair["unsafe_or_incompatible_A"], plan_pair["unsafe_or_incompatible_B"]
            )
        },
        "evidence": {
            column: categorical_agreement(evidence_pair[f"{column}_A"], evidence_pair[f"{column}_B"])
            for column in EVIDENCE_JUDGMENTS[:2]
        },
        "note_diagnostics": {
            "reviewer_A_plan": note_diagnostics(plan_a),
            "reviewer_B_plan": note_diagnostics(plan_b_judgments),
            "reviewer_A_evidence": note_diagnostics(evidence_a),
            "reviewer_B_evidence": note_diagnostics(evidence_b_judgments),
        },
    }
    (MODEL_DIR / "inter_model_agreement.json").write_text(
        json.dumps(native(agreement), indent=2), encoding="utf-8"
    )

    # Conditions are opened only after the independent agreement calculation above.
    plan_key = pd.read_csv(BLIND_DIR / "plan_audit_key.csv")
    evidence_key = pd.read_csv(BLIND_DIR / "evidence_audit_key.csv")
    plan_a_keyed = plan_a.merge(plan_key, on="audit_id", validate="one_to_one")
    plan_b_keyed = plan_b.merge(plan_key, on="audit_id", validate="one_to_one")
    evidence_a_keyed = evidence_a.merge(evidence_key, on="audit_id", validate="one_to_one")
    evidence_b_keyed = evidence_b.merge(evidence_key, on="audit_id", validate="one_to_one")

    plan_summary = pd.concat(
        [
            summarize_plan(plan_a_keyed, "GPT-5.6 Sol Ultra"),
            summarize_plan(plan_b_keyed, "Gemini Pro Extended"),
        ],
        ignore_index=True,
    )
    evidence_summary = pd.concat(
        [
            summarize_evidence(evidence_a_keyed, "GPT-5.6 Sol Ultra"),
            summarize_evidence(evidence_b_keyed, "Gemini Pro Extended"),
        ],
        ignore_index=True,
    )
    plan_summary.to_csv(MODEL_DIR / "plan_condition_summary.csv", index=False)
    evidence_summary.to_csv(MODEL_DIR / "evidence_condition_summary.csv", index=False)

    joined_evidence = evidence_a_keyed[
        ["audit_id", "condition", "support_label_direct_general_unsupported"]
    ].merge(
        evidence_b_keyed[["audit_id", "support_label_direct_general_unsupported"]],
        on="audit_id",
        suffixes=("_A", "_B"),
        validate="one_to_one",
    )
    consensus = {}
    for condition, group in joined_evidence.groupby("condition"):
        a_unsupported = group["support_label_direct_general_unsupported_A"].str.lower().eq("unsupported")
        b_unsupported = group["support_label_direct_general_unsupported_B"].str.lower().eq("unsupported")
        consensus[condition] = {
            "n": len(group),
            "both_unsupported": int((a_unsupported & b_unsupported).sum()),
            "either_unsupported": int((a_unsupported | b_unsupported).sum()),
            "support_exact_agreement": float(
                (
                    group["support_label_direct_general_unsupported_A"].str.lower()
                    == group["support_label_direct_general_unsupported_B"].str.lower()
                ).mean()
            ),
        }

    rag_consensus = consensus["rag"]
    mismatch_consensus = consensus["mismatched_rag"]
    both_table = [
        [rag_consensus["both_unsupported"], rag_consensus["n"] - rag_consensus["both_unsupported"]],
        [mismatch_consensus["both_unsupported"], mismatch_consensus["n"] - mismatch_consensus["both_unsupported"]],
    ]
    either_table = [
        [rag_consensus["either_unsupported"], rag_consensus["n"] - rag_consensus["either_unsupported"]],
        [mismatch_consensus["either_unsupported"], mismatch_consensus["n"] - mismatch_consensus["either_unsupported"]],
    ]
    consensus_tests = {
        "both_reviewers_unsupported": {
            "table_rag_then_mismatched": both_table,
            "fisher_p": float(fisher_exact(both_table).pvalue),
        },
        "either_reviewer_unsupported": {
            "table_rag_then_mismatched": either_table,
            "fisher_p": float(fisher_exact(either_table).pvalue),
        },
    }

    condition_analysis = {
        "plan_tests": {
            "GPT-5.6 Sol Ultra": plan_tests(plan_a_keyed),
            "Gemini Pro Extended": plan_tests(plan_b_keyed),
        },
        "evidence_tests": {
            "GPT-5.6 Sol Ultra": evidence_test(evidence_a_keyed),
            "Gemini Pro Extended": evidence_test(evidence_b_keyed),
        },
        "cross_reviewer_unsupported_consensus": consensus,
        "cross_reviewer_unsupported_tests": consensus_tests,
    }
    (MODEL_DIR / "condition_analysis.json").write_text(
        json.dumps(native(condition_analysis), indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
