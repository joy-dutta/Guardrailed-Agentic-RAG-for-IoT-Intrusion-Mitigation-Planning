# Running the Experiment

`reproduce.py` is the primary cross-platform entry point. Run it from the
repository root with the same Python interpreter used to install the package.

| Order | Command | Paid API calls? | Main outputs |
|---:|---|---:|---|
| 1 | `python scripts/reproduce.py smoke` | No | unit-test report |
| 2 | `python scripts/reproduce.py bootstrap` | No | extracted CSVs and verified standards |
| 3 | `python scripts/reproduce.py offline` | No | detector models, predictions, tables, fixed cases |
| 4 | `python scripts/reproduce.py journal-offline` | No | calibration, detector sensitivity, routing, and 160 cases |
| 5 | `python scripts/reproduce.py journal-agent` | Yes | 480 planning outputs and policy baseline |
| 6 | `python scripts/reproduce.py model-sensitivity` | Yes | 96 GPT-5.4 outputs and paired comparison |
| 7 | `python scripts/reproduce.py evidence-gate` | Yes | relevant-RAG action filtering and refinement |
| 8 | `python scripts/reproduce.py mismatched-evidence-gate` | Yes | wrong-family recovery results |
| 9 | `python scripts/reproduce.py model-audit` | No | GPT-5.6 Sol Ultra and Gemini Pro Extended audit summaries |
| 10 | `python scripts/reproduce.py journal-reports` | No | journal tables rebuilt from saved records |
| 11 | `python scripts/reproduce.py verify` | No | tests, hashes, result invariants, and secret scan |

`bootstrap_inputs.py` verifies the CICIoT2023 archive, performs path-safe
extraction, and downloads any missing standards from their recorded official
URLs. The reporting command reads the saved JSONL records and rebuilds the
summary tables without making API calls.

Build the technical handbook after installing the documentation dependency:

```bash
python -m pip install -e ".[docs]"
python scripts/build_technical_guide.py
```

`analyze_model_audits.py` rebuilds the completed Reviewer B records, condition summaries, statistical comparisons, and agreement statistics from the preserved blind packets and final judgments.

`verify_release.py` checks the canonical pilot and journal record counts, evidence-gate totals, standards hashes, local documentation links, publication-file exclusions, personal paths, and common API-key patterns.

Reference run IDs are preserved. Use a new run ID for a scientifically separate model or prompt comparison. Successful records are appended immediately, so the same run ID resumes rather than repeating completed calls.
