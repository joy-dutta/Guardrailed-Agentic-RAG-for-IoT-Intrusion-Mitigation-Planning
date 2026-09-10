from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(".matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .common import load_json, read_jsonl, write_json
from .hierarchical_detector import binary_metrics


FINAL_RUN = Path("experiments/runs/paper_final_v2")


def paired_exact_test(
    rows: list[dict[str, Any]],
    rag_value,
    no_rag_value,
) -> dict[str, Any]:
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        pairs[row["case_id"]][row["condition"]] = row
    rag_only = 0
    no_rag_only = 0
    for pair in pairs.values():
        if "rag" not in pair or "no_rag" not in pair:
            continue
        rag_success = bool(rag_value(pair["rag"]))
        no_rag_success = bool(no_rag_value(pair["no_rag"]))
        rag_only += int(rag_success and not no_rag_success)
        no_rag_only += int(no_rag_success and not rag_success)
    discordant = rag_only + no_rag_only
    p_value = (
        float(binomtest(min(rag_only, no_rag_only), discordant, 0.5).pvalue)
        if discordant
        else 1.0
    )
    return {
        "rag_only_successes": rag_only,
        "no_rag_only_successes": no_rag_only,
        "discordant_pairs": discordant,
        "two_sided_exact_p": p_value,
    }


def before_after_exact_test(
    rows: list[dict[str, Any]], raw_key: str, normalized_key: str
) -> dict[str, Any]:
    normalized_only = sum(
        not row["validity"][raw_key] and row["validity"][normalized_key]
        for row in rows
    )
    raw_only = sum(
        row["validity"][raw_key] and not row["validity"][normalized_key]
        for row in rows
    )
    discordant = normalized_only + raw_only
    p_value = (
        float(binomtest(min(normalized_only, raw_only), discordant, 0.5).pvalue)
        if discordant
        else 1.0
    )
    return {
        "normalized_only_successes": normalized_only,
        "raw_only_successes": raw_only,
        "discordant_records": discordant,
        "two_sided_exact_p": p_value,
    }


def export_detector_tables() -> pd.DataFrame:
    detector = load_json("reports/tables/detector_results.json")
    extra = load_json("reports/tables/detector_extra_trees_benchmark.json")
    rows = []
    for name, result in detector.items():
        rows.append(
            {
                "model": "Random Forest",
                "feature_set": name,
                "features": result["feature_count"],
                "accuracy": result["calibrated"]["accuracy"],
                "balanced_accuracy": result["calibrated"]["balanced_accuracy"],
                "macro_f1": result["calibrated"]["macro_f1"],
                "ece_15_bin": result["calibrated"]["ece_15_bin"],
                "confidence_threshold": result["selected_threshold"],
                "automatic_coverage": result["confidence_aware"]["coverage"],
                "selective_accuracy": result["confidence_aware"]["selective_accuracy"],
            }
        )
    rows.append(
        {
            "model": "Extra Trees",
            "feature_set": "leakage_controlled",
            "features": extra["feature_count"],
            "accuracy": extra["calibrated"]["accuracy"],
            "balanced_accuracy": extra["calibrated"]["balanced_accuracy"],
            "macro_f1": extra["calibrated"]["macro_f1"],
            "ece_15_bin": extra["calibrated"]["ece_15_bin"],
            "confidence_threshold": extra["selected_threshold"],
            "automatic_coverage": extra["confidence_aware"]["coverage"],
            "selective_accuracy": extra["confidence_aware"]["selective_accuracy"],
        }
    )
    comparison = pd.DataFrame(rows)
    comparison.to_csv("reports/tables/detector_model_comparison.csv", index=False)

    primary = detector["leakage_controlled"]["calibrated"]
    per_class = pd.DataFrame.from_dict(primary["per_class"], orient="index")
    per_class.index.name = "family"
    per_class.reset_index().to_csv("reports/tables/detector_per_family.csv", index=False)
    return comparison


def export_strengthened_detector_tables() -> dict[str, Any]:
    protocols = load_json("reports/tables/detector_split_protocols.json")
    primary = protocols["attack_type_aware"]
    per_class = pd.DataFrame.from_dict(primary["calibrated"]["per_class"], orient="index")
    per_class.index.name = "family"
    per_class.reset_index().to_csv(
        "reports/tables/detector_per_family_attack_type_aware.csv", index=False
    )

    predictions = pd.read_csv(
        "data/processed/test_predictions_protocol_attack_type_aware.csv",
        usecols=["family", "predicted_family"],
    )
    binary = binary_metrics(
        predictions["family"].to_numpy(), predictions["predicted_family"].to_numpy()
    )
    write_json("reports/tables/detector_binary_attack_metrics.json", binary)

    sample = pd.read_csv(
        "data/processed/ciciot2023_family_sample.csv",
        usecols=["family", "attack_type"],
    )
    mapping = sample.drop_duplicates().sort_values(["family", "attack_type"])
    mapping.to_csv("reports/tables/attack_family_mapping.csv", index=False)
    return {"protocols": protocols, "binary": binary}


def export_agent_tables(summary: dict[str, Any]) -> None:
    rows = []
    for condition, values in summary["conditions"].items():
        rows.append(
            {
                "condition": condition,
                "records": values["records"],
                "raw_json_validity": values["raw_json_validity"],
                "raw_compact_schema_validity": values["raw_compact_schema_validity"],
                "raw_full_schema_validity": values["raw_full_schema_validity"],
                "raw_policy_conformance": values["raw_policy_conformance"],
                "valid_evidence_attachment_rate": values["valid_evidence_attachment_rate"],
                "normalized_full_schema_validity": values["normalized_full_schema_validity"],
                "normalized_policy_conformance": values["normalized_policy_conformance"],
                "mean_evidence_references": values["mean_evidence_references"],
                "mean_retrieval_seconds": values["mean_retrieval_seconds"],
                "mean_llm_seconds": values["mean_llm_seconds"],
                "mean_end_to_end_seconds": values["mean_end_to_end_seconds"],
                "input_tokens": values["input_tokens"],
                "output_tokens": values["output_tokens"],
                "estimated_cost_usd": values["estimated_cost_usd"],
            }
        )
    pd.DataFrame(rows).to_csv("reports/tables/agent_ablation.csv", index=False)


def plot_detector_comparison(comparison: pd.DataFrame) -> None:
    labels = [
        "RF\nall features",
        "RF\nleakage-controlled",
        "Extra Trees\nleakage-controlled",
    ]
    x = np.arange(len(labels))
    width = 0.34
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x - width / 2, comparison["macro_f1"], width, label="Macro-F1", color="#287271")
    ax.bar(
        x + width / 2,
        comparison["balanced_accuracy"],
        width,
        label="Balanced accuracy",
        color="#E07A5F",
    )
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig("reports/figures/detector_model_comparison.png", dpi=240)
    plt.close(fig)


