# Relevant-RAG Evidence Gate

This run checks every action proposed in the 160 relevant-RAG plans. One plan can contain several actions, so the 160 plans produced 375 original actions.

For each action, the gate performs fresh retrieval using the predicted family, action name, active protocols, and important traffic observations. It verifies the retrieved identifiers, checks family/action compatibility, obtains an independent support label, removes weak actions, and inserts a cautious fallback when a plan becomes empty.

Important files:

| File | Role |
|---|---|
| `original_action_items.jsonl` | The 375 actions before filtering |
| `checker_a_results.jsonl` | Gate-checker labels |
| `checker_b_results.jsonl` | Independent evaluator labels |
| `gated_strict.jsonl` | First strict-gate plans |
| `refined_fallback_candidates.jsonl` | Action-weighted fallback candidates |
| `gated_strict_refined_fallback.jsonl` | Final 160 gated plans |
| `refinement_summary.json` | Before/after totals, exact paired test, subgroups, calls, and cost |

The refined gate retained 212 final actions. The independent evaluator labelled 193 directly or generally supported and 19 unsupported. Unsupported disruptive actions fell to zero.

Source configuration: `configs/ieee_access_evidence_gate.json`

Repeat with `python scripts/reproduce.py evidence-gate`.
