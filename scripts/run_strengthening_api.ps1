$ErrorActionPreference = "Stop"
if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is not available in this process environment."
}

$Config = Get-Content -Raw -LiteralPath "configs/experiment.json" | ConvertFrom-Json
Write-Host "Combined successful-call cap:" $Config.strengthening_api.combined_max_calls
Write-Host "Combined estimated-cost cap (USD):" $Config.strengthening_api.combined_max_cost_usd

$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"

& $Python -m iot_poc.shuffled_control --config configs/experiment.json
& $Python -m iot_poc.faithfulness_audit --config configs/experiment.json
& $Python -m iot_poc.action_evidence_binding --config configs/experiment.json
& $Python -m iot_poc.analysis
