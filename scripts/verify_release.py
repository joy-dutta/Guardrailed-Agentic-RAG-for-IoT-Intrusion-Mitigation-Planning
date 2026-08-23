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
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    for relative in completed.stdout.splitlines():
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if KEY_PATTERN.search(content):
            raise AssertionError(f"Possible API key in tracked file: {relative}")


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
        "docs/technical/REPRODUCIBILITY_GUIDE.md",
        "reports/tables/final_analysis.json",
        "scripts/reproduce.py",
        "src/iot_poc/guardrails.py",
    ]:
        require(relative)
    verify_canonical_runs()
    verify_standards()
    verify_no_secrets()
    verify_markdown_links()
    print(
        "Release verification passed: files, canonical runs, standards hashes, "
        "local links, and secret scan."
    )


if __name__ == "__main__":
    main()
