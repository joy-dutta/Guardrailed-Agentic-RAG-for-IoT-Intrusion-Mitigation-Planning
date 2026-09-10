# Action-Specific Evidence Binding Audit

This run retrieves evidence separately for each proposed action and audits the resulting action-to-passage link.

- `results.jsonl` preserves eight audit batches.
- `bound_intents.jsonl` stores the checked intent and evidence selected for every case.
- `summary.json` reports action-level support, whole-plan support, schema validity, policy conformance, calls, and cost.

The experiment tests whether action-specific retrieval improves evidence traceability beyond attaching one passage set to an entire plan.
