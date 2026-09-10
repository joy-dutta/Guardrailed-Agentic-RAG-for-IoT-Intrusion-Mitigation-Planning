from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import pandas as pd

from .common import load_json, read_jsonl, stable_seed


def compact_plan(intent: dict[str, Any]) -> str:
    return json.dumps(
        [
            {
                "action": action["action"],
                "parameters": action["parameters"],
                "duration_seconds": action["duration_seconds"],
                "approval_required": action["approval_required"],
                "rationale": action["rationale"],
            }
            for action in intent.get("actions", [])
        ],
        ensure_ascii=True,
    )


def choose_cases(records: list[dict[str, Any]], per_family: int, seed: int) -> list[str]:
    rag = [row for row in records if row["condition"] == "rag"]
    selected = []
    for family in sorted({row["evaluation"]["true_family"] for row in rag}):
        rows = [row for row in rag if row["evaluation"]["true_family"] == family]
        random.Random(stable_seed(f"human:{family}", seed)).shuffle(rows)
        selected.extend(row["case_id"] for row in rows[:per_family])
    return selected


def build_human_packets(config_path: str | Path) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    planning = extension["planning"]
    audit_config = extension["human_audit"]
    run_path = Path("experiments/runs") / str(planning["run_id"]) / "results.jsonl"
    records = [row for row in read_jsonl(run_path) if "error" not in row]
    policy_rows = {
        row["case_id"]: row
        for row in read_jsonl(
            "reports/comprehensive_evaluation/tables/policy_only_baseline_records.jsonl"
        )
    }
    selected_cases = choose_cases(
        records,
        int(audit_config["cases_per_true_family"]),
        int(base["seed"]),
    )

    plan_rows = []
    plan_key = []
    record_index = {(row["case_id"], row["condition"]): row for row in records}
    for case_id in selected_cases:
        rag = record_index[(case_id, "rag")]
        candidates = [
            ("rag", rag["normalized_intent"]),
            ("no_rag", record_index[(case_id, "no_rag")]["normalized_intent"]),
            ("policy_only", policy_rows[case_id]["policy_only_intent"]),
        ]
        random.Random(stable_seed(f"plans:{case_id}", int(base["seed"]))).shuffle(candidates)
        for position, (condition, intent) in enumerate(candidates, start=1):
            audit_id = f"PLAN-{len(plan_rows) + 1:04d}"
            plan_rows.append(
                {
                    "audit_id": audit_id,
                    "case_group": case_id,
                    "candidate": chr(64 + position),
                    "predicted_family": rag["alert"]["detector"]["predicted_family"],
                    "confidence": rag["alert"]["detector"]["calibrated_confidence"],
                    "route": rag["alert"]["routing_decision"],
                    "traffic_observations": json.dumps(rag["alert"]["observations"]),
                    "proposed_plan": compact_plan(intent),
                    "appropriate_1_to_5": "",
                    "conservative_1_to_5": "",
                    "useful_1_to_5": "",
                    "unsafe_or_incompatible": "",
                    "reviewer_note": "",
                }
            )
            plan_key.append(
                {
                    "audit_id": audit_id,
                    "case_id": case_id,
                    "condition": condition,
                    "true_family_for_analysis_only": rag["evaluation"]["true_family"],
                }
            )

    evidence_candidates = []
    for condition in ["rag", "mismatched_rag"]:
        for row in records:
            if row["condition"] != condition:
                continue
            excerpts = {item["chunk_id"]: item for item in row["evidence"]}
            cited = row["raw_intent"].get("evidence_used", [])
            cited = cited if isinstance(cited, list) else []
            for action in row["raw_intent"].get("recommended_actions", []):
                if not isinstance(action, dict):
                    continue
                evidence_candidates.append(
                    {
                        "condition": condition,
                        "case_id": row["case_id"],
                        "predicted_family": row["alert"]["detector"]["predicted_family"],
                        "action": action.get("action", ""),
                        "rationale": action.get("rationale", ""),
                        "evidence": [excerpts[item] for item in cited if item in excerpts],
                    }
                )
    evidence_rows = []
    evidence_key = []
    per_condition = int(audit_config["evidence_items_per_condition"])
    for condition in ["rag", "mismatched_rag"]:
        candidates = [item for item in evidence_candidates if item["condition"] == condition]
        random.Random(stable_seed(f"evidence:{condition}", int(base["seed"]))).shuffle(candidates)
        for item in candidates[:per_condition]:
            audit_id = f"EVID-{len(evidence_rows) + 1:04d}"
            evidence_rows.append(
                {
                    "audit_id": audit_id,
                    "predicted_family": item["predicted_family"],
                    "action": item["action"],
                    "rationale": item["rationale"],
                    "cited_evidence": json.dumps(item["evidence"], ensure_ascii=True),
                    "support_label_direct_general_unsupported": "",
                    "action_appropriate_yes_no_unclear": "",
                    "reviewer_note": "",
                }
            )
            evidence_key.append(
                {
                    "audit_id": audit_id,
                    "case_id": item["case_id"],
                    "condition": condition,
                }
            )
    random.Random(int(base["seed"])).shuffle(evidence_rows)

    output_dir = Path("reports/comprehensive_evaluation/human_audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_frame = pd.DataFrame(plan_rows)
    evidence_frame = pd.DataFrame(evidence_rows)
    plan_frame.to_csv(output_dir / "plan_audit_blind.csv", index=False)
    plan_frame.to_csv(output_dir / "reviewer_A_plan_audit.csv", index=False)
    plan_frame.to_csv(output_dir / "reviewer_B_plan_audit.csv", index=False)
    pd.DataFrame(plan_key).to_csv(output_dir / "plan_audit_key.csv", index=False)
    evidence_frame.to_csv(output_dir / "evidence_audit_blind.csv", index=False)
    evidence_frame.to_csv(output_dir / "reviewer_A_evidence_audit.csv", index=False)
    evidence_frame.to_csv(output_dir / "reviewer_B_evidence_audit.csv", index=False)
    pd.DataFrame(evidence_key).to_csv(output_dir / "evidence_audit_key.csv", index=False)
    summary = {
        "plan_cases": len(selected_cases),
        "plan_candidates": len(plan_rows),
        "evidence_items": len(evidence_rows),
        "required_human_reviewers": 2,
        "status": "Packets prepared; no human labels have been entered.",
    }
    Path(output_dir / "README.md").write_text(
        "# Blinded Human Audit\n\n"
        "Reviewer A and Reviewer B should complete only the two files carrying their "
        "reviewer letter, without opening either key file. They score every item "
        "independently. The generic files ending in `blind.csv` are clean master copies. After "
        "both reviews are complete, compute agreement before discussing disagreements, then "
        "adjudicate disagreements in a separate column. Blank cells are not negative labels; "
        "they mean the audit is unfinished. The dataset true label is excluded from the blind "
        "packet because the planner never receives it.\n\n"
        "## Plan scores\n\n"
        "Use integers from 1 (clearly poor) to 5 (clearly strong) for `appropriate`, "
        "`conservative`, and `useful`. Appropriate means suitable for the predicted traffic "
        "family and observations. Conservative means the plan avoids unnecessary disruption "
        "and asks for approval when needed. Useful means an operator could act on the intent "
        "after normal site-specific checks. Mark `unsafe_or_incompatible` yes only when an "
        "included action would be unsafe or incompatible with the alert as shown.\n\n"
        "## Evidence scores\n\n"
        "Mark support as `direct` when the cited passage specifically supports the proposed "
        "action, `general` when it supports the wider security goal but not that exact action, "
        "or `unsupported` when it does not justify the action. Then mark whether the action "
        "itself is appropriate as `yes`, `no`, or `unclear`. Do not infer missing device "
        "identity, topology, or attack facts.\n\n"
        "## Agreement\n\n"
        "After both reviewers return their files, run `python -m "
        "iot_poc.journal_human_audit_analysis`. It writes `inter_reviewer_agreement.json`. "
        "Only then should the condition keys be opened and disagreements discussed.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare blinded human audit packets.")
    parser.add_argument("--config", default="configs/planning_study_160_alerts.json")
    args = parser.parse_args()
    print(json.dumps(build_human_packets(args.config), indent=2))


if __name__ == "__main__":
    main()
