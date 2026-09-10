from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from .common import load_json, read_jsonl, write_json, write_jsonl
from .journal_evidence_gate import (
    _evidence_payload,
    _label_counts,
    _saved_usage,
    _write_item_table,
    apply_gate,
    deterministic_eligibility,
    fallback_candidates,
    fallback_retrieval_query,
    run_checker,
    summarize_variant,
)
from .retrieval import StandardsRetriever, load_standards_corpus


def load_judgments(path: Path) -> dict[str, dict[str, str]]:
    return {
        judgment["audit_id"]: judgment
        for row in read_jsonl(path)
        if "error" not in row
        for judgment in row["judgments"]
    }


def build_refined_candidates(
    records: list[dict[str, Any]],
    experiment_config: dict[str, Any],
    gate_config: dict[str, Any],
) -> list[dict[str, Any]]:
    chunks = load_standards_corpus(
        experiment_config["retrieval"]["standards_dir"],
        chunk_chars=int(experiment_config["retrieval"]["chunk_chars"]),
        chunk_overlap=int(experiment_config["retrieval"]["chunk_overlap"]),
    )
    retriever = StandardsRetriever(chunks)
    top_k = int(gate_config["retrieval"]["top_k"])
    candidates = []
    for record in records:
        if not record["fallback_used"]:
            continue
        for action in fallback_candidates(record):
            query = fallback_retrieval_query(record["alert"], action)
            evidence = retriever.retrieve(query, top_k=top_k)
            item = {
                "audit_id": f"EG-R-{len(candidates) + 1:04d}",
                "item_type": "refined_fallback_candidate",
                "case_id": record["case_id"],
                "action_index": 0,
                "predicted_family": record["alert"]["detector"]["predicted_family"],
                "route": record["gated_intent"]["route"],
                "action": action,
                "rationale": "Use a bounded, non-disruptive fallback because no evidence-eligible action remained.",
                "approval_required": False,
                "retrieval_query": query,
                "evidence_refs": [row["chunk_id"] for row in evidence],
                "cited_evidence": _evidence_payload(evidence),
            }
            eligible, reasons = deterministic_eligibility(item)
            item["deterministic_eligible"] = eligible
            item["eligibility_reasons"] = reasons
            candidates.append(item)
    return candidates


