# Wrong-Family Retrieval Recovery Gate

This run begins with the 160 planning outputs that deliberately received retrieval for a different family from the detector prediction. Those plans contained 376 original actions.

The gate does not declare the original evidence correct. It starts a recovery process by retrieving again for each action, rebinding citations, checking the action policy, removing weak actions, and adding a cautious fallback when needed.

Important files:

| File | Role |
|---|---|
| `original_action_items.jsonl` | The 376 actions proposed after wrong-family retrieval |
| `checker_a_results.jsonl` | Gate-checker support labels |
| `checker_b_results.jsonl` | Independent evaluator labels |
| `gated_strict.jsonl` | First strict-gate plans |
| `refined_fallback_candidates.jsonl` | Action-specific fallback candidates |
| `gated_strict_refined_fallback.jsonl` | Final 160 recovery plans |
| `refinement_summary.json` | Filtering, rebinding, support, disruptive-action, call, and cost totals |

The refined recovery path retained 213 actions. The independent evaluator labelled 199 directly or generally supported and 14 unsupported. All 33 disruptive actions present before the gate were removed. This supports a failure-containment claim, not a claim that the initial wrong-family retrieval was accurate.

Source configuration: `configs/ieee_access_mismatched_evidence_gate.json`

Repeat with `python scripts/reproduce.py mismatched-evidence-gate`.
