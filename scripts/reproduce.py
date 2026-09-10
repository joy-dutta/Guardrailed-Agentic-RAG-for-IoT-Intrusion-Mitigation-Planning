"""Cross-platform entry point for reproducing the IoT mitigation experiments."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "experiment.json"
JOURNAL_CONFIG = ROOT / "configs" / "planning_study_160_alerts.json"
MODEL_SENSITIVITY_CONFIG = ROOT / "configs" / "planner_model_sensitivity.json"
EVIDENCE_GATE_CONFIG = ROOT / "configs" / "evidence_gate_relevant_rag.json"
MISMATCHED_GATE_CONFIG = ROOT / "configs" / "evidence_gate_wrong_family.json"


def run(command: list[str]) -> None:
    """Run one stage from the repository root and stop on the first error."""
    print("\n+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def module(name: str, *args: str) -> list[str]:
    return [sys.executable, "-m", name, *args]


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set in this process. See the root README before "
            "running a paid stage."
        )


def approve_paid_stage(label: str, calls: int, cost: float, yes: bool) -> None:
    print(f"\n{label}")
    print(f"Configured call ceiling: {calls}")
    print(f"Configured estimated-cost ceiling: USD {cost:.2f}")
    print(
        "This is a local estimate based on prices stored in the configuration, "
        "not an account billing limit."
    )
    if yes:
        return
    if not sys.stdin.isatty():
        raise SystemExit("Use --yes after reviewing the configured API limits.")
    answer = input("Continue with this paid stage? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("Paid stage cancelled.")


def bootstrap() -> None:
    run([sys.executable, str(ROOT / "scripts" / "bootstrap_inputs.py")])


def smoke() -> None:
    run(module("pytest", "-q"))


def offline() -> None:
    stages: list[tuple[str, list[str]]] = [
        ("Prepare deterministic dataset sample", module("iot_poc.dataset", "--config", str(CONFIG))),
        ("Train primary detector", module("iot_poc.detector", "--config", str(CONFIG))),
        ("Run Extra Trees sanity baseline", module("iot_poc.detector_benchmark", "--config", str(CONFIG))),
        ("Select legacy fixed alerts", module("iot_poc.alerts", "--config", str(CONFIG))),
        ("Build split protocols", module("iot_poc.split_protocols", "--config", str(CONFIG))),
        ("Evaluate split protocols", module("iot_poc.detector_protocols", "--config", str(CONFIG))),
        ("Run hierarchical detector check", module("iot_poc.hierarchical_detector", "--config", str(CONFIG))),
        ("Repeat fixed seeds", module("iot_poc.detector_repeated_seeds", "--config", str(CONFIG))),
        ("Evaluate family-specific routing", module("iot_poc.family_routing", "--config", str(CONFIG))),
        ("Evaluate detector alternatives", module("iot_poc.detector_alternatives", "--config", str(CONFIG))),
        ("Select fixed reference alerts", module("iot_poc.alerts_protocol")),
        (
            "Evaluate detector-error propagation",
            module(
                "iot_poc.error_propagation",
                "--run-id",
                "reference_evaluation/paired_rag_no_rag_32_alerts",
            ),
        ),
        (
            "Run 576 guardrail mutations",
            module(
                "iot_poc.guardrail_stress",
                "--run-id",
                "reference_evaluation/paired_rag_no_rag_32_alerts",
            ),
        ),
    ]
    for label, command in stages:
        print(f"\n=== {label} ===")
        run(command)
    smoke()
    run(module("iot_poc.provenance"))


def journal_offline() -> None:
    """Run the no-cost IEEE Access extensions in dependency order."""
    stages: list[tuple[str, list[str]]] = [
        (
            "Compare confidence-calibration methods",
            module("iot_poc.journal_calibration", "--config", str(JOURNAL_CONFIG)),
        ),
        (
            "Select the fixed 160-alert planning sample",
            module("iot_poc.journal_cases", "--config", str(JOURNAL_CONFIG)),
        ),
        (
            "Compare detector families",
            module("iot_poc.journal_detector_sensitivity", "--config", str(JOURNAL_CONFIG)),
        ),
        (
            "Compare global and family-aware routing",
            module("iot_poc.journal_family_routing", "--config", str(JOURNAL_CONFIG)),
        ),
    ]
    for label, command in stages:
        print(f"\n=== {label} ===")
        run(command)
    smoke()


def journal_agent(yes: bool) -> None:
    """Repeat the 160-alert, three-condition planning experiment."""
    require_api_key()
    config = load_config(JOURNAL_CONFIG)["planning"]
    approve_paid_stage(
        "Expanded relevant-RAG, no-RAG, and wrong-family-RAG experiment",
        int(config["max_calls"]),
        float(config["max_cost_usd"]),
        yes,
    )
    run(module("iot_poc.journal_agent", "--config", str(JOURNAL_CONFIG)))
    run(module("iot_poc.journal_policy_baseline", "--config", str(JOURNAL_CONFIG)))
    run(module("iot_poc.journal_statistics", "--config", str(JOURNAL_CONFIG)))
    run(module("iot_poc.journal_human_audit", "--config", str(JOURNAL_CONFIG)))


def model_sensitivity(yes: bool) -> None:
    """Repeat the fixed 32-alert subset with the stronger planning model."""
    run(
        module(
            "iot_poc.journal_model_sensitivity",
            "--config",
            str(MODEL_SENSITIVITY_CONFIG),
        )
    )
    require_api_key()
    config = load_config(MODEL_SENSITIVITY_CONFIG)["planning"]
    approve_paid_stage(
        "Stronger-model sensitivity experiment",
        int(config["max_calls"]),
        float(config["max_cost_usd"]),
        yes,
    )
    run(module("iot_poc.journal_agent", "--config", str(MODEL_SENSITIVITY_CONFIG)))
    run(module("iot_poc.journal_model_compare"))


def evidence_gate(config_path: Path, label: str, yes: bool) -> None:
    """Run one action-level evidence gate and its fallback refinement."""
    require_api_key()
    config = load_config(config_path)
    approve_paid_stage(
        label,
        int(config["combined_max_calls"]),
        float(config["combined_max_cost_usd"]),
        yes,
    )
    run(module("iot_poc.journal_evidence_gate", "--config", str(config_path)))
    run(module("iot_poc.journal_evidence_gate_refinement", "--config", str(config_path)))


def model_audit_reports() -> None:
    run([sys.executable, str(ROOT / "scripts" / "analyze_model_audits.py")])


def journal_reports() -> None:
    """Rebuild no-cost summaries from preserved reference records."""
    run(module("iot_poc.journal_policy_baseline", "--config", str(JOURNAL_CONFIG)))
    run(module("iot_poc.journal_statistics", "--config", str(JOURNAL_CONFIG)))
    run(module("iot_poc.journal_model_compare"))
    model_audit_reports()


def agent(run_id: str, cases_path: str, case_limit: int, yes: bool) -> None:
    require_api_key()
    config = load_config()["agent"]
    approve_paid_stage(
        "Paired RAG/no-RAG generation",
        int(config["max_calls"]),
        float(config["max_cost_usd"]),
        yes,
    )
    args = [
        "--config",
        str(CONFIG),
        "--run-id",
        run_id,
        "--cases-path",
        cases_path,
    ]
    if case_limit:
        args.extend(["--case-limit", str(case_limit)])
    run(module("iot_poc.experiment", *args))


def audits(audit_run_id: str, yes: bool) -> None:
    run(module("iot_poc.audit"))
    require_api_key()
    config = load_config()["independent_relevance_audit"]
    approve_paid_stage(
        "Blinded second model-based relevance audit",
        int(config["max_calls"]),
        float(config["max_cost_usd"]),
        yes,
    )
    run(
        module(
            "iot_poc.audit_second",
            "--config",
            str(CONFIG),
            "--run-id",
            audit_run_id,
        )
    )


def strengthening(yes: bool) -> None:
    require_api_key()
    config = load_config()["strengthening_api"]
    approve_paid_stage(
        "Wrong-family retrieval and action-evidence controls",
        int(config["combined_max_calls"]),
        float(config["combined_max_cost_usd"]),
        yes,
    )
    run(module("iot_poc.shuffled_control", "--config", str(CONFIG)))
    run(module("iot_poc.faithfulness_audit", "--config", str(CONFIG)))
    run(module("iot_poc.action_evidence_binding", "--config", str(CONFIG)))


def reports() -> None:
    run(module("iot_poc.analysis"))


def verify() -> None:
    run([sys.executable, str(ROOT / "scripts" / "verify_release.py")])


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run the CICIoT2023 detector, Agentic RAG, guardrail, and reporting "
            "stages in a documented order."
        )
    )
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Verify and prepare the dataset and standards.")
    sub.add_parser("smoke", help="Run fast tests without a dataset or API key.")
    sub.add_parser("offline", help="Run all dataset and detector stages without API calls.")
    sub.add_parser(
        "journal-offline",
        help="Run calibration, case selection, detector sensitivity, and routing without API calls.",
    )

    agent_parser = sub.add_parser("agent", help="Run the paired RAG/no-RAG experiment.")
    agent_parser.add_argument(
        "--run-id", default="local_reproduction/paired_rag_no_rag"
    )
    agent_parser.add_argument(
        "--cases-path",
        default="data/processed/agent_cases_attack_type_aware.jsonl",
    )
    agent_parser.add_argument("--case-limit", type=int, default=0)
    agent_parser.add_argument("--yes", action="store_true", help="Accept the displayed API ceilings.")

    audit_parser = sub.add_parser("audits", help="Apply the first audit and run the second auditor.")
    audit_parser.add_argument(
        "--audit-run-id", default="local_reproduction/independent_relevance_audit"
    )
    audit_parser.add_argument("--yes", action="store_true", help="Accept the displayed API ceilings.")

    strengthening_parser = sub.add_parser(
        "strengthening", help="Run wrong-family and action-evidence controls."
    )
    strengthening_parser.add_argument(
        "--yes", action="store_true", help="Accept the displayed API ceilings."
    )
    journal_agent_parser = sub.add_parser(
        "journal-agent", help="Run the 160-alert, three-condition planning experiment."
    )
    journal_agent_parser.add_argument(
        "--yes", action="store_true", help="Accept the displayed API ceilings."
    )
    sensitivity_parser = sub.add_parser(
        "model-sensitivity", help="Repeat the fixed subset with the stronger model."
    )
    sensitivity_parser.add_argument(
        "--yes", action="store_true", help="Accept the displayed API ceilings."
    )
    relevant_gate_parser = sub.add_parser(
        "evidence-gate", help="Apply action-level retrieval and filtering to relevant-RAG plans."
    )
    relevant_gate_parser.add_argument(
        "--yes", action="store_true", help="Accept the displayed API ceilings."
    )
    mismatched_gate_parser = sub.add_parser(
        "mismatched-evidence-gate",
        help="Apply the same recovery gate after deliberately wrong-family retrieval.",
    )
    mismatched_gate_parser.add_argument(
        "--yes", action="store_true", help="Accept the displayed API ceilings."
    )
    sub.add_parser("model-audit", help="Rebuild the two model-review summaries.")
    sub.add_parser("journal-reports", help="Rebuild journal summaries from saved records.")
    sub.add_parser("reports", help="Regenerate result tables from saved records.")
    sub.add_parser("verify", help="Check canonical counts, hashes, tests, and release files.")
    return value


def main() -> None:
    args = parser().parse_args()
    os.environ.setdefault("PYTHONPATH", str(ROOT / "src"))
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "smoke":
        smoke()
    elif args.command == "offline":
        offline()
    elif args.command == "journal-offline":
        journal_offline()
    elif args.command == "agent":
        agent(args.run_id, args.cases_path, args.case_limit, args.yes)
    elif args.command == "audits":
        audits(args.audit_run_id, args.yes)
    elif args.command == "strengthening":
        strengthening(args.yes)
    elif args.command == "journal-agent":
        journal_agent(args.yes)
    elif args.command == "model-sensitivity":
        model_sensitivity(args.yes)
    elif args.command == "evidence-gate":
        evidence_gate(
            EVIDENCE_GATE_CONFIG,
            "Action-specific evidence gate for relevant-RAG plans",
            args.yes,
        )
    elif args.command == "mismatched-evidence-gate":
        evidence_gate(
            MISMATCHED_GATE_CONFIG,
            "Recovery gate after deliberately wrong-family retrieval",
            args.yes,
        )
    elif args.command == "model-audit":
        model_audit_reports()
    elif args.command == "journal-reports":
        journal_reports()
    elif args.command == "reports":
        reports()
    elif args.command == "verify":
        verify()


if __name__ == "__main__":
    main()
