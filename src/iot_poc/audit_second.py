from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from .agent import response_text
from .common import append_jsonl, load_json, read_jsonl, write_json


LABELS = ["direct", "supporting", "irrelevant"]


def blind_packet(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packet = [
        {
            "item_id": f"{row['case_id']}|{row['rank']}",
            "case_id": row["case_id"],
            "predicted_family": row["predicted_family"],
            "rank": row["rank"],
            "source": Path(row["source"]).name,
            "chunk_id": row["chunk_id"],
            "excerpt": row["excerpt"],
        }
        for row in candidates
    ]
    pd.DataFrame(packet).to_csv(
        "reports/tables/retrieval_audit_blind_packet.csv", index=False
    )
    return packet


def audit_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["judgments"],
        "properties": {
            "judgments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["item_id", "predicted_family", "label", "reason"],
                    "properties": {
                        "item_id": {"type": "string"},
                        "predicted_family": {"type": "string"},
                        "label": {"type": "string", "enum": LABELS},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }


def estimated_cost(config: dict[str, Any], calls: int) -> float:
    return (
        calls
        * int(config["estimated_input_tokens_per_call"])
        / 1_000_000
        * float(config["input_usd_per_million"])
        + calls
        * int(config["estimated_output_tokens_per_call"])
        / 1_000_000
        * float(config["output_usd_per_million"])
    )


def usage_cost(config: dict[str, Any], input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * float(config["input_usd_per_million"])
        + output_tokens / 1_000_000 * float(config["output_usd_per_million"])
    )


def call_auditor(client: Any, config: dict[str, Any], batch: list[dict[str, Any]]) -> dict:
    response = client.responses.create(
        model=config["model"],
        instructions=(
            "Act as a blinded retrieval-relevance auditor. Evaluate only whether each "
            "excerpt is useful for assessing or mitigating the stated predicted IoT "
            "attack family. Do not assume a passage is relevant because its publisher "
            "is authoritative. Label direct when it explicitly addresses the attack or "
            "an immediately applicable control; supporting when it provides useful "
            "security context but is not threat-specific; and irrelevant when it does "
            "not materially help. A control need not name the attack to be applicable. "
            "For Benign, guidance supporting non-disruptive monitoring and avoiding "
            "unnecessary mitigation can be direct. Judge every item independently, use "
            "only its stated predicted_family, and return item_id and predicted_family "
            "exactly as supplied. The reason must refer to that stated family."
        ),
        input=json.dumps({"rubric_labels": LABELS, "items": batch}, indent=2),
        reasoning={"effort": "none"},
        max_output_tokens=int(config["max_output_tokens"]),
        text={
            "format": {
                "type": "json_schema",
                "name": "blinded_retrieval_audit",
                "schema": audit_schema(),
                "strict": True,
            }
        },
    )
    raw_text = getattr(response, "output_text", None) or response_text(response) or "{}"
    parsed = json.loads(raw_text)
    expected = {row["item_id"] for row in batch}
    returned = [row["item_id"] for row in parsed.get("judgments", [])]
    if set(returned) != expected or len(returned) != len(expected):
        raise ValueError("Auditor did not return every requested item_id exactly once.")
    expected_families = {row["item_id"]: row["predicted_family"] for row in batch}
    if any(
        row.get("predicted_family") != expected_families[row["item_id"]]
        for row in parsed["judgments"]
    ):
        raise ValueError("Auditor changed a supplied predicted_family.")
    usage = getattr(response, "usage", None)
    return {
        "judgments": parsed["judgments"],
        "raw_text": raw_text,
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def run_second_audit(
    config_path: str = "configs/experiment.json",
    run_id: str = "reference_evaluation/independent_relevance_audit",
) -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the audit process.")
    from openai import OpenAI

    config = load_json(config_path)["independent_relevance_audit"]
    candidates = load_json("reports/tables/retrieval_audit_candidates.json")
    packet = blind_packet(candidates)
    if config.get("batch_by_family"):
        families = sorted({row["predicted_family"] for row in packet})
        batches = [
            [row for row in packet if row["predicted_family"] == family]
            for family in families
        ]
    else:
        batches = [packet]
    if len(batches) > int(config["max_calls"]):
        raise RuntimeError("Planned audit calls exceed the hard call cap.")
    preflight_cost = estimated_cost(config, len(batches))
    if preflight_cost > float(config["max_cost_usd"]):
        raise RuntimeError("Planned audit cost exceeds the hard dollar cap.")

    results_path = Path("experiments/runs") / run_id / "results.jsonl"
    existing = read_jsonl(results_path)
    completed_batches = {row["batch_index"] for row in existing if "error" not in row}
    attempted_calls = sum(int(row.get("api_attempts", 1)) for row in existing)
    client = OpenAI()
    for batch_index, batch in enumerate(batches):
        if batch_index in completed_batches:
            continue
        last_error = None
        attempts = 0
        for _ in range(int(config["retry_limit"]) + 1):
            if attempted_calls >= int(config["max_calls"]):
                raise RuntimeError("Hard second-auditor API call cap reached.")
            attempted_calls += 1
            attempts += 1
            try:
                result = call_auditor(client, config, batch)
                result.update(
                    {
                        "batch_index": batch_index,
                        "api_attempts": attempts,
                        "estimated_cost_usd": usage_cost(
                            config, result["input_tokens"], result["output_tokens"]
                        ),
                    }
                )
                append_jsonl(results_path, result)
                last_error = None
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        if last_error:
            append_jsonl(
                results_path,
                {
                    "batch_index": batch_index,
                    "api_attempts": attempts,
                    "error": last_error,
                },
            )

    records = [row for row in read_jsonl(results_path) if "error" not in row]
    judgments = [judgment for row in records for judgment in row["judgments"]]
    if len(judgments) != len(packet):
        raise RuntimeError("The blinded second audit is incomplete.")
    output = {
        "auditor_type": "blinded_model_based",
        "run_id": run_id,
        "model": config["model"],
        "items": len(judgments),
        "calls": sum(int(row.get("api_attempts", 1)) for row in records),
        "input_tokens": sum(row["input_tokens"] for row in records),
        "output_tokens": sum(row["output_tokens"] for row in records),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in records),
        "hard_call_cap": int(config["max_calls"]),
        "hard_cost_cap_usd": float(config["max_cost_usd"]),
        "preflight_cost_estimate_usd": preflight_cost,
        "judgments": judgments,
    }
    write_json("reports/tables/retrieval_audit_independent.json", output)
    return output


def compare_auditors(
    second_path: str | Path = "reports/tables/retrieval_audit_independent.json",
) -> dict[str, Any]:
    first = load_json("reports/tables/retrieval_audit_labeled.json")
    second_document = load_json(second_path)
    second = {row["item_id"]: row for row in second_document["judgments"]}
    paired = []
    for row in first:
        item_id = f"{row['case_id']}|{row['rank']}"
        other = second[item_id]
        paired.append(
            {
                "item_id": item_id,
                "case_id": row["case_id"],
                "predicted_family": row["predicted_family"],
                "rank": row["rank"],
                "chunk_id": row["chunk_id"],
                "first_label": row["manual_label"],
                "second_label": other["label"],
                "second_reason": other["reason"],
            }
        )
    first_labels = [row["first_label"] for row in paired]
    second_labels = [row["second_label"] for row in paired]
    first_binary = [label != "irrelevant" for label in first_labels]
    second_binary = [label != "irrelevant" for label in second_labels]
    three_way_agreement = sum(a == b for a, b in zip(first_labels, second_labels)) / len(paired)
    binary_agreement = sum(a == b for a, b in zip(first_binary, second_binary)) / len(paired)
    summary = {
        "items": len(paired),
        "auditor_1": "primary_semantic_audit",
        "auditor_2": "blinded_model_based_audit",
        "auditor_2_model": second_document["model"],
        "three_way_exact_agreement": three_way_agreement,
        "three_way_cohen_kappa": float(cohen_kappa_score(first_labels, second_labels, labels=LABELS)),
        "three_way_confusion_matrix_labels": LABELS,
        "three_way_confusion_matrix": confusion_matrix(
            first_labels, second_labels, labels=LABELS
        ).tolist(),
        "binary_relevance_agreement": binary_agreement,
        "binary_relevance_cohen_kappa": float(cohen_kappa_score(first_binary, second_binary)),
        "auditor_1_relevant_rate": sum(first_binary) / len(first_binary),
        "auditor_2_relevant_rate": sum(second_binary) / len(second_binary),
        "disagreements": [row for row in paired if row["first_label"] != row["second_label"]],
        "second_audit_cost_usd": second_document["estimated_cost_usd"],
        "human_audit_status": "A second independent human has not yet reviewed the blind packet.",
    }
    write_json("reports/tables/retrieval_audit_independent_agreement.json", summary)
    pd.DataFrame(paired).to_csv(
        "reports/tables/retrieval_audit_independent_items.csv", index=False
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a blinded second retrieval audit.")
    parser.add_argument("--config", default="configs/experiment.json")
    parser.add_argument(
        "--run-id", default="reference_evaluation/independent_relevance_audit"
    )
    args = parser.parse_args()
    run_second_audit(args.config, args.run_id)
    print(json.dumps(compare_auditors(), indent=2))


if __name__ == "__main__":
    main()
