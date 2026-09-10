# GPT-5.4 Sensitivity Run

This run repeats all three planning conditions on a prespecified 32-alert subset using GPT-5.4. The subset contains four alerts from each true traffic family and balances detector correctness with confidence-routing status.

- `results.jsonl`: 96 complete planning outputs.
- `summary.json`: model, token, cost, latency, schema, policy, and evidence-attachment totals.

The sensitivity experiment checks whether the main conclusions depend on using GPT-5.4 mini. It found similar normalized action sets and the same guardrailed conformance pattern, while the stronger model cost more and took slightly longer.

Source configuration: `configs/ieee_access_model_sensitivity.json`

Repeat with `python scripts/reproduce.py model-sensitivity`.
