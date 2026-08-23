from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .agent import OpenAIMitigationAgent
from .common import append_jsonl, load_json, read_jsonl, write_json
from .guardrails import full_policy_conformance, normalize_intent, raw_policy_conformance
from .retrieval import StandardsRetriever, load_standards_corpus
from .schemas import FULL_INTENT_SCHEMA, RAW_INTENT_SCHEMA, validate


QUERY_TERMS = {
    "Benign": "normal activity continuous monitoring avoid unnecessary disruption cybersecurity state logging",
    "DDoS": "distributed denial of service flooding resource exhaustion availability filtering network traffic",
    "DoS": "denial of service resource exhaustion availability traffic filtering",
    "Recon": "reconnaissance scanning probing unauthorized activity continuous monitoring logging",
    "Web": "SQL injection invalid data input application layer user interface prevent system manipulation",
    "BruteForce": "password brute force failed authentication attempt limiting account lockout",
    "Spoofing": "spoofing impersonation authentication network access control identity",
    "Mirai": "botnet compromised malware malicious code logically disable network interfaces restrict access authorized communication",
}


def retrieval_query(alert: dict[str, Any]) -> str:
    family = alert["detector"]["predicted_family"]
    active_protocols = [
        name
        for name in ["TCP", "UDP", "ICMP", "HTTP", "HTTPS", "DNS", "ARP"]
        if float(alert["observations"].get(name, 0)) > 0.2
    ]
    return " ".join(
        [
            QUERY_TERMS[family],
            f"IoT gateway predicted threat {family}",
            f"protocols {' '.join(active_protocols)}",
        ]
    )


def estimate_planned_cost(agent_config: dict[str, Any], calls: int) -> float:
    input_tokens = calls * int(agent_config["estimated_input_tokens_per_call"])
    output_tokens = calls * int(agent_config["estimated_output_tokens_per_call"])
    return (
        input_tokens / 1_000_000 * float(agent_config["input_usd_per_million"])
        + output_tokens / 1_000_000 * float(agent_config["output_usd_per_million"])
    )


def usage_cost(agent_config: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * float(agent_config["input_usd_per_million"])
        + output_tokens / 1_000_000 * float(agent_config["output_usd_per_million"])
    )


def evaluate_record(
    case: dict[str, Any],
    condition: str,
    evidence: list[dict[str, Any]],
    response: Any,
    latency: dict[str, float],
    agent_config: dict[str, Any],
) -> dict[str, Any]:
    alert = case["alert"]
    raw = response.raw_intent
    raw_json_valid = "_json_parse_error" not in raw
    raw_compact_valid, raw_compact_errors = validate(raw, RAW_INTENT_SCHEMA)
    raw_full_valid, raw_full_errors = validate(raw, FULL_INTENT_SCHEMA)
    raw_policy_valid, raw_policy_errors = raw_policy_conformance(
        raw, alert["detector"]["predicted_family"]
    )
    guardrail_start = time.perf_counter()
    normalized = normalize_intent(raw, alert, evidence)
    normalized_schema_valid, normalized_schema_errors = validate(normalized, FULL_INTENT_SCHEMA)
    available_evidence = [item["chunk_id"] for item in evidence]
    normalized_policy_valid, normalized_policy_errors = full_policy_conformance(
        normalized, alert, available_evidence
    )
    guardrail_seconds = time.perf_counter() - guardrail_start
    cited = raw.get("evidence_used", []) if isinstance(raw, dict) else []
    citation_ids_valid = isinstance(cited, list) and all(ref in available_evidence for ref in cited)

    cost = usage_cost(agent_config, response.input_tokens, response.output_tokens)
    return {
        "case_id": case["case_id"],
        "condition": condition,
        "selection_reason": case["selection_reason"],
        "alert": alert,
        "evaluation": case["evaluation"],
        "counterfactual_plan_only": alert["routing_decision"] == "escalate",
        "retrieval_query": retrieval_query(alert),
        "evidence": evidence,
        "raw_intent": raw,
        "normalized_intent": normalized,
        "validity": {
            "raw_json_valid": raw_json_valid,
            "raw_compact_schema_valid": raw_compact_valid,
            "raw_compact_schema_errors": raw_compact_errors,
            "raw_full_schema_valid": raw_full_valid,
            "raw_full_schema_errors": raw_full_errors,
            "raw_policy_valid": raw_policy_valid,
            "raw_policy_errors": raw_policy_errors,
            "citation_ids_valid": citation_ids_valid,
            "normalized_full_schema_valid": normalized_schema_valid,
            "normalized_full_schema_errors": normalized_schema_errors,
            "normalized_policy_valid": normalized_policy_valid,
            "normalized_policy_errors": normalized_policy_errors,
        },
        "latency_seconds": {
            **latency,
            "guardrails": guardrail_seconds,
            "end_to_end": latency["retrieval"] + latency["llm"] + guardrail_seconds,
        },
        "usage": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "estimated_cost_usd": cost,
        },
    }


