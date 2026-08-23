# Running the Experiment

`reproduce.py` is the primary cross-platform entry point. Run it from the
repository root with the same Python interpreter used to install the package.

| Order | Command | Paid API calls? | Main outputs |
|---:|---|---:|---|
| 1 | `python scripts/reproduce.py smoke` | No | unit-test report |
| 2 | `python scripts/reproduce.py bootstrap` | No | extracted CSVs and verified standards |
| 3 | `python scripts/reproduce.py offline` | No | detector models, predictions, tables, fixed cases |
| 4 | `python scripts/reproduce.py agent --run-id my_main_run` | Yes | paired RAG/no-RAG JSONL and summary |
| 5 | `python scripts/reproduce.py audits --audit-run-id my_audit` | Yes | relevance labels and agreement |
| 6 | `python scripts/reproduce.py strengthening` | Yes | wrong-family and action-evidence controls |
| 7 | `python scripts/reproduce.py reports` | No | final machine-readable tables |
| 8 | `python scripts/reproduce.py verify` | No | release-integrity report |

`bootstrap_inputs.py` verifies the CICIoT2023 archive, performs path-safe
extraction, and downloads any missing standards from their recorded official
URLs. The reporting command reads the saved JSONL records and rebuilds the
summary tables without making API calls.

Build the technical handbook after installing the documentation dependency:

```bash
python -m pip install -e ".[docs]"
python scripts/build_technical_guide.py
```

The three PowerShell files are convenience wrappers retained for Windows users.
They execute the same Python modules. The Python runner is preferred in public
documentation because it works across operating systems and displays API
ceilings before paid stages.

Reference run IDs are preserved. Use a new run ID for new model generation.
Successful records are appended immediately, so the same run ID resumes rather
than repeating completed calls.
