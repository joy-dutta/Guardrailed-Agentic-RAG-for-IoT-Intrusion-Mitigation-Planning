"""Verify the public release and its preserved reference artifacts."""

from __future__ import annotations

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
        "experiments/runs/paper_final_v2/results.jsonl": 64,
        "experiments/runs/second_relevance_audit_v2/results.jsonl": 8,
        "experiments/runs/shuffled_rag_control/results.jsonl": 52,
        "experiments/runs/action_evidence_faithfulness/results.jsonl": 8,
        "experiments/runs/action_evidence_binding_audit/results.jsonl": 8,
    }
    for relative, line_count in expected.items():
        rows = json_lines(require(relative))
        if len(rows) != line_count:
            raise AssertionError(f"{relative}: expected {line_count} saved rows, found {len(rows)}")

    main_rows = [
        row
        for row in json_lines(require("experiments/runs/paper_final_v2/results.jsonl"))
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
    expanded_path = require("experiments/runs/ieee_access_expanded/results.jsonl")
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
            require("experiments/runs/ieee_access_gpt54_sensitivity/results.jsonl")
        )
        if "error" not in row
    ]
    if len(sensitivity) != 96:
        raise AssertionError(f"Expected 96 successful sensitivity records, found {len(sensitivity)}")

    expected_gates = {
        "ieee_access_evidence_gate": {
            "original_actions": 375,
            "final_actions": 212,
            "unsupported_before": 116,
            "unsupported_after": 19,
            "disruptive_after": 3,
        },
        "ieee_access_mismatched_evidence_gate": {
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
        if Path(relative).name == ".env" or relative.lower().endswith((".tex", ".pptx"))
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


def main() -> None:
    for relative in [
        "README.md",
        "configs/experiment.json",
        "data/processed/agent_cases_attack_type_aware.jsonl",
        "data/processed/ieee_access_agent_cases.jsonl",
        "docs/technical/REPRODUCIBILITY_GUIDE.md",
        "reports/tables/final_analysis.json",
        "reports/journal_extension/tables/expanded_agent_summary.json",
        "reports/journal_extension/tables/evidence_gate_refined_fallback.json",
        "reports/journal_extension/tables/mismatched_evidence_gate_refined_fallback.json",
        "scripts/reproduce.py",
        "src/iot_poc/guardrails.py",
        "src/iot_poc/journal_evidence_gate.py",
    ]:
        require(relative)
    verify_canonical_runs()
    verify_journal_runs()
    verify_standards()
    verify_no_secrets()
    verify_markdown_links()
    print(
        "Release verification passed: files, canonical runs, IEEE Access runs, "
        "standards hashes, local links, publication exclusions, and secret scan."
    )


if __name__ == "__main__":
    main()
