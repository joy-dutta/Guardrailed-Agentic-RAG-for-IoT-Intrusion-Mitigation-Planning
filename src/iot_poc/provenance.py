from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .common import load_json, sha256_file, write_json


STANDARD_URLS = {
    "NIST.IR.8259A.pdf": "https://nvlpubs.nist.gov/nistpubs/ir/2020/NIST.IR.8259A.pdf",
    "NIST.SP.800-213.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-213.pdf",
    "NIST.SP.800-213A.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-213A.pdf",
    "NIST.SP.800-61r3.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
    "RFC8520.txt": "https://www.rfc-editor.org/rfc/rfc8520.txt",
    "RFC8576.txt": "https://www.rfc-editor.org/rfc/rfc8576.txt",
    "ETSI.EN.303.645.V3.1.3.pdf": "https://www.etsi.org/deliver/etsi_en/303600_303699/303645/03.01.03_60/en_303645v030103p.pdf",
}


def build_manifest(config_path: str = "configs/experiment.json") -> dict:
    config = load_json(config_path)
    standards = []
    for path in sorted(Path("docs/standards").glob("*")):
        if path.is_file() and path.name in STANDARD_URLS:
            standards.append(
                {
                    "file": path.name,
                    "source_url": STANDARD_URLS.get(path.name),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    archive = Path("data/raw/CICIoT2023_CSV.zip")
    implementation_files = sorted(
        path
        for root in [Path("src"), Path("configs"), Path("scripts")]
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "name": "CICIoT2023",
            "official_page": "https://www.unb.ca/cic/datasets/iotdataset-2023.html",
            "archive": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": sha256_file(archive),
        },
        "standards": standards,
        "implementation": [
            {
                "file": str(path).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in implementation_files
        ],
        "experiment_config": config,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    write_json("provenance/manifest.json", manifest)
    return manifest


def freeze_requirements() -> None:
    completed = subprocess.run(
        [str(Path(".venv/Scripts/python.exe")), "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    )
    Path("requirements.lock.txt").write_text(completed.stdout, encoding="utf-8")


if __name__ == "__main__":
    freeze_requirements()
    build_manifest()
    print("Wrote provenance/manifest.json and requirements.lock.txt")
