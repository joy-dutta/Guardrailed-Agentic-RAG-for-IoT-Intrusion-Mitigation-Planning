# Data Layout

This folder separates source data, temporary extraction, generated detector artifacts, and small shareable examples.

| Folder | Contents |
|---|---|
| `raw/` | The manually downloaded `CICIoT2023_CSV.zip` archive |
| `interim/CSV/` | The 309 extracted source CSV files |
| `processed/` | Deterministic samples, split assignments, detector outputs, models, and fixed planning cases |
| `sample/` | One small alert that can be inspected without downloading CICIoT2023 |

The large archive, extracted CSVs, fitted models, and generated prediction tables are excluded from Git. The two fixed journal case files are included because they are small and allow the planning experiments to be inspected or repeated without retraining the detector:

- `processed/ieee_access_agent_cases.jsonl`: 160 alerts, 20 from each true traffic family.
- `processed/ieee_access_gpt54_sensitivity_cases.jsonl`: the fixed 32-alert stronger-model subset.

The journal sample deliberately contains correct and incorrect detector outputs above and below the selected confidence threshold. It is an uncertainty stress sample, not an estimate of real-world attack prevalence.

Run `python scripts/reproduce.py bootstrap`, followed by `offline` and `journal-offline`, to recreate the excluded files. Input counts and split checks are preserved in `reports/tables/` and `reports/journal_extension/tables/`.

A CICIoT2023 row describes a numerical traffic observation. It does not identify a verified physical device. Generated plans therefore target an observed flow profile and remain non-executing intent.
