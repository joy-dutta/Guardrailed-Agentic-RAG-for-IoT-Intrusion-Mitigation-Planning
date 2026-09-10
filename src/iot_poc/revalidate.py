from __future__ import annotations

import argparse
from pathlib import Path

from .common import load_json, read_jsonl, write_json, write_jsonl
from .experiment import export_retrieval_audit, plot_agent_results, summarize_agent_results
from .guardrails import full_policy_conformance, normalize_intent
from .schemas import FULL_INTENT_SCHEMA, validate


def revalidate_run(run_id: str) -> dict:
    run_dir = Path("experiments/runs") / run_id
    results_path = run_dir / "results.jsonl"
    rows = read_jsonl(results_path)
    for row in rows:
        if "error" in row:
            continue
        evidence = row.get("evidence", [])
        normalized = normalize_intent(row["raw_intent"], row["alert"], evidence)
        schema_valid, schema_errors = validate(normalized, FULL_INTENT_SCHEMA)
        available_evidence = [item["chunk_id"] for item in evidence]
        policy_valid, policy_errors = full_policy_conformance(
            normalized, row["alert"], available_evidence
        )
        row["normalized_intent"] = normalized
        row["validity"]["normalized_full_schema_valid"] = schema_valid
        row["validity"]["normalized_full_schema_errors"] = schema_errors
        row["validity"]["normalized_policy_valid"] = policy_valid
        row["validity"]["normalized_policy_errors"] = policy_errors
    write_jsonl(results_path, rows)

    successful = [row for row in rows if "error" not in row]
    updated = summarize_agent_results(successful)
    old_summary = load_json(run_dir / "summary.json")
    for key, value in old_summary.items():
        if key not in {"total_records", "conditions"}:
            updated[key] = value
    write_json(run_dir / "summary.json", updated)
    if run_id == "reference_evaluation/paired_rag_no_rag_32_alerts":
        write_json("reports/tables/agent_results.json", updated)
        plot_agent_results(updated, Path("reports/figures"))
        export_retrieval_audit(
            successful, Path("reports/tables/retrieval_audit_candidates.json")
        )
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reapply deterministic guardrails to saved raw LLM outputs."
    )
    parser.add_argument(
        "run_ids",
        nargs="*",
        default=["reference_evaluation/paired_rag_no_rag_32_alerts"],
    )
    args = parser.parse_args()
    for run_id in args.run_ids:
        summary = revalidate_run(run_id)
        print(f"Revalidated {summary['total_records']} records in {run_id}.")


if __name__ == "__main__":
    main()
