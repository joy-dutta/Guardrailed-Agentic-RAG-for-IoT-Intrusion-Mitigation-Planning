"""Hash every tracked release file except the manifest itself."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "provenance" / "release_manifest.json"
BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".joblib", ".zip"}


def canonical_release_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in BINARY_SUFFIXES:
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main() -> None:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    files = []
    for relative in sorted(completed.stdout.splitlines()):
        if relative == "provenance/release_manifest.json":
            continue
        path = ROOT / relative
        if path.is_file():
            content = canonical_release_bytes(path)
            files.append(
                {
                    "path": relative.replace("\\", "/"),
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repository": "joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning",
        "artifact_version": "1.1.0",
        "hash_policy": "Text files use LF-normalized bytes; listed binary formats use raw bytes.",
        "reference_run_paths": [
            "reference_evaluation/paired_rag_no_rag_32_alerts",
            "reference_evaluation/independent_relevance_audit",
            "reference_evaluation/wrong_family_retrieval_control_32_alerts",
            "reference_evaluation/action_evidence_faithfulness_audit",
            "reference_evaluation/action_evidence_binding_audit",
            "reference_evaluation/three_condition_planning_160_alerts",
            "reference_evaluation/gpt54_model_sensitivity_32_alerts",
            "evidence_gates/relevant_rag_160_alerts",
            "evidence_gates/wrong_family_recovery_160_alerts",
        ],
        "files": files,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(files)} file hashes.")


if __name__ == "__main__":
    main()
