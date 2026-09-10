# Experiment Configuration

This folder is the frozen control panel for the experiments. Changing a model, seed, split rule, retrieval setting, prompt limit, policy, or cost ceiling creates a new condition and should use a new run ID.

| File | Role |
|---|---|
| `experiment.json` | Base CICIoT2023 preprocessing, detector, retrieval, agent, guardrail, and pilot settings |
| `ieee_access_extension.json` | Five-seed calibration, 160-alert sample, three planning conditions, and human-audit sampling |
| `ieee_access_model_sensitivity.json` | Fixed 32-alert GPT-5.4 sensitivity run |
| `ieee_access_evidence_gate.json` | Action-specific checking for the relevant-RAG outputs |
| `ieee_access_mismatched_evidence_gate.json` | The same recovery gate after deliberately wrong-family retrieval |

## Cost Protection

Each paid configuration contains a maximum number of calls and a maximum estimated cost. The code checks both values before a stage begins and continues checking saved usage while the run proceeds. Successful records are appended immediately, which allows a stopped run to resume.

| Stage | Call ceiling | Estimated-cost ceiling |
|---|---:|---:|
| Expanded planning | 500 | USD 4.00 |
| GPT-5.4 sensitivity | 110 | USD 3.00 |
| Relevant-RAG evidence gate | 20 | USD 2.50 |
| Wrong-family recovery gate | 20 | USD 2.50 |

These safeguards are local estimates, not account-level billing controls. Review the JSON file and the provider account limit before repeating a paid experiment.

No credential belongs in this folder. The implementation reads `OPENAI_API_KEY` only from the running process environment.