def plot_grounding(summary: dict[str, Any]) -> None:
    values = [
        summary["conditions"]["no_rag"]["valid_evidence_attachment_rate"],
        summary["conditions"]["rag"]["valid_evidence_attachment_rate"],
    ]
    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    bars = ax.bar(["No RAG", "Official-standards RAG"], values, color=["#8D99AE", "#287271"])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Answers with valid standards references")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.1%}", ha="center")
    fig.tight_layout()
    fig.savefig("reports/figures/rag_grounding_comparison.png", dpi=240)
    plt.close(fig)


def plot_guardrails(summary: dict[str, Any]) -> None:
    metrics = [
        ("raw_full_schema_validity", "Raw full schema"),
        ("normalized_full_schema_validity", "Guardrailed full schema"),
        ("raw_policy_conformance", "Raw policy"),
        ("normalized_policy_conformance", "Guardrailed policy"),
    ]
    x = np.arange(len(metrics))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.0, 4.3))
    for offset, condition, color in [
        (-0.5, "no_rag", "#8D99AE"),
        (0.5, "rag", "#287271"),
    ]:
        values = [summary["conditions"][condition][key] for key, _ in metrics]
        ax.bar(
            x + offset * width,
            values,
            width,
            label=condition.replace("_", " ").upper(),
            color=color,
        )
    ax.set_xticks(x, [label for _, label in metrics])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Fraction of outputs")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncols=2)
    fig.tight_layout()
    fig.savefig("reports/figures/guardrail_ablation.png", dpi=240)
    plt.close(fig)


