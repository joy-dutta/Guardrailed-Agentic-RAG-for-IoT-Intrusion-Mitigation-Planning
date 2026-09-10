# Guardrailed Agentic RAG for IoT Intrusion Mitigation Planning

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![Tests](https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning/actions/workflows/ci.yml/badge.svg)](https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/code%20license-MIT-green.svg)](LICENSE)

This repository follows an IoT security alert from detection to a checked mitigation plan. A calibrated detector predicts the likely traffic family. Uncertain predictions are routed to review. The planning agent retrieves official security guidance, proposes a small set of actions, and passes the proposal through deterministic schema, policy, and evidence checks.

The result is a transparent mitigation intent that an operator can inspect. It always remains `PROPOSED_NOT_EXECUTED`. The software does not issue commands to a device, gateway, firewall, or cloud service.

## Why This Work Matters

An intrusion detector can be wrong, and a fluent language model can produce a convincing but weakly supported response. This project treats both outputs as useful inputs that still need checking. The practical goal is simple:

> Turn an uncertain IoT alert into a smaller, traceable, policy-compatible plan before any real network action is considered.

The experiments show three positive outcomes:

1. Confidence routing keeps lower-confidence detector decisions out of the normal planning path.
2. Official-document retrieval gives the planner traceable source identifiers.
3. Deterministic guardrails and an action-level evidence gate remove weak or incompatible actions and fall back to cautious monitoring, traffic capture, or operator notification when needed.

## Pipeline At A Glance

```text
CICIoT2023 traffic row
        |
        v
calibrated attack-family detector
        |
        +--> uncertain alert --> collect evidence and request review
        |
        v
official-document retrieval --> mitigation planner
        |
        v
schema and action-policy guardrails
        |
        v
action-specific retrieval and evidence gate
        |
        v
bounded intent: PROPOSED_NOT_EXECUTED
```

## What Was Evaluated

The repository preserves the reference evaluation and the larger journal study.

| Experiment | Purpose |
|---|---|
| CICIoT2023 preprocessing and split controls | Build a traceable detector input without treating repeated traffic rows as independent evidence |
| Five-seed calibration comparison | Compare raw, sigmoid, and isotonic confidence values without using the final test labels for selection |
| Detector sensitivity | Check whether confidence-routing behavior depends on one classifier |
| Global and family-aware routing | Compare one confidence threshold with separate thresholds for each predicted traffic family |
| 160-alert planning study | Compare relevant RAG, no RAG, and deliberately wrong-family RAG on the same alerts |
| Policy-only baseline | Show what a fixed response table produces without an LLM |
| Stronger-model sensitivity | Repeat a fixed 32-alert subset with GPT-5.4 |
| Guardrail ablation and 576 mutations | Compare raw and normalized outputs and systematically challenge declared safeguards |
| Relevant-RAG evidence gate | Recheck every proposed action using action-specific retrieval |
| Wrong-family recovery gate | Test whether the same gate contains the effect of deliberately mismatched initial retrieval |
| Two independent model reviews | Compare blinded judgments from ChatGPT using GPT-5.6 Sol Ultra and Gemini using Gemini Pro Extended |

## Main Findings In Plain Language

| Finding | Result | Practical meaning |
|---|---:|---|
| Five-seed detector performance | Mean macro-F1 about 0.73 | The detector is useful for producing alerts, while difficult cases still benefit from cautious routing |
| Family-aware confidence routing | Wrong retained decisions reduced by about 30% | Separate family thresholds send more uncertain traffic to review and reduce risky automatic handoff |
| Traceable source attachment | Relevant RAG 158/160; no RAG 0/160 | Retrieval gives the planner identifiable official context |
| Initial wrong-family control | Valid identifiers still appeared in 151/160 plans | A real citation identifier shows traceability, not whether the passage supports the action |
| Relevant-RAG evidence gate | Unsupported retained actions fell from 30.9% to 9.0% | The gate kept a smaller and better-supported action set |
| Wrong-family recovery gate | Unsupported retained actions fell from 31.1% to 6.6% | Fresh action-level retrieval and filtering contained much of the initial retrieval error |
| Disruptive actions after wrong-family recovery | 33 before the gate; 0 after | The recovery path failed toward cautious, non-disruptive responses |
| Final schema and policy checks | 100% for the tested normalized outputs | Deterministic code enforced the declared output contract in the evaluated cases |
| Mutation stress test | 576/576 final outputs passed declared checks | The implemented safeguards contained every tested mutation class |

