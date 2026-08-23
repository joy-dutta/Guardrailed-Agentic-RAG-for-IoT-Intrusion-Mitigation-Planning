"""Hash every tracked release file except the manifest itself."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "provenance" / "release_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    completed = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    files = []
    for relative in sorted(completed.stdout.splitlines()):
        if relative == "provenance/release_manifest.json":
            continue
        path = ROOT / relative
        if path.is_file():
            files.append(
                {
                    "path": relative.replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repository": "joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning",
        "artifact_version": "1.0.0",
        "canonical_run_ids": [
            "paper_final_v2",
            "second_relevance_audit_v2",
            "shuffled_rag_control",
            "action_evidence_faithfulness",
            "action_evidence_binding_audit",
        ],
        "files": files,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(files)} file hashes.")


if __name__ == "__main__":
    main()
