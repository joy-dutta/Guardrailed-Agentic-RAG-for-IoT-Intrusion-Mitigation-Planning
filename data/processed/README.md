# Generated Data And Fixed Cases

The full experiment creates sampled traffic tables, split assignments, calibrated predictions, and fitted models here. Large generated files are ignored because they can be rebuilt from the verified CICIoT2023 archive.

Four small JSONL case files are committed for transparent planning reproduction:

| File | Purpose |
|---|---|
| `agent_cases.jsonl` | Original fixed pilot cases |
| `agent_cases_attack_type_aware.jsonl` | Final 32-alert pilot set |
| `planning_cases_160.jsonl` | Main 160-alert, eight-family planning set |
| `model_sensitivity_cases_32.jsonl` | Prespecified 32-alert stronger-model subset |

Each record separates `alert`, which is visible to the planner, from `evaluation`, which contains the hidden true label and sampling provenance. This prevents the planner from receiving ground truth as though it came from a detector.

To regenerate the fixed cases, first run the detector stages, then run `python scripts/reproduce.py journal-offline`. Case selection follows the frozen seed and calibration result in `configs/planning_study_160_alerts.json`.
