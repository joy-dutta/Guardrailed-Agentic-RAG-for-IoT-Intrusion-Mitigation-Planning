# Confidence-Aware Guardrailed Agentic RAG for IoT Intrusion Mitigation Planning

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![Tests](https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning/actions/workflows/ci.yml/badge.svg)](https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/code%20license-MIT-green.svg)](LICENSE)

This repository shows how an IoT intrusion alert can be converted into a
standards-grounded and bounded mitigation plan. A calibrated detector estimates
the likely attack family, an agent retrieves relevant security guidance, and
deterministic guardrails check the proposed response before any gateway or
cloud action is considered.

The implementation is an offline research prototype. It produces mitigation
intent with status `PROPOSED_NOT_EXECUTED`; it does not send commands to a
device, firewall, gateway, or cloud service.

## What This Repository Lets You Check

- Rebuild the detector and confidence-routing experiments from CICIoT2023.
- Compare the same 32 alerts with official-document RAG and without RAG.
- Inspect every saved agent response used to produce the reported tables.
- Repeat the relevance, wrong-family retrieval, action-evidence, and guardrail
  experiments.
- Rebuild the result tables directly from machine-readable experiment records.
- Trace each reported result to a configuration, run ID, and source table.

The central finding is deliberately modest: relevant retrieval makes proposals
more traceable, while deterministic guardrails enforce the output contract and
bounded action policy. Neither component proves that a proposed action will
stop a live attack.

## Choose Your Reproduction Path