The percentages after the evidence gate are support rates among the actions that remained. They are not attack-classification accuracy and do not claim that an action will stop a live incident. The gate deliberately removes many actions and sometimes inserts a conservative fallback. Its contribution is failure containment and clearer evidence, not making the original wrong evidence correct.

## Independent Model Reviews

Two models reviewed blinded records independently:

- Reviewer A: **ChatGPT using GPT-5.6 Sol Ultra**
- Reviewer B: **Gemini using Gemini Pro Extended**

Each reviewer assessed 192 mitigation plans and 128 action-evidence records. Their completed outputs, condition summaries, agreement statistics, and interpretation are preserved in [`reports/comprehensive_evaluation/model_audit/`](reports/comprehensive_evaluation/model_audit/README.md).

Both reviews were broadly positive about the usefulness and cautious character of the final plans. They also differed in grading strictness, especially when deciding whether a passage directly supported an action or was only generally related. This is useful evidence because it shows where judgments are stable and where expert interpretation still matters. These are model-based reviews and are presented as supplementary triangulation, not as human validation.

Blank packets for a future security-aware human review are kept separately in [`reports/comprehensive_evaluation/human_audit/`](reports/comprehensive_evaluation/human_audit/README.md).

## Choose A Reproduction Path

| Goal | Dataset needed | API key needed | Command |
|---|---:|---:|---|
| Run tests and release checks | No | No | `python scripts/reproduce.py verify` |
| Rebuild summaries from saved records | No | No | `python scripts/reproduce.py journal-reports` |
| Rebuild the original detector study | Yes | No | `python scripts/reproduce.py offline` |
| Rebuild journal calibration and routing | Yes | No | `python scripts/reproduce.py journal-offline` |
| Repeat the 480-output planning run | Prepared cases | Yes | `python scripts/reproduce.py journal-agent` |
| Repeat the stronger-model subset | Prepared cases | Yes | `python scripts/reproduce.py model-sensitivity` |
| Repeat the relevant-RAG evidence gate | Saved primary run | Yes | `python scripts/reproduce.py evidence-gate` |
| Repeat wrong-family recovery | Saved primary run | Yes | `python scripts/reproduce.py mismatched-evidence-gate` |

Saved reference records reproduce the reported tables without paid calls. A fresh hosted-model run follows the same method, but wording can vary because API generation is not guaranteed to be byte-identical over time.

## Quick Start

Python 3.12 is the tested environment. Docker is not required.

```bash
git clone https://github.com/joy-dutta/Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning.git
cd Guardrailed-Agentic-RAG-for-IoT-Intrusion-Mitigation-Planning
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\reproduce.py verify
```

macOS or Linux:

```bash
./.venv/bin/python -m pip install --upgrade pip setuptools
./.venv/bin/python -m pip install -e '.[dev]'
./.venv/bin/python scripts/reproduce.py verify
```

`requirements.lock.txt` records the exact package versions used for the saved experiments.

## Prepare CICIoT2023

The full experiment uses the official CICIoT2023 CSV release: 309 CSV files, 46,776,700 rows, and 39 numerical traffic features. The registered archive is too large for ordinary Git hosting, so it is not committed.

