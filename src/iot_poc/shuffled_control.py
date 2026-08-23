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
    QUERY_TERMS,
    estimate_planned_cost,
    evaluate_record,
    retrieval_query,
    summarize_agent_results,
)
from .retrieval import StandardsRetriever, load_standards_corpus


def wrong_family_map() -> dict[str, str]:
    families = sorted(QUERY_TERMS)
    return {
        family: families[(index + 1) % len(families)]
        for index, family in enumerate(families)
    }


def strengthening_usage() -> tuple[int, float]:
    calls = 0
    cost = 0.0
    for path in [
        Path("experiments/runs/shuffled_rag_control/results.jsonl"),
        Path("experiments/runs/action_evidence_faithfulness/results.jsonl"),
        Path("experiments/runs/action_evidence_binding_audit/results.jsonl"),
    ]:
        for row in read_jsonl(path):
            transport_failure = str(row.get("error", "")).startswith("APIConnectionError:")
            calls += 0 if transport_failure else int(row.get("api_attempts", 1))
            cost += float(row.get("usage", {}).get("estimated_cost_usd", 0.0))
            cost += float(row.get("estimated_cost_usd", 0.0))
    return calls, cost


def run_shuffled_control(
    config_path: str | Path = "configs/experiment.json",
    cases_path: str | Path = "data/processed/agent_cases_attack_type_aware.jsonl",
) -> dict[str, Any]:
    config = load_json(config_path)
    agent_config = config["agent"]
    limits = config["strengthening_api"]
    local_limits = limits["shuffled_retrieval"]
    cases = read_jsonl(cases_path)
    run_dir = Path("experiments/runs/shuffled_rag_control")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    existing = read_jsonl(results_path)
    completed = {row["case_id"] for row in existing if "error" not in row}
    planned_calls = sum(case["case_id"] not in completed for case in cases)
    full_preflight_cost = estimate_planned_cost(agent_config, len(cases))
    preflight_cost = estimate_planned_cost(agent_config, planned_calls)
    local_used_calls = sum(
        0
        if str(row.get("error", "")).startswith("APIConnectionError:")
        else int(row.get("api_attempts", 1))
        for row in existing
    )
    local_used_cost = sum(
        float(row.get("usage", {}).get("estimated_cost_usd", 0.0)) for row in existing
    )
    if local_used_calls + planned_calls > int(local_limits["max_calls"]):
        raise RuntimeError("Shuffled-control call plan exceeds its hard call cap.")
    if local_used_cost + preflight_cost > float(local_limits["max_cost_usd"]):
        raise RuntimeError("Shuffled-control preflight exceeds its hard cost cap.")
    combined_calls, combined_cost = strengthening_usage()
    if combined_calls + planned_calls > int(limits["combined_max_calls"]):
        raise RuntimeError("Combined strengthening call plan exceeds the 50-call cap.")
    if combined_cost + preflight_cost > float(limits["combined_max_cost_usd"]):
        raise RuntimeError("Combined strengthening preflight exceeds the $0.35 cap.")

    chunks = load_standards_corpus(
        config["retrieval"]["standards_dir"],
        chunk_chars=int(config["retrieval"]["chunk_chars"]),
        chunk_overlap=int(config["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    agent = OpenAIMitigationAgent(
        model=agent_config["model"],
        max_output_tokens=int(agent_config["max_output_tokens"]),
    )
    mapping = wrong_family_map()
    attempted = sum(
        0
        if str(row.get("error", "")).startswith("APIConnectionError:")
        else int(row.get("api_attempts", 1))
        for row in existing
    )
    actual_cost = local_used_cost
    tasks = list(cases)
    random.Random(int(config["seed"])).shuffle(tasks)
    for case in tasks:
        if case["case_id"] in completed:
            continue
        alert = case["alert"]
        true_query_family = alert["detector"]["predicted_family"]
        shuffled_family = mapping[true_query_family]
        query_alert = copy.deepcopy(alert)
        query_alert["detector"]["predicted_family"] = shuffled_family
        retrieval_start = time.perf_counter()
        evidence = retriever.retrieve(
            retrieval_query(query_alert), top_k=int(config["retrieval"]["top_k"])
        )
        retrieval_seconds = time.perf_counter() - retrieval_start
        attempts_for_task = 0
        last_error = None
        for _ in range(int(agent_config["retry_limit"]) + 1):
            combined_calls, combined_cost = strengthening_usage()
            if attempted >= int(local_limits["max_calls"]):
                raise RuntimeError("Shuffled-control hard call cap reached.")
            if actual_cost >= float(local_limits["max_cost_usd"]):
                raise RuntimeError("Shuffled-control hard cost cap reached.")
            if combined_calls >= int(limits["combined_max_calls"]):
                raise RuntimeError("Combined strengthening hard call cap reached.")
            if combined_cost >= float(limits["combined_max_cost_usd"]):
                raise RuntimeError("Combined strengthening hard cost cap reached.")
            attempted += 1
            attempts_for_task += 1
            try:
                start = time.perf_counter()
                response = agent.generate(alert, evidence, "rag")
                llm_seconds = time.perf_counter() - start
                record = evaluate_record(
                    case,
                    "shuffled_rag",
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
                record["api_attempts"] = attempts_for_task
                record["control"] = {
                    "actual_predicted_family": true_query_family,
                    "retrieval_query_family": shuffled_family,
                    "model_saw_condition_label": "rag",
                }
                actual_cost += float(record["usage"]["estimated_cost_usd"])
                append_jsonl(results_path, record)
                completed.add(case["case_id"])
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
                    "condition": "shuffled_rag",
                    "error": last_error,
                    "api_attempts": attempts_for_task,
                },
            )

    records = [row for row in read_jsonl(results_path) if "error" not in row]
    summary = summarize_agent_results(records)
    summary.update(
        {
            "run_id": "shuffled_rag_control",
            "model": agent_config["model"],
            "records": len(records),
            "wrong_family_mapping": mapping,
            "hard_call_cap": int(local_limits["max_calls"]),
            "hard_cost_cap_usd": float(local_limits["max_cost_usd"]),
            "combined_hard_call_cap": int(limits["combined_max_calls"]),
            "combined_hard_cost_cap_usd": float(limits["combined_max_cost_usd"]),
            "preflight_cost_estimate_usd": full_preflight_cost,
            "additional_preflight_cost_estimate_usd": preflight_cost,
            "actual_calls": sum(
                0
                if str(row.get("error", "")).startswith("APIConnectionError:")
                else int(row.get("api_attempts", 1))
                for row in read_jsonl(results_path)
            ),
            "unbilled_transport_failures": sum(
                int(row.get("api_attempts", 1))
                for row in read_jsonl(results_path)
                if str(row.get("error", "")).startswith("APIConnectionError:")
            ),
            "actual_estimated_cost_usd": sum(
                float(row["usage"]["estimated_cost_usd"]) for row in records
            ),
        }
    )
    write_json(run_dir / "summary.json", summary)
    write_json("reports/tables/shuffled_rag_control.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a wrong-family retrieval control.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    print(json.dumps(run_shuffled_control(args.config), indent=2))


if __name__ == "__main__":
    main()