| Goal | Dataset needed | API key needed | Command |
|---|---:|---:|---|
| Inspect the saved reference results | No | No | `python scripts/reproduce.py reports` |
| Check installation and safety logic | No | No | `python scripts/reproduce.py smoke` |
| Rebuild detector experiments | Yes | No | `python scripts/reproduce.py offline` |
| Repeat paired RAG/no-RAG generation | Prepared cases | Yes | `python scripts/reproduce.py agent --run-id my_main_run` |
| Repeat the complete experiment | Yes | Yes | See [Full API reproduction](#full-api-reproduction) |

The saved canonical outputs reconstruct the exact tables reported by this
project. A fresh LLM run follows the same method but may not reproduce identical
wording because hosted model generation is not byte-deterministic.

## Quick Start

Python 3.12 is the tested environment and the minimum supported version. The
commands below work in PowerShell, Command Prompt, macOS, and Linux when the
virtual environment path is adjusted for the platform.

```bash
git clone https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning.git
cd Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning
python -m venv .venv
```

PowerShell installation:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\reproduce.py smoke
```

macOS or Linux installation:

```bash
./.venv/bin/python -m pip install --upgrade pip setuptools
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/python scripts/reproduce.py smoke
```

`requirements.lock.txt` records the exact successful environment. Editable
installation from `pyproject.toml` makes the `src/iot_poc` package available to
every command.

## Prepare the Official Inputs

The experiment uses the official CICIoT2023 CSV release. The source archive
contains 309 CSV files, 46,776,700 rows, and 39 numerical traffic features.
Folder names provide the attack labels; individual rows do not contain a
verified device identifier.

1. Obtain `CSV.zip` from the [official CICIoT2023 page](https://www.unb.ca/cic/datasets/iotdataset-2023.html).
2. Save it as `data/raw/CICIoT2023_CSV.zip`.
3. Run `python scripts/reproduce.py bootstrap`.

The bootstrap script verifies this exact archive before extraction:

```text
Bytes:   1,430,268,604
SHA-256: E211E878D2F39226EA3A854683F91AE6175B628807EE96EEECB7A04A36A28DBD
```

It also verifies the six standards files distributed with this repository and
downloads ETSI EN 303 645 V3.1.3 from ETSI's official server. See
[`docs/standards/README.md`](docs/standards/README.md) for the seven-document
corpus, versions, roles, source URLs, hashes, and redistribution notes.

## Run the Offline Experiment

```bash
python scripts/reproduce.py offline
```

This performs the stages in their scientific order:

1. prepare and deduplicate the fixed family-balanced sample;
2. build random-row, attack-type-aware, and strict whole-file splits;
3. train and calibrate the Random Forest detector;
4. evaluate calibration, confidence routing, alternatives, and five fixed seeds;
5. select 32 fixed agent alerts without exposing ground-truth labels to the LLM;
6. evaluate detector-error propagation and 576 guardrail mutations;
7. run tests and record provenance.

The primary split contains 221,795 training, 78,133 calibration, and 78,599
test rows. `Number` and `Tot sum` are removed from the primary detector because
they encode aggregation-window behavior that can become an optimistic
collection shortcut. The mapping and split logic are explained in
[`docs/dataset/DATA_CARD.md`](docs/dataset/DATA_CARD.md).

## Configure OpenAI Access

Set the key only in your local process environment:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

```bash
export OPENAI_API_KEY="your-api-key"
```

The reference configuration uses `gpt-5.4-mini-2026-03-17`. API limits are checked
before a paid stage begins, and successful responses are saved immediately so
an interrupted run can resume. The configured dollar figures are local
estimates based on the prices recorded at experiment time, not an account-level
billing guarantee. Review `configs/experiment.json` and your provider billing
controls before running.

## Paired RAG/No-RAG Experiment

```bash
python scripts/reproduce.py agent --run-id my_main_run
```

The command sends the same 32 detector alerts once with the top three official
standards chunks and once with an empty retrieval context. The stage is capped
at 96 attempts and an estimated USD 2.00. The saved reference run used 64
successful calls and an estimated USD 0.1675.

Use a new run ID for a fresh reproduction. Reusing a run ID resumes completed
case-condition pairs instead of paying for them again.

## Full API Reproduction

The complete reference sequence is:

```bash
python scripts/reproduce.py agent --run-id paper_final_v2
python scripts/reproduce.py audits --audit-run-id second_relevance_audit_v2
python scripts/reproduce.py strengthening
python scripts/reproduce.py reports
python scripts/reproduce.py verify
```

The successful records for these reference run IDs are included. Repeating
the commands reconstructs their summaries without paying for completed calls.
For a scientifically separate run, use a new main run ID and preserve it as a
new experiment rather than overwriting the reference evidence.

The strengthening controls are capped separately at 50 calls and an estimated
USD 0.35. They test wrong-family retrieval, action-level evidence support,
action-specific evidence binding, and the second blinded model-based relevance
audit. Both relevance auditors are model-based. Label-free packets are included
for a separate human assessment.

## Main Results

| Research question | Saved result | Plain-language meaning |
|---|---:|---|
| Detector under attack-type-aware evaluation | Mean macro-F1 0.731 across five seeds | Useful as an alert source, but not reliable enough for unconditional enforcement |
| Confidence routing | Mean 96.2% accuracy on 54.0% covered rows | Stronger alerts continue to planning; the rest are held for evidence and review |
| Valid standards references | RAG 31/32; no RAG 0/32 | Retrieval adds traceable official context |
| Retrieval relevance | Conservative agreement 46/48 | Most top-three passages were relevant or supporting in the two model-based audits |
| Full executor schema | Raw 0/64; guarded 64/64 | The LLM proposes compact intent; deterministic code closes the executor contract |
| Action-policy conformance | Raw 44/64; guarded 64/64 | Retrieval does not replace deterministic safety checks |
| Action-specific evidence support | 68.8% supported; 31.3% unsupported | Evidence binding helps, but unsupported actions still require review or replacement |
| Guardrail mutation stress | 576/576 final outputs passed declared checks | The implemented rules contained every tested mutation class |
| Intentionally wrong detector labels | Three wrong-category disruptive cases removed | Top-two filtering traded aggressive response for safer monitoring and escalation |

Read [`docs/results/RESULTS_IN_PLAIN_LANGUAGE.md`](docs/results/RESULTS_IN_PLAIN_LANGUAGE.md)
for the physical-world interpretation and
[`docs/results/CLAIMS_AND_LIMITATIONS.md`](docs/results/CLAIMS_AND_LIMITATIONS.md)
for the exact claim boundary.

## Repository Navigation

| Path | Start here when you want to... |
|---|---|
| [`configs/`](configs/README.md) | inspect models, seeds, chunking, and API caps |
| [`data/`](data/README.md) | understand raw, prepared, and fixed-case data |
| [`docs/`](docs/README.md) | read the method without opening source code |
| [`experiments/runs/`](experiments/runs/README.md) | inspect the exact saved API records and run IDs |
| [`reports/tables/`](reports/tables/README.md) | find the machine-readable evidence behind a result |
| [`scripts/`](scripts/README.md) | run the experiment in the correct order |
| [`src/iot_poc/`](src/README.md) | inspect the Python implementation by component |
| [`tests/`](tests/README.md) | see which invariants and mappings are tested |
| [`provenance/`](provenance/README.md) | verify hashes, versions, and release contents |
| [`paper/`](paper/README.md) | read the study context and repository scope |

## Citing This Software

Citation metadata for the code and experimental artifacts is provided in
[`CITATION.cff`](CITATION.cff). GitHub can export this metadata in common
bibliographic formats from the repository's **Cite this repository** menu.
The study context and contributor list are summarized in
[`paper/README.md`](paper/README.md).

## Safety, Licensing, and Responsible Use

The MIT license applies to original source code in this repository. Dataset and
standards materials retain their publishers' terms; see
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). The ETSI PDF is downloaded
from its official source and is not redistributed here.

Generated plans are research outputs, not deployment-ready commands. A real
gateway requires independently defined policy, authentication, authorization,
transactional rollback, live service-impact testing, and operator governance.
See [`SECURITY.md`](SECURITY.md) before adapting the code to an operational
network.

## Technical Documentation

The complete reproducibility handbook is available in two forms:

- [`docs/technical/REPRODUCIBILITY_GUIDE.md`](docs/technical/REPRODUCIBILITY_GUIDE.md)
- [`docs/technical/Technical_Reproducibility_Guide.pdf`](docs/technical/Technical_Reproducibility_Guide.pdf)

The guide covers the experiment from raw traffic rows to final bounded intent,
including every command, configuration, run ID, result, and limitation needed
for an independent handover.