def run_agent_experiment(
    config_path: str | Path,
    run_id: str,
    case_limit: int | None = None,
    cases_path: str | Path = "data/processed/agent_cases.jsonl",
) -> dict[str, Any]:
    config = load_json(config_path)
    agent_config = config["agent"]
    cases = read_jsonl(cases_path)
    if case_limit is not None:
        cases = cases[:case_limit]
    conditions = list(agent_config["conditions"])
    planned_calls = len(cases) * len(conditions)
    planned_cost = estimate_planned_cost(agent_config, planned_calls)
    if planned_calls > int(agent_config["max_calls"]):
        raise RuntimeError("Planned calls exceed the configured hard call cap.")
    if planned_cost > float(agent_config["max_cost_usd"]):
        raise RuntimeError("Preflight estimate exceeds the configured hard dollar cap.")

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

    run_dir = Path("experiments/runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    existing = read_jsonl(results_path)
    completed = {(row["case_id"], row["condition"]) for row in existing if "error" not in row}
    attempted_calls = sum(int(row.get("api_attempts", 1)) for row in existing)
    actual_cost = sum(float(row.get("usage", {}).get("estimated_cost_usd", 0)) for row in existing)

    tasks = [(case, condition) for case in cases for condition in conditions]
    random.Random(int(config["seed"])).shuffle(tasks)
    for case, condition in tasks:
        task_key = (case["case_id"], condition)
        if task_key in completed:
            continue
        alert = case["alert"]
        retrieval_start = time.perf_counter()
        evidence = (
            retriever.retrieve(retrieval_query(alert), top_k=int(config["retrieval"]["top_k"]))
            if condition == "rag"
            else []
        )
        retrieval_seconds = time.perf_counter() - retrieval_start

        attempts_for_task = 0
        last_error = None
        for _ in range(int(agent_config["retry_limit"]) + 1):
            if attempted_calls >= int(agent_config["max_calls"]):
                raise RuntimeError("Hard API call cap reached before the experiment completed.")
            if actual_cost >= float(agent_config["max_cost_usd"]):
                raise RuntimeError("Hard API dollar cap reached before the experiment completed.")
            attempted_calls += 1
            attempts_for_task += 1
            try:
                llm_start = time.perf_counter()
                response = agent.generate(alert, evidence, condition)
                llm_seconds = time.perf_counter() - llm_start
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
                record["api_attempts"] = attempts_for_task
                actual_cost += float(record["usage"]["estimated_cost_usd"])
                append_jsonl(results_path, record)
                completed.add(task_key)
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

    records = [row for row in read_jsonl(results_path) if "error" not in row]
    summary = summarize_agent_results(records)
    summary.update(
        {
            "run_id": run_id,
            "model": agent_config["model"],
            "retriever": retriever.backend,
            "standards_chunks": len(chunks),
            "planned_calls_for_this_invocation": planned_calls,
            "hard_call_cap": int(agent_config["max_calls"]),
            "hard_cost_cap_usd": float(agent_config["max_cost_usd"]),
            "preflight_cost_estimate_usd": planned_cost,
            "actual_calls_in_saved_records": sum(int(row.get("api_attempts", 1)) for row in read_jsonl(results_path)),
            "actual_estimated_cost_usd": sum(
                float(row.get("usage", {}).get("estimated_cost_usd", 0)) for row in records
            ),
            "results_path": str(results_path),
            "cases_path": str(cases_path),
        }
    )
    write_json(run_dir / "summary.json", summary)
    write_json("reports/tables/agent_results.json", summary)
    plot_agent_results(summary, Path("reports/figures"))
    export_retrieval_audit(records, Path("reports/tables/retrieval_audit_candidates.json"))
    return summary


def rate(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([bool(row["validity"][key]) for row in rows])) if rows else 0.0


def summarize_agent_results(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"total_records": len(records), "conditions": {}}
    for condition in sorted({row["condition"] for row in records}):
        rows = [row for row in records if row["condition"] == condition]
        input_tokens = sum(row["usage"]["input_tokens"] for row in rows)
        output_tokens = sum(row["usage"]["output_tokens"] for row in rows)
        summary["conditions"][condition] = {
            "records": len(rows),
            "raw_json_validity": rate(rows, "raw_json_valid"),
            "raw_compact_schema_validity": rate(rows, "raw_compact_schema_valid"),
            "raw_full_schema_validity": rate(rows, "raw_full_schema_valid"),
            "raw_policy_conformance": rate(rows, "raw_policy_valid"),
            "citation_identifier_validity": rate(rows, "citation_ids_valid"),
            "normalized_full_schema_validity": rate(rows, "normalized_full_schema_valid"),
            "normalized_policy_conformance": rate(rows, "normalized_policy_valid"),
            "evidence_attachment_rate": float(
                np.mean([bool(row["raw_intent"].get("evidence_used")) for row in rows])
            ),
            "valid_evidence_attachment_rate": float(
                np.mean(
                    [
                        bool(row["raw_intent"].get("evidence_used"))
                        and bool(row["validity"]["citation_ids_valid"])
                        for row in rows
                    ]
                )
            ),
            "mean_evidence_references": float(
                np.mean(
                    [
                        len(row["raw_intent"].get("evidence_used", []))
                        if isinstance(row["raw_intent"].get("evidence_used", []), list)
                        else 0
                        for row in rows
                    ]
                )
            ),
            "mean_retrieval_seconds": float(np.mean([row["latency_seconds"]["retrieval"] for row in rows])),
            "mean_llm_seconds": float(np.mean([row["latency_seconds"]["llm"] for row in rows])),
            "mean_end_to_end_seconds": float(np.mean([row["latency_seconds"]["end_to_end"] for row in rows])),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": float(sum(row["usage"]["estimated_cost_usd"] for row in rows)),
        }
    return summary


def plot_agent_results(summary: dict[str, Any], output_dir: Path) -> None:
    conditions = sorted(summary["conditions"])
    metrics = [
        ("evidence_attachment_rate", "Evidence attached"),
        ("raw_policy_conformance", "Raw policy conformance"),
        ("normalized_policy_conformance", "Guardrailed policy conformance"),
    ]
    x = np.arange(len(metrics))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.3, 4.2))
    for index, condition in enumerate(conditions):
        values = [summary["conditions"][condition][key] for key, _ in metrics]
        ax.bar(x + (index - 0.5) * width, values, width, label=condition.replace("_", " ").upper())
    ax.set_xticks(x, [label for _, label in metrics], rotation=10)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction of cases")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "rag_guardrail_comparison.png", dpi=220)
    plt.close(fig)


