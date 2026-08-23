param(
    [string]$RunId = "paper_final_v2",
    [string]$CasesPath = "data/processed/agent_cases_attack_type_aware.jsonl",
    [int]$CaseLimit = 0
)

$ErrorActionPreference = "Stop"
if (-not $env:OPENAI_API_KEY) {
    throw "OPENAI_API_KEY is not available in this process environment."
}

$Config = Get-Content -Raw -LiteralPath "configs/experiment.json" | ConvertFrom-Json
Write-Host "Model:" $Config.agent.model
Write-Host "Hard API attempt cap:" $Config.agent.max_calls
Write-Host "Hard estimated-cost cap (USD):" $Config.agent.max_cost_usd

$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "..\src"
if ($CaseLimit -gt 0) {
    & $Python -m iot_poc.experiment --config configs/experiment.json --run-id $RunId --cases-path $CasesPath --case-limit $CaseLimit
} else {
    & $Python -m iot_poc.experiment --config configs/experiment.json --run-id $RunId --cases-path $CasesPath
}
