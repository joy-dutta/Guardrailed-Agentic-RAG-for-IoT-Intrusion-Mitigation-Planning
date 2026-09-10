from __future__ import annotations

import argparse
import copy
import json
import random
import time
from pathlib import Path
from typing import Any

from .agent import OpenAIMitigationAgent
from .common import append_jsonl, load_json, read_jsonl, write_json
from .experiment import (
    estimate_planned_cost,
    evaluate_record,
    retrieval_query,
    summarize_agent_results,
)
from .retrieval import StandardsRetriever, load_standards_corpus
from .shuffled_control import wrong_family_map


def is_unbilled_transport_failure(row: dict[str, Any]) -> bool:
    return str(row.get("error", "")).startswith("APIConnectionError:")


def evidence_for_condition(
    condition: str,
    alert: dict[str, Any],
    retriever: StandardsRetriever,
    top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if condition == "no_rag":
        return [], {"model_condition": "no_rag"}
    if condition == "rag":
        return retriever.retrieve(retrieval_query(alert), top_k=top_k), {
            "model_condition": "rag"
        }
    if condition == "mismatched_rag":
        mapping = wrong_family_map()
        query_alert = copy.deepcopy(alert)
        actual = str(alert["detector"]["predicted_family"])
        query_alert["detector"]["predicted_family"] = mapping[actual]
        return retriever.retrieve(retrieval_query(query_alert), top_k=top_k), {
            "model_condition": "rag",
            "actual_predicted_family": actual,
            "retrieval_query_family": mapping[actual],
        }
    raise ValueError(f"Unknown condition: {condition}")


def run_journal_agent(
    config_path: str | Path, case_limit: int | None = None
) -> dict[str, Any]:
    extension = load_json(config_path)
    base = load_json(extension["base_config"])
    planning = extension["planning"]
    agent_config = {**base["agent"], **planning}
    cases = read_jsonl(planning["cases_path"])
    if case_limit is not None:
        cases = cases[:case_limit]
    conditions = [str(item) for item in planning["conditions"]]
    tasks = [(case, condition) for case in cases for condition in conditions]
    planned_calls = len(tasks)
    planned_cost = estimate_planned_cost(agent_config, planned_calls)
    if planned_calls > int(planning["max_calls"]):
        raise RuntimeError("Expanded experiment exceeds its hard API call cap.")
    if planned_cost > float(planning["max_cost_usd"]):
        raise RuntimeError("Expanded experiment exceeds its preflight dollar cap.")

    chunks = load_standards_corpus(
        base["retrieval"]["standards_dir"],
        int(base["retrieval"]["chunk_chars"]),
        int(base["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    agent = OpenAIMitigationAgent(
        model=str(agent_config["model"]),
        max_output_tokens=int(agent_config["max_output_tokens"]),
    )
    run_dir = Path("experiments/runs") / str(planning["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    existing = read_jsonl(results_path)
    completed = {
        (row["case_id"], row["condition"])
        for row in existing
        if "error" not in row
    }
    attempts = sum(
        0 if is_unbilled_transport_failure(row) else int(row.get("api_attempts", 1))
        for row in existing
    )
    cost = sum(
        float(row.get("usage", {}).get("estimated_cost_usd", 0.0))
        for row in existing
    )
    reserve = float(planning["per_call_cost_reserve_usd"])
    random.Random(int(base["seed"])).shuffle(tasks)

    for case, condition in tasks:
        key = (case["case_id"], condition)
        if key in completed:
            continue
        evidence_start = time.perf_counter()
        evidence, control = evidence_for_condition(
            condition,
            case["alert"],
            retriever,
            int(base["retrieval"]["top_k"]),
        )
        retrieval_seconds = time.perf_counter() - evidence_start
        last_error = None
        attempts_for_task = 0
        for _ in range(int(planning["retry_limit"]) + 1):
            if attempts >= int(planning["max_calls"]):
                raise RuntimeError("Expanded experiment reached its hard API call cap.")
            if cost + reserve > float(planning["max_cost_usd"]):
                raise RuntimeError("Expanded experiment reached its reserved dollar cap.")
            attempts += 1
            attempts_for_task += 1
            try:
                start = time.perf_counter()
                response = agent.generate(
                    case["alert"], evidence, str(control["model_condition"])
                )
                llm_seconds = time.perf_counter() - start
                record = evaluate_record(
                    case,
                    condition,
                    evidence,
                    response,
                    {
                        "retrieval": retrieval_seconds,
                        "llm": llm_seconds,
                        "guardrails": 0.0,
                        "end_to_end": retrieval_seconds + llm_seconds,
                    },
                    agent_config,
                )
                record["control"] = control
                record["api_attempts"] = attempts_for_task
                cost += float(record["usage"]["estimated_cost_usd"])
                append_jsonl(results_path, record)
                completed.add(key)
                last_error = None
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0)
        if last_error:
            append_jsonl(
                results_path,
                {
                    "case_id": case["case_id"],
                    "condition": condition,
                    "error": last_error,
                    "api_attempts": attempts_for_task,
                },
            )

    all_rows = read_jsonl(results_path)
    records = [row for row in all_rows if "error" not in row]
    summary = summarize_agent_results(records)
    summary.update(
        {
            "run_id": str(planning["run_id"]),
            "model": str(agent_config["model"]),
            "cases": len(cases),
            "conditions": summary["conditions"],
            "retriever": retriever.backend,
            "standards_chunks": len(chunks),
            "planned_calls": planned_calls,
            "successful_records": len(records),
            "saved_errors": sum("error" in row for row in all_rows),
            "billable_api_attempts": sum(
                0 if is_unbilled_transport_failure(row) else int(row.get("api_attempts", 1))
                for row in all_rows
            ),
            "unbilled_transport_failures": sum(
                int(row.get("api_attempts", 1))
                for row in all_rows
                if is_unbilled_transport_failure(row)
            ),
            "estimated_cost_usd": sum(
                float(row.get("usage", {}).get("estimated_cost_usd", 0.0))
                for row in records
            ),
            "hard_call_cap": int(planning["max_calls"]),
            "hard_cost_cap_usd": float(planning["max_cost_usd"]),
            "preflight_cost_estimate_usd": planned_cost,
            "results_path": str(results_path),
        }
    )
    write_json(run_dir / "summary.json", summary)
    write_json(
        planning.get(
            "summary_path",
            "reports/journal_extension/tables/expanded_agent_summary.json",
        ),
        summary,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the expanded IEEE Access RAG controls."
    )
    parser.add_argument("--config", default="configs/ieee_access_extension.json")
    parser.add_argument("--case-limit", type=int)
    args = parser.parse_args()
    print(json.dumps(run_journal_agent(args.config, args.case_limit), indent=2))


if __name__ == "__main__":
    main()
