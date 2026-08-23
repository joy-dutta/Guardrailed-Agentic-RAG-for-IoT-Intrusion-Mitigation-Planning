$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"

& $Python -m iot_poc.dataset --config configs/experiment.json
& $Python -m iot_poc.detector --config configs/experiment.json
& $Python -m iot_poc.detector_benchmark --config configs/experiment.json
& $Python -m iot_poc.alerts --config configs/experiment.json
& $Python -m iot_poc.split_protocols --config configs/experiment.json
& $Python -m iot_poc.detector_protocols --config configs/experiment.json
& $Python -m iot_poc.hierarchical_detector --config configs/experiment.json
& $Python -m iot_poc.detector_repeated_seeds --config configs/experiment.json
& $Python -m iot_poc.family_routing --config configs/experiment.json
& $Python -m iot_poc.detector_alternatives --config configs/experiment.json
& $Python -m iot_poc.alerts_protocol
& $Python -m iot_poc.error_propagation --run-id paper_final_v2
& $Python -m iot_poc.guardrail_stress --run-id paper_final_v2
& $Python -m pytest -q
& $Python -m iot_poc.provenance