def export_retrieval_audit(records: list[dict[str, Any]], path: Path) -> None:
    candidates = []
    rag_rows = sorted(
        [row for row in records if row["condition"] == "rag"],
        key=lambda row: row["case_id"],
    )
    selected_case_ids = set()
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in rag_rows:
        family = row["alert"]["detector"]["predicted_family"]
        by_family.setdefault(family, []).append(row)
    for family_rows in by_family.values():
        selected_case_ids.update(row["case_id"] for row in family_rows[:2])
    for row in rag_rows:
        if row["case_id"] not in selected_case_ids:
            continue
        for rank, evidence in enumerate(row["evidence"], start=1):
            candidates.append(
                {
                    "case_id": row["case_id"],
                    "predicted_family": row["alert"]["detector"]["predicted_family"],
                    "rank": rank,
                    "source": evidence["source"],
                    "chunk_id": evidence["chunk_id"],
                    "score": evidence["score"],
                    "excerpt": evidence["excerpt"],
                    "manual_label": "PENDING",
                    "manual_note": "",
                }
            )
    write_json(path, candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded RAG/no-RAG IoT mitigation experiments.")
    parser.add_argument("--config", default="configs/experiment.json")
    parser.add_argument("--run-id", default="paper_main")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--cases-path", default="data/processed/agent_cases.jsonl")
    args = parser.parse_args()
    summary = run_agent_experiment(
        args.config, args.run_id, args.case_limit, args.cases_path
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
