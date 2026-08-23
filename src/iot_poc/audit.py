from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from .common import load_json, write_json


def apply_retrieval_judgments(
    candidates_path: str | Path,
    judgments_path: str | Path,
) -> dict[str, Any]:
    candidates = load_json(candidates_path)
    judgment_document = load_json(judgments_path)
    lookup = {
        (row["family"], row["chunk_id"]): row
        for row in judgment_document["judgments"]
    }
    audited = []
    for candidate in candidates:
        key = (candidate["predicted_family"], candidate["chunk_id"])
        if key not in lookup:
            raise KeyError(f"No manual judgment for {key}")
        judgment = lookup[key]
        audited.append(
            {
                **candidate,
                "manual_label": judgment["label"],
                "manual_note": judgment["note"],
            }
        )

    labels = Counter(row["manual_label"] for row in audited)
    relevant_labels = {"direct", "supporting"}
    case_ids = sorted({row["case_id"] for row in audited})
    top_rank = [row for row in audited if row["rank"] == 1]
    cases_with_relevant = [
        case_id
        for case_id in case_ids
        if any(
            row["manual_label"] in relevant_labels
            for row in audited
            if row["case_id"] == case_id
        )
    ]
    family_counts: dict[str, Counter] = {}
    for row in audited:
        family_counts.setdefault(row["predicted_family"], Counter())[row["manual_label"]] += 1

    total = len(audited)
    relevant = labels["direct"] + labels["supporting"]
    summary = {
        "audited_cases": len(case_ids),
        "audited_chunks": total,
        "label_counts": dict(labels),
        "relevant_chunks": relevant,
        "relevant_chunk_rate": relevant / total,
        "direct_chunk_rate": labels["direct"] / total,
        "top_1_relevance_rate": sum(
            row["manual_label"] in relevant_labels for row in top_rank
        )
        / len(top_rank),
        "cases_with_at_least_one_relevant_chunk": len(cases_with_relevant),
        "case_hit_rate": len(cases_with_relevant) / len(case_ids),
        "by_family": {
            family: dict(counts) for family, counts in sorted(family_counts.items())
        },
        "rubric": judgment_document["rubric"],
        "review_status": judgment_document["review_status"],
    }
    write_json("reports/tables/retrieval_audit_labeled.json", audited)
    write_json("reports/tables/retrieval_audit_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the frozen manual retrieval judgments.")
    parser.add_argument(
        "--candidates", default="reports/tables/retrieval_audit_candidates.json"
    )
    parser.add_argument(
        "--judgments",
        default="docs/experiment_protocol/retrieval_audit_judgments.json",
    )
    args = parser.parse_args()
    summary = apply_retrieval_judgments(args.candidates, args.judgments)
    print(summary)


if __name__ == "__main__":
    main()
