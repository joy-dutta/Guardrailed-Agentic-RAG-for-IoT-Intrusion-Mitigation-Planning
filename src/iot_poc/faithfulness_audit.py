from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .agent import response_text
from .common import append_jsonl, load_json, read_jsonl, write_json
from .experiment import usage_cost
from .shuffled_control import strengthening_usage


LABELS = ["directly_supported", "generally_supported", "unsupported"]


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
                    "required": ["audit_id", "label", "reason"],
                    "properties": {
                        "audit_id": {"type": "string"},
                        "label": {"type": "string", "enum": LABELS},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }


def build_items() -> list[dict[str, Any]]:
    original = [
        row
        for row in read_jsonl(
            "experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/results.jsonl"
        )
        if "error" not in row and row["condition"] == "rag"
    ]
    shuffled = [
        row
        for row in read_jsonl(
            "experiments/runs/reference_evaluation/wrong_family_retrieval_control_32_alerts/results.jsonl"
        )
        if "error" not in row
    ]
    source_items = []
    for record in original + shuffled:
        cited = record["raw_intent"].get("evidence_used", [])
        cited = cited if isinstance(cited, list) else []
        evidence = {
            item["chunk_id"]: {
                "chunk_id": item["chunk_id"],
                "source": Path(item["source"]).name,
                "excerpt": item["excerpt"],
            }
            for item in record["evidence"]
        }
        cited_evidence = [evidence[ref] for ref in cited if ref in evidence]
        for action_index, action in enumerate(
            record["raw_intent"].get("recommended_actions", []), start=1
        ):
            if not isinstance(action, dict):
                continue
            source_items.append(
                {
                    "condition": record["condition"],
                    "case_id": record["case_id"],
                    "action_index": action_index,
                    "predicted_family": record["alert"]["detector"]["predicted_family"],
                    "action": action.get("action", ""),
                    "rationale": action.get("rationale", ""),
                    "cited_evidence": cited_evidence,
                }
            )

    random.Random(20260821).shuffle(source_items)
    for index, item in enumerate(source_items, start=1):
        item["audit_id"] = f"AE-{index:03d}"
    packet_rows = []
    key_rows = []
    for item in source_items:
        packet_rows.append(
            {
                "audit_id": item["audit_id"],
                "predicted_family": item["predicted_family"],
                "action": item["action"],
                "rationale": item["rationale"],
                "cited_evidence": json.dumps(item["cited_evidence"], ensure_ascii=True),
                "human_label": "",
                "human_reason": "",
            }
        )
        key_rows.append(
            {
                "audit_id": item["audit_id"],
                "condition": item["condition"],
                "case_id": item["case_id"],
                "action_index": item["action_index"],
            }
        )
    pd.DataFrame(packet_rows).to_csv(
        "reports/tables/action_evidence_human_blind_packet.csv", index=False
    )
    pd.DataFrame(key_rows).to_csv(
        "reports/tables/action_evidence_blind_key.csv", index=False
    )
    return source_items