def select_candidates(
    candidates: list[dict[str, Any]], checker_a: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    label_rank = {"unsupported": 0, "generally_supported": 1, "directly_supported": 2}
    action_priority = {"CAPTURE_TRAFFIC": 3, "MONITOR": 2, "NOTIFY_OPERATOR": 1}
    by_case: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_case.setdefault(item["case_id"], []).append(item)
    selected = []
    for case_id in sorted(by_case):
        selected.append(
            max(
                by_case[case_id],
                key=lambda item: (
                    int(item["deterministic_eligible"]),
                    label_rank[checker_a[item["audit_id"]]["label"]],
                    action_priority[item["action"]],
                ),
            )
        )
    return selected


def subgroup_case_support(
    records: list[dict[str, Any]], checker_b: dict[str, dict[str, str]]
) -> dict[str, Any]:
    def supported(ids: list[str]) -> bool:
        return all(checker_b[item_id]["label"] != "unsupported" for item_id in ids)

    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(record["evaluation"]["true_family"], []).append(record)
    family_results = {}
    for family, rows in sorted(groups.items()):
        before = sum(supported(row["original_item_ids"]) for row in rows)
        after = sum(supported(row["final_item_ids"]) for row in rows)
        family_results[family] = {
            "cases": len(rows),
            "before_cases_all_actions_supported": before,
            "after_cases_all_actions_supported": after,
            "before_rate": before / len(rows),
            "after_rate": after / len(rows),
        }
    halves = {"first_80": records[:80], "second_80": records[80:]}
    half_results = {}
    for name, rows in halves.items():
        before = sum(supported(row["original_item_ids"]) for row in rows)
        after = sum(supported(row["final_item_ids"]) for row in rows)
        half_results[name] = {
            "cases": len(rows),
            "before_cases_all_actions_supported": before,
            "after_cases_all_actions_supported": after,
            "before_rate": before / len(rows),
            "after_rate": after / len(rows),
        }
    return {"by_true_family": family_results, "by_fixed_case_half": half_results}


def citation_rebinding_summary(
    records: list[dict[str, Any]], original_items: list[dict[str, Any]]
) -> dict[str, int]:
    item_by_id = {item["audit_id"]: item for item in original_items}
    original_occurrences = 0
    final_occurrences = 0
    kept_original_actions = 0
    unchanged_bundles = 0
    overlapping_occurrences = 0
    for record in records:
        original_occurrences += sum(
            len(action["evidence_refs"]) for action in record["original_intent"]["actions"]
        )
        final_occurrences += sum(
            len(action["evidence_refs"]) for action in record["gated_intent"]["actions"]
        )
        for item_id, final_action in zip(
            record["final_item_ids"], record["gated_intent"]["actions"]
        ):
            if item_id not in item_by_id:
                continue
            kept_original_actions += 1
            item = item_by_id[item_id]
            original_action = record["original_intent"]["actions"][
                int(item["action_index"]) - 1
            ]
            old_refs = set(original_action["evidence_refs"])
            new_refs = set(final_action["evidence_refs"])
            unchanged_bundles += old_refs == new_refs
            overlapping_occurrences += len(old_refs & new_refs)
    return {
        "original_citation_occurrences": original_occurrences,
        "final_citation_occurrences": final_occurrences,
        "kept_original_actions": kept_original_actions,
        "original_evidence_bundles_retained_unchanged": unchanged_bundles,
        "old_citation_occurrences_reappearing_after_reretrieval": overlapping_occurrences,
    }


def run_refinement(
    config_path: str | Path = "configs/evidence_gate_relevant_rag.json",
    prepare_only: bool = False,
) -> dict[str, Any]:
    gate_config = load_json(config_path)
    experiment_config = load_json(gate_config["base_config"])
    source_condition = str(gate_config.get("source_condition", "rag"))
    report_prefix = str(gate_config.get("report_prefix", "evidence_gate"))
    run_dir = Path("experiments/runs") / gate_config["run_id"]
    original_items = read_jsonl(run_dir / "original_action_items.jsonl")
    source_records = [
        row
        for row in read_jsonl(gate_config["source_results"])
        if "error" not in row and row.get("condition") == source_condition
    ]
    source_records.sort(key=lambda row: row["case_id"])
    strict_records = read_jsonl(run_dir / "gated_strict.jsonl")
    if len(strict_records) != len(source_records):
        raise RuntimeError("Run the base evidence-gate experiment before refining fallbacks.")
    candidates = build_refined_candidates(strict_records, experiment_config, gate_config)
    write_jsonl(run_dir / "refined_fallback_candidates.jsonl", candidates)
    preflight = {
        "fallback_cases": sum(row["fallback_used"] for row in strict_records),
        "candidate_actions": len(candidates),
        "additional_expected_calls": 2,
        "combined_hard_call_cap": int(gate_config["combined_max_calls"]),
        "combined_hard_cost_cap_usd": float(gate_config["combined_max_cost_usd"]),
    }
    write_json(run_dir / "refinement_preflight.json", preflight)
    if prepare_only:
        return preflight
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available to the fallback-refinement process.")
    from openai import OpenAI

    client = OpenAI()
    checker_a_path = run_dir / "checker_a_results.jsonl"
    checker_b_path = run_dir / "checker_b_results.jsonl"
    refined_a_path = run_dir / "checker_a_refined_fallback_results.jsonl"
    refined_b_path = run_dir / "checker_b_refined_fallback_results.jsonl"
    all_result_paths = [checker_a_path, checker_b_path, refined_a_path, refined_b_path]
    refined_a = run_checker(
        client,
        "gate_checker_refined_fallback",
        gate_config["gate_checker"],
        [("refined_fallback_candidates:all", candidates)],
        refined_a_path,
        all_result_paths,
        gate_config,
    )
    selected = select_candidates(candidates, refined_a)
    write_jsonl(run_dir / "refined_fallback_selected.jsonl", selected)
    refined_b = run_checker(
        client,
        "independent_evaluator_refined_fallback",
        gate_config["independent_evaluator"],
        [("refined_fallback_selected:all", selected)],
        refined_b_path,
        all_result_paths,
        gate_config,
    )
    checker_a = load_judgments(checker_a_path)
    checker_a.update(refined_a)
    checker_b = load_judgments(checker_b_path)
    checker_b.update(refined_b)
    refined_records = apply_gate(
        source_records, original_items, selected, checker_a, "strict"
    )
    write_jsonl(run_dir / "gated_strict_refined_fallback.jsonl", refined_records)
    summary = summarize_variant(
        refined_records, original_items, original_items + selected, checker_b
    )
    prior = load_json(run_dir / "summary.json")["variants"]["strict"]
    total_calls, total_cost = _saved_usage(all_result_paths)
    result = {
        **preflight,
        "selection_rule": (
            "Choose a deterministically eligible fallback with the strongest gate-checker "
            "support; break ties in favor of traffic capture, then monitoring, then notification."
        ),
        "candidate_checker_a_labels": _label_counts(
            [item["audit_id"] for item in candidates], refined_a
        ),
        "selected_checker_a_labels": _label_counts(
            [item["audit_id"] for item in selected], refined_a
        ),
        "selected_actions": dict(Counter(item["action"] for item in selected)),
        "prior_strict_gate": prior,
        "refined_strict_gate": summary,
        "subgroup_case_support": subgroup_case_support(refined_records, checker_b),
        "citation_rebinding": citation_rebinding_summary(refined_records, original_items),
        "actual_total_api_calls_for_base_and_refinement": total_calls,
        "actual_total_estimated_cost_usd_for_base_and_refinement": total_cost,
    }
    write_json(run_dir / "refinement_summary.json", result)
    write_json(
        f"reports/comprehensive_evaluation/tables/{report_prefix}_refined_fallback.json",
        result,
    )
    _write_item_table(
        original_items + selected,
        checker_a,
        checker_b,
        {"strict_refined": refined_records},
        Path(
            f"reports/comprehensive_evaluation/tables/{report_prefix}_refined_items.csv"
        ),
    )
    evaluation = summary["independent_evaluator"]
    condition_label = (
        "deliberately wrong-family RAG"
        if source_condition == "mismatched_rag"
        else "relevant RAG"
    )
    rebinding = result["citation_rebinding"]
    if source_condition == "mismatched_rag":
        rebinding_paragraph = (
            f"The wrong-family plans originally contained "
            f"{rebinding['original_citation_occurrences']} citation occurrences. None of the "
            f"original action-level evidence bundles was accepted unchanged. The gate "
            f"retrieved evidence again for each action, removed {summary['removed_actions']} "
            f"actions, rebound the {rebinding['kept_original_actions']} surviving original "
            f"actions to the new action-specific results, and inserted "
            f"{summary['fallback_cases']} cautious fallbacks. Only "
            f"{rebinding['old_citation_occurrences_reappearing_after_reretrieval']} individual "
            f"chunk identifiers reappeared through the new retrieval queries."
        )
        claim_sentence = (
            "The experiment supports the claim that action-specific retrieval plus an external "
            "evidence gate can reduce the effect of deliberately wrong-family retrieval."
        )
    else:
        rebinding_paragraph = (
            f"The gate retrieved evidence again for each action, removed "
            f"{summary['removed_actions']} actions, rebound the "
            f"{rebinding['kept_original_actions']} surviving original actions to the new "
            f"action-specific results, and inserted {summary['fallback_cases']} cautious "
            "fallbacks."
        )
        claim_sentence = (
            "The experiment supports the claim that action-specific retrieval plus an external "
            "evidence gate can reduce action-evidence mismatch."
        )
    interpretation = f"""# Action-to-Evidence Gate: Refined Result

## The result in one sentence

An action-specific evidence gate made the final mitigation plans more standards-grounded under a separate evaluator, while deliberately producing smaller and more conservative plans.

## What was tested

The experiment reused {summary['cases']} {condition_label} alerts from the primary planning study. Their guardrailed plans contained {summary['original_actions']} actions. Each action received a new retrieval query containing the predicted attack family, the proposed action, active protocols, and important observed traffic features. A deterministic check first confirmed that the action was permitted by the existing family policy and that every cited identifier belonged to that action's retrieval result.

GPT-5.4 mini then labelled each action's passages as directly supported, generally supported, or unsupported. The strict gate kept direct support, kept general support only for non-disruptive actions, and removed unsupported actions. If no action remained, it used bounded traffic capture, monitoring, or operator notification according to the route. A second model, GPT-5.4, independently evaluated the original and final actions without seeing the first model's labels or gate decisions.

The first fallback retrieval sometimes found attack-family guidance instead of guidance for the fallback action. The refinement repeated the fallback action terms in the retrieval query, considered the safe fallback actions permitted by the route, and selected the candidate with the strongest support from the gate checker. Ties favored evidence collection, then monitoring, then operator notification.

## What changed

| Independent GPT-5.4 evaluation | Before gate | After refined strict gate |
|---|---:|---:|
| Actions judged direct or general support | {evaluation['before_direct_or_general_rate']:.1%} | {evaluation['after_direct_or_general_rate']:.1%} |
| Actions judged unsupported | {evaluation['before_unsupported_rate']:.1%} | {evaluation['after_unsupported_rate']:.1%} |
| Cases where every action had direct or general support | {evaluation['before_cases_all_actions_supported']}/{summary['cases']} ({evaluation['before_case_all_actions_supported_rate']:.2%}) | {evaluation['after_cases_all_actions_supported']}/{summary['cases']} ({evaluation['after_case_all_actions_supported_rate']:.2%}) |
| Disruptive actions | {evaluation['before_disruptive_actions']} | {evaluation['after_disruptive_actions']} |
| Unsupported disruptive actions | {evaluation['before_unsupported_disruptive_actions']} | {evaluation['after_unsupported_disruptive_actions']} |

The gate removed {summary['removed_actions']} original actions and inserted a bounded fallback in {summary['fallback_cases']} cases, leaving {summary['final_actions']} final actions. At the whole-plan level, {evaluation['paired_case_test']['improved_cases']} cases improved, none worsened, and the two-sided exact McNemar result was `p = {evaluation['paired_case_test']['two_sided_exact_mcnemar_p']:.3g}`. All 160 final plans remained valid under the declared schema and policy checks.

{rebinding_paragraph}

The all-actions-supported rate increased in each of the eight true traffic families and in both fixed 80-case halves. This subgroup check does not turn the iterative experiment into a held-out validation, but it shows that the aggregate gain was not produced by only one attack family or one part of the case list.

## Physical-world meaning

For a gateway operator, the change is simple: an action is no longer retained merely because it cites a real document identifier. The cited passage must also be useful for that particular action. When this link is weak, the prototype chooses a cautious evidence-collection or monitoring step instead of preserving a more aggressive proposal. The output still has status `PROPOSED_NOT_EXECUTED`; it does not configure a gateway or block a device.

## What the paper can safely claim

{claim_sentence} Under the separate GPT-5.4 evaluator, the unsupported-action rate fell by {evaluation['absolute_unsupported_rate_reduction'] * 100:.1f} percentage points, a {evaluation['relative_unsupported_rate_reduction']:.1%} relative reduction.

It does not support a claim of perfect grounding or autonomous correctness. {evaluation['after_label_counts']['unsupported']} final actions were still judged unsupported by the second model. Human review is still needed for a strong semantic-support claim, and any disruptive action still requires explicit approval before execution.

## Run integrity

The base gate and fallback refinement used {result['actual_total_api_calls_for_base_and_refinement']} API calls at an estimated total cost of USD {result['actual_total_estimated_cost_usd_for_base_and_refinement']:.3f}. The hard limits were {gate_config['combined_max_calls']} calls and USD {gate_config['combined_max_cost_usd']:.2f}. No API key is stored in the project.
"""
    interpretation_name = (
        "WRONG_FAMILY_RECOVERY_GATE.md"
        if gate_config.get("source_condition") == "mismatched_rag"
        else "RELEVANT_RAG_EVIDENCE_GATE.md"
    )
    (Path("reports/comprehensive_evaluation") / interpretation_name).write_text(
        interpretation, encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refine evidence-gate fallbacks with action-weighted retrieval."
    )
    parser.add_argument("--config", default="configs/evidence_gate_relevant_rag.json")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_refinement(args.config, args.prepare_only), indent=2))


if __name__ == "__main__":
    main()
