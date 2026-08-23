# Data Layout

- `raw/`: the registered `CICIoT2023_CSV.zip` archive; unchanged after download
- `interim/CSV/`: the 309 extracted source CSVs; unchanged after extraction
- `processed/ciciot2023_family_sample.csv`: deterministic sampled and cleaned table
- `processed/ciciot2023_split_protocols.csv`: random-row, attack-type-aware,
  and strict whole-file split assignments for every sampled row
- `processed/test_predictions_*.csv`: calibrated detector outputs on held-out rows
- `processed/agent_cases_attack_type_aware.jsonl`: 32 fixed reference alerts
  used by both LLM conditions
- `processed/*.joblib`: fitted detectors and calibrators

The archive and large generated CSV/model files are excluded from Git by
`.gitignore`. They can be recreated with `scripts/bootstrap_inputs.py` and
`scripts/run_offline.ps1`. Input counts are saved in
`../reports/tables/dataset_audit.json`, and all split assignments are summarized
in `../reports/tables/split_protocols.json`.

Do not interpret a CSV row as a uniquely identified physical device. The
dataset does not provide a validated device ID, and generated intents therefore
target an observed flow profile only.