def call_auditor(client: Any, model: str, max_tokens: int, batch: list[dict]) -> dict:
    supplied = [
        {
            "audit_id": item["audit_id"],
            "predicted_family": item["predicted_family"],
            "recommended_action": item["action"],
            "action_rationale": item["rationale"],
            "cited_evidence": item["cited_evidence"],
        }
        for item in batch
    ]
    response = client.responses.create(
        model=model,
        instructions=(
            "Act as a blinded action-to-evidence auditor. Judge only whether the cited "
            "official-document excerpts support the recommended action for the stated "
            "predicted IoT threat family. Label directly_supported when an excerpt "
            "explicitly supports that action or its concrete mechanism; generally_supported "
            "when the excerpts support the security objective but not the specific action; "
            "and unsupported when the evidence is absent, unrelated, or cannot justify the "
            "action. Do not reward authority, citation count, or plausible outside knowledge. "
            "Judge every item independently and return each audit_id exactly once."
        ),
        input=json.dumps({"items": supplied}, indent=2),
        reasoning={"effort": "none"},
        max_output_tokens=max_tokens,
        text={
            "format": {
                "type": "json_schema",
                "name": "action_evidence_faithfulness",
                "schema": audit_schema(),
                "strict": True,
            }
        },
    )
    text = getattr(response, "output_text", None) or response_text(response) or "{}"
    parsed = json.loads(text)
    expected = {item["audit_id"] for item in batch}
    returned = [item["audit_id"] for item in parsed.get("judgments", [])]
    if set(returned) != expected or len(returned) != len(expected):
        raise ValueError("Auditor did not return every audit_id exactly once.")
    usage = getattr(response, "usage", None)
    return {
        "judgments": parsed["judgments"],
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def exact_paired_p(original: dict[str, bool], shuffled: dict[str, bool]) -> dict[str, Any]:
    original_only = sum(original[key] and not shuffled[key] for key in original)
    shuffled_only = sum(shuffled[key] and not original[key] for key in original)
    discordant = original_only + shuffled_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(0, min(original_only, shuffled_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    return {
        "paired_cases": len(original),
        "original_only_successes": original_only,
        "shuffled_only_successes": shuffled_only,
        "discordant_pairs": discordant,
        "two_sided_exact_p": p_value,
    }


def summarize(items: list[dict], judgments: dict[str, dict], cost: float, calls: int) -> dict:
    rows = []
    for item in items:
        judgment = judgments[item["audit_id"]]
        rows.append({**item, "label": judgment["label"], "reason": judgment["reason"]})
    safe_rows = [
        {key: value for key, value in row.items() if key != "cited_evidence"}
        for row in rows
    ]
    pd.DataFrame(safe_rows).to_csv(
        "reports/tables/action_evidence_faithfulness_items.csv", index=False
    )

    by_condition = {}
    case_success: dict[str, dict[str, bool]] = {}
    for condition in ["rag", "shuffled_rag"]:
        condition_rows = [row for row in rows if row["condition"] == condition]
        counts = Counter(row["label"] for row in condition_rows)
        cases = sorted({row["case_id"] for row in condition_rows})
        per_case = {
            case_id: all(
                row["label"] != "unsupported"
                for row in condition_rows
                if row["case_id"] == case_id
            )
            for case_id in cases
        }
        case_success[condition] = per_case
        by_condition[condition] = {
            "actions": len(condition_rows),
            "label_counts": dict(counts),
            "direct_support_rate": counts["directly_supported"] / len(condition_rows),
            "direct_or_general_support_rate": (
                counts["directly_supported"] + counts["generally_supported"]
            )
            / len(condition_rows),
            "unsupported_rate": counts["unsupported"] / len(condition_rows),
            "cases_with_all_actions_supported": sum(per_case.values()),
            "case_all_actions_supported_rate": sum(per_case.values()) / len(per_case),
        }
    paired = exact_paired_p(case_success["rag"], case_success["shuffled_rag"])
    return {
        "auditor_type": "blinded_model_based_action_to_evidence_audit",
        "labels": LABELS,
        "conditions_hidden_from_auditor": True,
        "items": len(rows),
        "calls": calls,
        "estimated_cost_usd": cost,
        "by_condition": by_condition,
        "paired_case_test": paired,
        "human_audit_status": (
            "A label-free packet is available; an independent human has not yet labelled it."
        ),
    }


def run_faithfulness(config_path: str = "configs/experiment.json") -> dict[str, Any]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the audit process.")
    from openai import OpenAI

    config = load_json(config_path)
    limits = config["strengthening_api"]
    audit_config = limits["faithfulness_audit"]
    agent_config = config["agent"]
    items = build_items()
    no_evidence = [item for item in items if not item["cited_evidence"]]
    auditable = [item for item in items if item["cited_evidence"]]
    families = sorted({item["predicted_family"] for item in auditable})
    batches = [
        [item for item in auditable if item["predicted_family"] == family]
        for family in families
    ]
    run_dir = Path("experiments/runs/reference_evaluation/action_evidence_faithfulness_audit")
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    existing = read_jsonl(results_path)
    completed = {row["batch_family"] for row in existing if "error" not in row}
    missing_batches = [
        (family, batch)
        for family, batch in zip(families, batches)
        if family not in completed
    ]
    local_used_calls = sum(int(row.get("api_attempts", 1)) for row in existing)
    local_used_cost = sum(float(row.get("estimated_cost_usd", 0.0)) for row in existing)
    if local_used_calls + len(missing_batches) > int(audit_config["max_calls"]):
        raise RuntimeError("Faithfulness audit exceeds its hard call cap.")
    per_batch_estimate = (
        int(audit_config["estimated_input_tokens_per_call"])
        / 1_000_000
        * float(agent_config["input_usd_per_million"])
        + int(audit_config["estimated_output_tokens_per_call"])
        / 1_000_000
        * float(agent_config["output_usd_per_million"])
    )
    full_preflight_cost = len(batches) * per_batch_estimate
    preflight_cost = len(missing_batches) * per_batch_estimate
    if local_used_cost + preflight_cost > float(audit_config["max_cost_usd"]):
        raise RuntimeError("Faithfulness audit preflight exceeds its hard cost cap.")
    combined_calls, combined_cost = strengthening_usage()
    if combined_calls + len(missing_batches) > int(limits["combined_max_calls"]):
        raise RuntimeError("Combined strengthening call plan exceeds its hard cap.")
    if combined_cost + preflight_cost > float(limits["combined_max_cost_usd"]):
        raise RuntimeError("Combined strengthening preflight exceeds its hard cost cap.")

    attempted = sum(int(row.get("api_attempts", 1)) for row in existing)
    client = OpenAI()
    for family, batch in zip(families, batches):
        if family in completed:
            continue
        attempts_for_batch = 0
        last_error = None
        for _ in range(int(audit_config["retry_limit"]) + 1):
            combined_calls, combined_cost = strengthening_usage()
            if attempted >= int(audit_config["max_calls"]):
                raise RuntimeError("Faithfulness-audit hard call cap reached.")
            if combined_calls >= int(limits["combined_max_calls"]):
                raise RuntimeError("Combined strengthening hard call cap reached.")
            if combined_cost >= float(limits["combined_max_cost_usd"]):
                raise RuntimeError("Combined strengthening hard cost cap reached.")
            attempted += 1
            attempts_for_batch += 1
            try:
                result = call_auditor(
                    client,
                    str(audit_config["model"]),
                    int(audit_config["max_output_tokens"]),
                    batch,
                )
                result.update(
                    {
                        "batch_family": family,
                        "api_attempts": attempts_for_batch,
                        "estimated_cost_usd": usage_cost(
                            agent_config, result["input_tokens"], result["output_tokens"]
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
                    "batch_family": family,
                    "api_attempts": attempts_for_batch,
                    "error": last_error,
                },
            )

    records = [row for row in read_jsonl(results_path) if "error" not in row]
    judgments = {
        judgment["audit_id"]: judgment
        for record in records
        for judgment in record["judgments"]
    }
    for item in no_evidence:
        judgments[item["audit_id"]] = {
            "audit_id": item["audit_id"],
            "label": "unsupported",
            "reason": "No cited evidence was attached to this action.",
        }
    if len(judgments) != len(items):
        raise RuntimeError("The action-to-evidence audit is incomplete.")
    cost = sum(float(record["estimated_cost_usd"]) for record in records)
    calls = sum(int(record.get("api_attempts", 1)) for record in records)
    summary = summarize(items, judgments, cost, calls)
    summary.update(
        {
            "model": audit_config["model"],
            "hard_call_cap": int(audit_config["max_calls"]),
            "hard_cost_cap_usd": float(audit_config["max_cost_usd"]),
            "combined_hard_call_cap": int(limits["combined_max_calls"]),
            "combined_hard_cost_cap_usd": float(limits["combined_max_cost_usd"]),
            "preflight_cost_estimate_usd": full_preflight_cost,
            "additional_preflight_cost_estimate_usd": preflight_cost,
            "input_tokens": sum(record["input_tokens"] for record in records),
            "output_tokens": sum(record["output_tokens"] for record in records),
        }
    )
    write_json("reports/tables/action_evidence_faithfulness.json", summary)
    write_json(run_dir / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit action-to-evidence faithfulness.")
    parser.add_argument("--config", default="configs/experiment.json")
    args = parser.parse_args()
    print(json.dumps(run_faithfulness(args.config), indent=2))


if __name__ == "__main__":
    main()