def plot_retrieval_audit(audit: dict[str, Any]) -> None:
    families = sorted(audit["by_family"])
    direct = [audit["by_family"][family].get("direct", 0) / 6 for family in families]
    supporting = [audit["by_family"][family].get("supporting", 0) / 6 for family in families]
    irrelevant = [audit["by_family"][family].get("irrelevant", 0) / 6 for family in families]
    y = np.arange(len(families))
    fig, ax = plt.subplots(figsize=(7.0, 4.7))
    ax.barh(y, direct, label="Direct", color="#287271")
    ax.barh(y, supporting, left=direct, label="Supporting", color="#E9C46A")
    left = np.asarray(direct) + np.asarray(supporting)
    ax.barh(y, irrelevant, left=left, label="Irrelevant", color="#E76F51")
    ax.set_yticks(y, families)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of audited top-3 chunks")
    ax.legend(frameon=False, ncols=3, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig("reports/figures/retrieval_relevance_audit.png", dpi=240)
    plt.close(fig)


def plot_strengthened_evidence(
    faithfulness: dict[str, Any], binding: dict[str, Any]
) -> None:
    values = [
        faithfulness["by_condition"]["shuffled_rag"][
            "direct_or_general_support_rate"
        ],
        faithfulness["by_condition"]["rag"]["direct_or_general_support_rate"],
        binding["direct_or_general_support_rate"],
    ]
    labels = ["Wrong-family\nretrieval", "Relevant RAG\noriginal actions", "Action-specific\nevidence binding"]
    fig, ax = plt.subplots(figsize=(7.3, 4.3))
    ax.bar(labels, values, color=["#E07A5F", "#E9C46A", "#287271"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Actions with direct or general evidence support")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/action_evidence_support.png", dpi=240)
    plt.close(fig)


def plot_guardrail_stress(stress: dict[str, Any]) -> None:
    labels = ["Compact\nschema", "Action\npolicy"]
    raw = [stress["raw_compact_schema_validity"], stress["raw_policy_conformance"]]
    normalized = [stress["schema_validity"], stress["policy_conformance"]]
    x = np.arange(len(labels))
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.bar(x - width / 2, raw, width, label="Mutated raw proposal", color="#E07A5F")
    ax.bar(x + width / 2, normalized, width, label="After guardrails", color="#287271")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Fraction passing")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig("reports/figures/guardrail_mutation_stress.png", dpi=240)
    plt.close(fig)


def run_analysis() -> dict[str, Any]:
    rows = read_jsonl(FINAL_RUN / "results.jsonl")
    summary = load_json(FINAL_RUN / "summary.json")
    audit = load_json("reports/tables/retrieval_audit_summary.json")
    strengthened_detector = export_strengthened_detector_tables()
    detector_protocols = strengthened_detector["protocols"]
    detector = detector_protocols["attack_type_aware"]
    strict_detector = detector_protocols["strict_family_file"]
    row_detector = detector_protocols["stratified_rows"]
    hierarchical = load_json("reports/tables/hierarchical_detector.json")
    repeated_seeds = load_json("reports/tables/detector_repeated_seeds.json")
    interrater = load_json(
        "reports/tables/retrieval_audit_interrater_agreement_v2.json"
    )
    exploratory = load_json("experiments/runs/paper_main/summary.json")
    prior_final = load_json("experiments/runs/paper_final/summary.json")
    second_audit_v1 = load_json("reports/tables/retrieval_audit_second_blinded.json")
    second_audit_v2 = load_json("reports/tables/retrieval_audit_second_blinded_v2.json")
    family_routing = load_json("reports/tables/family_specific_routing.json")
    error_propagation = load_json("reports/tables/detector_error_propagation.json")
    guardrail_stress = load_json("reports/tables/guardrail_mutation_stress.json")
    alternatives = load_json("reports/tables/detector_alternative_models.json")
    shuffled_control = load_json("reports/tables/shuffled_rag_control.json")
    faithfulness = load_json("reports/tables/action_evidence_faithfulness.json")
    evidence_binding = load_json("reports/tables/action_evidence_binding.json")

    comparison = export_detector_tables()
    export_agent_tables(summary)
    plot_detector_comparison(comparison)
    plot_grounding(summary)
    plot_guardrails(summary)
    plot_retrieval_audit(audit)
    plot_strengthened_evidence(faithfulness, evidence_binding)
    plot_guardrail_stress(guardrail_stress)

    statistics = {
        "rag_valid_reference_paired_test": paired_exact_test(
            rows,
            rag_value=lambda row: bool(row["raw_intent"].get("evidence_used"))
            and row["validity"]["citation_ids_valid"],
            no_rag_value=lambda row: bool(row["raw_intent"].get("evidence_used"))
            and row["validity"]["citation_ids_valid"],
        ),
        "full_schema_guardrail_test": before_after_exact_test(
            rows, "raw_full_schema_valid", "normalized_full_schema_valid"
        ),
        "policy_guardrail_test": before_after_exact_test(
            rows, "raw_policy_valid", "normalized_policy_valid"
        ),
    }
    result = {
        "paper_run": summary,
        "detector_primary": {
            "protocol": "attack_type_aware",
            "meaning": "Known attack types remain represented; source files are held out when at least three files exist for that attack type.",
            "macro_f1": detector["calibrated"]["macro_f1"],
            "balanced_accuracy": detector["calibrated"]["balanced_accuracy"],
            "ece_15_bin": detector["calibrated"]["ece_15_bin"],
            "selected_threshold": detector["selected_threshold"],
            "confidence_aware": detector["confidence_aware"],
            "target_selective_accuracy": 0.95,
            "target_met": detector["confidence_aware"]["selective_accuracy"] >= 0.95,
            "binary_attack_detection": strengthened_detector["binary"],
            "five_seed_stability": repeated_seeds["summary"]["attack_type_aware"],
        },
        "detector_protocol_comparison": {
            "stratified_rows_optimistic_benchmark": {
                "macro_f1": row_detector["calibrated"]["macro_f1"],
                "balanced_accuracy": row_detector["calibrated"]["balanced_accuracy"],
                "confidence_aware": row_detector["confidence_aware"],
            },
            "attack_type_aware_primary": {
                "macro_f1": detector["calibrated"]["macro_f1"],
                "balanced_accuracy": detector["calibrated"]["balanced_accuracy"],
                "confidence_aware": detector["confidence_aware"],
            },
            "strict_unseen_file_subtype_stress_test": {
                "macro_f1": strict_detector["calibrated"]["macro_f1"],
                "balanced_accuracy": strict_detector["calibrated"]["balanced_accuracy"],
                "confidence_aware": strict_detector["confidence_aware"],
            },
            "hierarchical_sanity_check": {
                "macro_f1": hierarchical["calibrated"]["macro_f1"],
                "balanced_accuracy": hierarchical["calibrated"]["balanced_accuracy"],
                "confidence_aware": hierarchical["confidence_aware"],
                "interpretation": "The small gain over the flat model does not justify additional deployment complexity.",
            },
            "five_seed_stability": repeated_seeds,
        },
        "retrieval_audit": audit,
        "retrieval_interrater": interrater,
        "family_specific_routing": family_routing,
        "detector_error_propagation": error_propagation,
        "guardrail_mutation_stress": guardrail_stress,
        "detector_alternative_models": alternatives,
        "shuffled_rag_control": shuffled_control,
        "action_evidence_faithfulness": faithfulness,
        "action_specific_evidence_binding": evidence_binding,
        "paired_statistics": statistics,
        "development_cost_ledger": {
            "exploratory_run_usd": exploratory["actual_estimated_cost_usd"],
            "prior_final_run_usd": prior_final["actual_estimated_cost_usd"],
            "strengthened_final_run_usd": summary["actual_estimated_cost_usd"],
            "second_audit_v1_usd": second_audit_v1["estimated_cost_usd"],
            "second_audit_v2_usd": second_audit_v2["estimated_cost_usd"],
            "shuffled_retrieval_control_usd": shuffled_control[
                "actual_estimated_cost_usd"
            ],
            "action_evidence_faithfulness_audit_usd": faithfulness[
                "estimated_cost_usd"
            ],
            "action_evidence_binding_audit_usd": evidence_binding[
                "estimated_cost_usd"
            ],
            "strengthening_successful_calls": shuffled_control["actual_calls"]
            + faithfulness["calls"]
            + evidence_binding["calls"],
            "strengthening_api_cost_usd": shuffled_control[
                "actual_estimated_cost_usd"
            ]
            + faithfulness["estimated_cost_usd"]
            + evidence_binding["estimated_cost_usd"],
            "total_estimated_usd": exploratory["actual_estimated_cost_usd"]
            + prior_final["actual_estimated_cost_usd"]
            + summary["actual_estimated_cost_usd"]
            + second_audit_v1["estimated_cost_usd"]
            + second_audit_v2["estimated_cost_usd"]
            + shuffled_control["actual_estimated_cost_usd"]
            + faithfulness["estimated_cost_usd"]
            + evidence_binding["estimated_cost_usd"],
        },
        "claim_assessment": {
            "supported": [
                "Official-standards RAG substantially increases valid standards references.",
                "In the 32-alert pilot audit, relevant retrieval supported more proposed actions than the wrong-family control; the larger journal control is reported separately and narrows this claim.",
                "Action-specific post-guardrail retrieval increases evidence support for final bounded actions.",
                "Deterministic normalization enforces the full executor-facing schema and bounded policy.",
                "The tested guardrails preserved all declared invariants across 576 mutated proposals.",
                "Top-two conservative action filtering removed wrong-family disruptive actions in the intentionally misclassified cases.",
                "The pipeline is practical for offline intent generation at modest latency and API cost.",
            ],
            "not_supported_or_out_of_scope": [
                "The detector is not state of the art and remains weak on Web, Recon, BruteForce, and benign specificity.",
                "RAG alone does not improve raw action-policy conformance.",
                "Neither relevant RAG nor action-specific binding provides universal action-level standards support.",
                "Family-specific confidence thresholds do not guarantee the target under held-out-file distribution shift.",
                "The experiment does not execute mitigations or measure operational attack suppression.",
                "The strict unseen-file/subtype stress test does not reach the 95 percent selective-accuracy target.",
            ],
        },
    }
    write_json("reports/tables/final_analysis.json", result)
    return result


if __name__ == "__main__":
    result = run_analysis()
    print(json.dumps(result, indent=2))
