# GPT-5.4 Planner Sensitivity Study

This run repeats all three planning conditions on a prespecified 32-alert subset using GPT-5.4. The subset contains four alerts from each true traffic family and balances detector correctness with confidence-routing status.

- `results.jsonl` contains 96 successful planning outputs.
- `summary.json` records model, condition, validation, evidence, timing, token, and cost totals.

Source configuration: `configs/planner_model_sensitivity.json`.

This experiment checks whether the main planning conclusions depend on GPT-5.4 mini. It is a bounded sensitivity analysis, not a claim that one model is operationally superior.
