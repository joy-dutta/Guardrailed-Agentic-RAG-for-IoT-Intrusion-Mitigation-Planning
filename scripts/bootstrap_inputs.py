from __future__ import annotations

import hashlib
import shutil
import urllib.request
from pathlib import Path
from zipfile import ZipFile


ARCHIVE = Path("data/raw/CICIoT2023_CSV.zip")
EXPECTED_ARCHIVE_SHA256 = "E211E878D2F39226EA3A854683F91AE6175B628807EE96EEECB7A04A36A28DBD"
CSV_ROOT = Path("data/interim/CSV")
STANDARD_URLS = {
    "NIST.IR.8259A.pdf": "https://nvlpubs.nist.gov/nistpubs/ir/2020/NIST.IR.8259A.pdf",
    "NIST.SP.800-213.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-213.pdf",
    "NIST.SP.800-213A.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-213A.pdf",
    "NIST.SP.800-61r3.pdf": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
    "RFC8520.txt": "https://www.rfc-editor.org/rfc/rfc8520.txt",
    "RFC8576.txt": "https://www.rfc-editor.org/rfc/rfc8576.txt",
    "ETSI.EN.303.645.V3.1.3.pdf": "https://www.etsi.org/deliver/etsi_en/303600_303699/303645/03.01.03_60/en_303645v030103p.pdf",
}
STANDARD_SHA256 = {
    "ETSI.EN.303.645.V3.1.3.pdf": "CE3EFEC89E392064AD0F8C16082D49E219A5F0641E417FEC8CB1DA4F1765855C",
    "NIST.IR.8259A.pdf": "B3B54B00B5AC3F3582A3E3FD17D3F25B18F848A51F113000B6489ADBCCE374B4",
    "NIST.SP.800-213.pdf": "8F90D1FC02A3436444DCA859B2F66E97942F443C07109798AEAEE1315A6C60AE",
    "NIST.SP.800-213A.pdf": "D75F9E71CC178F293837FB9AD514F2B79FACDB242A75B802E279B56E58171FDD",
    "NIST.SP.800-61r3.pdf": "E5593D6BB85DAECEC7E8D9549400C7B3473BCC3F06E469C82218073AFA7FBA2D",
    "RFC8520.txt": "71B163203172FC40168F047FB9A7548A4140D5759EB9F508F575FF0DA0797802",
    "RFC8576.txt": "16F2A71B411641ECF3BF5BC60874101EEF701410DD213BDD65CEC9E2B7EA3D90",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def prepare_dataset() -> None:
    if not ARCHIVE.exists():
        raise FileNotFoundError(
            "Download the registered CICIoT2023 CSV.zip and place it at "
            f"{ARCHIVE}."
        )
    actual_hash = sha256(ARCHIVE)
    if actual_hash != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(f"Unexpected dataset archive SHA-256: {actual_hash}")
    if CSV_ROOT.exists() and any(CSV_ROOT.glob("*/*.csv")):
        print("Dataset CSV folders already exist; extraction skipped.")
        return
    CSV_ROOT.parent.mkdir(parents=True, exist_ok=True)
    destination = CSV_ROOT.parent.resolve()
    with ZipFile(ARCHIVE) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Unsafe path in dataset archive: {member.filename}")
        archive.extractall(CSV_ROOT.parent)
    if not any(CSV_ROOT.glob("*/*.csv")):
        raise RuntimeError("Extraction completed but no expected CSV files were found.")
    print("Dataset archive verified and extracted.")


def prepare_standards() -> None:
    destination = Path("docs/standards")
    destination.mkdir(parents=True, exist_ok=True)
    for filename, url in STANDARD_URLS.items():
        target = destination / filename
        if target.exists() and target.stat().st_size > 1000:
            actual_hash = sha256(target)
            if actual_hash != STANDARD_SHA256[filename]:
                raise ValueError(f"Unexpected SHA-256 for existing {filename}: {actual_hash}")
            print(f"Standards file verified: {filename}")
            continue
        temporary = target.with_suffix(target.suffix + ".download")
        request = urllib.request.Request(url, headers={"User-Agent": "iot-rag-reproduction/1.0"})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual_hash = sha256(temporary)
        if actual_hash != STANDARD_SHA256[filename]:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"Unexpected SHA-256 for downloaded {filename}: {actual_hash}")
        temporary.replace(target)
        print(f"Downloaded {filename}")


if __name__ == "__main__":
    prepare_dataset()
    prepare_standards()