1. Download `CSV.zip` from the [official CICIoT2023 page](https://www.unb.ca/cic/datasets/iotdataset-2023.html).
2. Save it as `data/raw/CICIoT2023_CSV.zip`.
3. Run `python scripts/reproduce.py bootstrap`.

The bootstrap stage checks the archive before extraction:

```text
Bytes:   1,430,268,604
SHA-256: E211E878D2F39226EA3A854683F91AE6175B628807EE96EEECB7A04A36A28DBD
```

The current full working tree occupies about 17.3 GB after extraction and generated artifacts, so allowing at least 20 GB of free space is sensible. Dataset organization, preprocessing, family mapping, and split logic are described in [`docs/dataset/DATA_CARD.md`](docs/dataset/DATA_CARD.md).

## Standards Corpus

The retrieval corpus contains seven official publications from NIST, ETSI, and the IETF. The repository includes redistributable NIST and RFC files with source URLs and hashes. ETSI EN 303 645 is downloaded from ETSI's official server and verified locally because its redistribution terms differ.

See [`docs/standards/README.md`](docs/standards/README.md) for the document versions, experimental roles, chunking settings, source links, and integrity checks.

## API Access And Cost Controls

Set the OpenAI key only in the current process:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

```bash
export OPENAI_API_KEY="your-api-key"
```

Each paid stage has its own configuration, call ceiling, and estimated-cost ceiling. The command displays these limits before starting and asks for confirmation. Successful responses are stored immediately, so an interrupted run can resume without repeating completed work.

| Paid stage | Hard call ceiling | Hard estimated-cost ceiling | Saved-run estimated cost |
|---|---:|---:|---:|
| 160 alerts across three conditions | 500 | USD 4.00 | USD 1.32 |
| GPT-5.4 sensitivity subset | 110 | USD 3.00 | USD 0.83 |
| Relevant-RAG evidence gate and refinement | 20 | USD 2.50 | USD 1.21 |
| Wrong-family recovery gate and refinement | 20 | USD 2.50 | USD 1.26 |

These are code-level estimates using the prices recorded in the configuration. They are not provider-side billing limits. Review the configuration and set an account-level budget before repeating a paid run.

## Recommended Full Sequence

```bash
python scripts/reproduce.py bootstrap
python scripts/reproduce.py offline
python scripts/reproduce.py journal-offline
python scripts/reproduce.py journal-agent
python scripts/reproduce.py model-sensitivity
python scripts/reproduce.py evidence-gate
python scripts/reproduce.py mismatched-evidence-gate
python scripts/reproduce.py model-audit
python scripts/reproduce.py journal-reports
python scripts/reproduce.py verify
```

Run paid stages separately after reading their displayed limits. Do not place API credentials in a command history, configuration file, notebook, or committed `.env` file.

## Repository Guide

| Path | What you will find |
|---|---|
| [`.github/`](.github/ABOUT.md) | Contribution, conduct, security, and automated-check documentation |
| [`configs/`](configs/README.md) | Frozen models, seeds, thresholds, retrieval settings, and API limits |
| [`data/`](data/README.md) | Dataset instructions, generated-data layout, fixed alerts, and a small example |
| [`docs/`](docs/README.md) | Dataset, method, protocol, standards, results, legal, and technical documentation |
| [`experiments/runs/`](experiments/runs/README.md) | Saved API records and run-level provenance |
| [`reports/tables/`](reports/tables/README.md) | Reference result tables and claim boundaries |
| [`reports/comprehensive_evaluation/`](reports/comprehensive_evaluation/README.md) | Expanded evaluation, evidence gates, and independent audits |
| [`scripts/`](scripts/README.md) | Reproduction, verification, and documentation commands |
| [`src/iot_poc/`](src/iot_poc/README.md) | Python implementation organized by pipeline stage |
| [`tests/`](tests/README.md) | No-cost tests for mappings, retrieval, routing, guardrails, statistics, and gates |
| [`provenance/`](provenance/README.md) | Environment details and release file hashes |

## Publication Status

This repository supports an associated manuscript being prepared for journal peer review. Bibliographic details will be added after publication. The manuscript and its publication figures are not part of this repository.

## Responsible Interpretation

The project demonstrates mitigation planning, uncertainty routing, evidence traceability, deterministic conformance, and retrieval-failure containment. It does not claim live attack suppression or automatic authorization to change a network.

This boundary is a strength of the design. A real deployment can place the checked intent behind local authentication, authorization, service-impact controls, rollback, and operator approval without changing the experimental meaning of this repository.

The exact supported claims and open validation steps are listed in [`docs/results/CLAIMS_AND_LIMITATIONS.md`](docs/results/CLAIMS_AND_LIMITATIONS.md). Software citation metadata is available in [`CITATION.cff`](CITATION.cff).
