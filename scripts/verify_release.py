"""Verify the public release and its preserved reference artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY_PATTERN = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")
ABSOLUTE_USER_PATH = re.compile(
    r"(?:[A-Za-z]:\\" + "Users" + r"\\|/" + "Users" + r"/|/" + "home" + r"/)"
)


def json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(relative: str) -> Path:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f"Required release file is missing: {relative}")
    return path


def verify_canonical_runs() -> None:
    expected = {
        "experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/results.jsonl": 64,
        "experiments/runs/reference_evaluation/independent_relevance_audit/results.jsonl": 8,
        "experiments/runs/reference_evaluation/wrong_family_retrieval_control_32_alerts/results.jsonl": 52,
        "experiments/runs/reference_evaluation/action_evidence_faithfulness_audit/results.jsonl": 8,
        "experiments/runs/reference_evaluation/action_evidence_binding_audit/results.jsonl": 8,
    }
    for relative, line_count in expected.items():
        rows = json_lines(require(relative))
        if len(rows) != line_count:
            raise AssertionError(f"{relative}: expected {line_count} saved rows, found {len(rows)}")

    main_rows = [
        row
        for row in json_lines(
            require(
                "experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/results.jsonl"
            )
        )
        if "error" not in row
    ]
    if len(main_rows) != 64:
        raise AssertionError("The reference run does not contain 64 successful records.")
    conditions = {condition: 0 for condition in ("rag", "no_rag")}
    for row in main_rows:
        conditions[row["condition"]] += 1
    if conditions != {"rag": 32, "no_rag": 32}:
        raise AssertionError(f"Unexpected paired condition counts: {conditions}")


def verify_journal_runs() -> None:
    expanded_path = require(
        "experiments/runs/reference_evaluation/three_condition_planning_160_alerts/results.jsonl"
    )
    expanded = json_lines(expanded_path)
    successful = [row for row in expanded if "error" not in row]
    if len(successful) != 480:
        raise AssertionError(f"Expected 480 successful expanded records, found {len(successful)}")
    conditions = {condition: 0 for condition in ("rag", "no_rag", "mismatched_rag")}
    for row in successful:
        conditions[row["condition"]] += 1
    if conditions != {"rag": 160, "no_rag": 160, "mismatched_rag": 160}:
        raise AssertionError(f"Unexpected expanded condition counts: {conditions}")

    sensitivity = [
        row
        for row in json_lines(
            require(
                "experiments/runs/reference_evaluation/gpt54_model_sensitivity_32_alerts/results.jsonl"
            )
        )
        if "error" not in row
    ]
    if len(sensitivity) != 96:
        raise AssertionError(f"Expected 96 successful sensitivity records, found {len(sensitivity)}")

    expected_gates = {
        "evidence_gates/relevant_rag_160_alerts": {
            "original_actions": 375,
            "final_actions": 212,
            "unsupported_before": 116,
            "unsupported_after": 19,
            "disruptive_after": 3,
        },
        "evidence_gates/wrong_family_recovery_160_alerts": {
            "original_actions": 376,
            "final_actions": 213,
            "unsupported_before": 117,
            "unsupported_after": 14,
            "disruptive_after": 0,
        },
    }
    for run_id, expected in expected_gates.items():
        summary = json.loads(
            require(f"experiments/runs/{run_id}/refinement_summary.json").read_text(
                encoding="utf-8"
            )
        )
        gate = summary["refined_strict_gate"]
        evaluation = gate["independent_evaluator"]
        observed = {
            "original_actions": gate["original_actions"],
            "final_actions": gate["final_actions"],
            "unsupported_before": evaluation["before_label_counts"]["unsupported"],
            "unsupported_after": evaluation["after_label_counts"]["unsupported"],
            "disruptive_after": evaluation["after_disruptive_actions"],
        }
        if observed != expected:
            raise AssertionError(f"Unexpected evidence-gate totals for {run_id}: {observed}")
        if gate["schema_validity"] != 1.0 or gate["policy_conformance"] != 1.0:
            raise AssertionError(f"Final gate outputs failed declared checks for {run_id}")


def verify_standards() -> None:
    manifest = json.loads(require("docs/standards/manifest.json").read_text(encoding="utf-8"))
    for item in manifest["documents"]:
        if not item["distributed_in_repository"]:
            continue
        path = require(f"docs/standards/{item['file']}")
        observed = sha256(path)
        if observed.lower() != item["sha256"].lower():
            raise AssertionError(f"Standards hash mismatch: {item['file']}")


def verify_dataset_mapping() -> None:
    mapping_path = require("reports/tables/attack_family_mapping.csv")
    with mapping_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    families = {row["family"] for row in rows}
    expected_families = {
        "Benign",
        "BruteForce",
        "DDoS",
        "DoS",
        "Mirai",
        "Recon",
        "Spoofing",
        "Web",
    }
    if len(rows) != 34 or families != expected_families:
        raise AssertionError(
            f"Unexpected attack-family mapping: labels={len(rows)}, families={sorted(families)}"
        )


def verify_model_reviews() -> None:
    expected = {
        "reports/comprehensive_evaluation/model_audit/"
        "chatgpt_A_plan_completed.csv": 192,
        "reports/comprehensive_evaluation/model_audit/"
        "chatgpt_A_evidence_completed.csv": 128,
        "reports/comprehensive_evaluation/model_audit/"
        "gemini_B_plan_completed.csv": 192,
        "reports/comprehensive_evaluation/model_audit/"
        "gemini_B_evidence_completed.csv": 128,
        "reports/comprehensive_evaluation/model_audit/"
        "gemini_B_plan_judgments.csv": 192,
        "reports/comprehensive_evaluation/model_audit/"
        "gemini_B_evidence_judgments.csv": 128,
    }
    for relative, expected_rows in expected.items():
        with require(relative).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        identifiers = [row.get("audit_id", "").strip() for row in rows]
        if len(rows) != expected_rows or any(not value for value in identifiers):
            raise AssertionError(
                f"Incomplete model-review artifact: {relative} ({len(rows)} rows)"
            )
        if len(set(identifiers)) != expected_rows:
            raise AssertionError(f"Duplicate model-review audit IDs: {relative}")


def verify_no_secrets() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = completed.stdout.splitlines()
    forbidden_names = [
        relative
        for relative in tracked
        if Path(relative).name == ".env"
        or relative.lower().endswith((".tex", ".pptx"))
        or relative.replace("\\", "/").startswith(
            ("paper/", "presentations/", "reports/figures/")
        )
    ]
    if forbidden_names:
        raise AssertionError(f"Private or publication files are tracked: {forbidden_names}")
    for relative in tracked:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if KEY_PATTERN.search(content):
            raise AssertionError(f"Possible API key in tracked file: {relative}")
        if ABSOLUTE_USER_PATH.search(content):
            raise AssertionError(f"Personal absolute path in tracked file: {relative}")


def verify_markdown_links() -> None:
    pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = urllib.parse.unquote(target.split("#", 1)[0])
            if relative and not (path.parent / relative).exists():
                raise AssertionError(
                    f"Broken local Markdown link in {path.relative_to(ROOT)}: {target}"
                )


def verify_public_layout() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [
        Path(relative)
        for relative in completed.stdout.splitlines()
        if (ROOT / relative).is_file()
    ]
    forbidden_path_terms = {
        "development_history",
        "paper_main",
        "paper_final",
        "paper_final_v2",
        "second_relevance_audit",
        "second_relevance_audit_v2",
        "ieee_access_expanded",
        "ieee_access_gpt54_sensitivity",
        "ieee_access_evidence_gate",
        "ieee_access_mismatched_evidence_gate",
    }
    unprofessional = [
        path.as_posix()
        for path in tracked
        if forbidden_path_terms.intersection(path.parts)
    ]
    if unprofessional:
        raise AssertionError(f"Superseded public paths were reintroduced: {unprofessional}")

    visible_run_entries = {
        path.parts[2]
        for path in tracked
        if len(path.parts) >= 3 and path.parts[:2] == ("experiments", "runs")
    }
    expected_run_entries = {
        "README.md",
        "run_catalog.csv",
        "reference_evaluation",
        "evidence_gates",
    }
    if visible_run_entries != expected_run_entries:
        raise AssertionError(
            "The public run index must contain only the two documented groups: "
            f"{sorted(visible_run_entries)}"
        )

    documented_directories: set[Path] = set()
    for path in tracked:
        parent = path.parent
        while parent != Path("."):
            documented_directories.add(parent)
            parent = parent.parent
    exclusions = {Path(".github"), Path(".github/workflows")}
    missing_readmes = []
    for directory in sorted(documented_directories - exclusions):
        absolute = ROOT / directory
        if not (absolute / "README.md").exists() and not (absolute / "ABOUT.md").exists():
            missing_readmes.append(directory.as_posix())
    if missing_readmes:
        raise AssertionError(f"Artifact folders without a README: {missing_readmes}")


def verify_release_manifest() -> None:
    manifest_path = require("provenance/release_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = {item["path"]: item for item in manifest["files"]}
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    current = {
        relative.replace("\\", "/")
        for relative in completed.stdout.splitlines()
        if relative.replace("\\", "/") != "provenance/release_manifest.json"
        and (ROOT / relative).is_file()
    }
    if set(recorded) != current:
        missing = sorted(current - set(recorded))
        stale = sorted(set(recorded) - current)
        raise AssertionError(
            f"Release manifest file set is stale; missing={missing}, stale={stale}"
        )
    for relative, item in recorded.items():
        path = ROOT / relative
        if path.stat().st_size != int(item["bytes"]) or sha256(path) != item["sha256"]:
            raise AssertionError(f"Release manifest mismatch: {relative}")


def main() -> None:
    for relative in [
        "README.md",
        "configs/experiment.json",
        "data/processed/agent_cases_attack_type_aware.jsonl",
        "data/processed/planning_cases_160.jsonl",
        "docs/technical/REPRODUCIBILITY_GUIDE.md",
        "reports/tables/reference_analysis.json",
        "reports/comprehensive_evaluation/tables/expanded_agent_summary.json",
        "reports/comprehensive_evaluation/tables/evidence_gate_refined_fallback.json",
        "reports/comprehensive_evaluation/tables/mismatched_evidence_gate_refined_fallback.json",
        "scripts/reproduce.py",
        "src/iot_poc/guardrails.py",
        "src/iot_poc/journal_evidence_gate.py",
    ]:
        require(relative)
    verify_canonical_runs()
    verify_journal_runs()
    verify_standards()
    verify_dataset_mapping()
    verify_model_reviews()
    verify_no_secrets()
    verify_markdown_links()
    verify_public_layout()
    verify_release_manifest()
    print(
        "Release verification passed: files, reference runs, expanded runs, "
        "standards hashes, documented layout, local links, publication exclusions, "
        "secret scan, and release-manifest integrity."
    )


if __name__ == "__main__":
    main()
