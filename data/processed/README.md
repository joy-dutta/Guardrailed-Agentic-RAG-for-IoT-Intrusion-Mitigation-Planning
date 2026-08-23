# Generated Data and Models

This folder contains deterministic samples, fitted models, calibrated test
predictions, and fixed agent cases. All large artifacts are reproducible from
the raw archive and `configs/experiment.json`; summary numbers and hashes live
under `reports/` and `provenance/`.

`ciciot2023_split_protocols.csv` contains the exact three split assignments used
to compare evaluation assumptions. `agent_cases_attack_type_aware.jsonl`
contains the 32 final detector alerts plus ground truth under a separate
`evaluation` field. Only the `alert` object is sent to the LLM.
