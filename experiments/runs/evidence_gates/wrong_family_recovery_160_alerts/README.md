# Evidence Gate After Wrong-Family Retrieval

The 160 wrong-family planning outputs contained 376 proposed actions. The gate does not treat the original evidence as correct. It retrieves again for each action, rebinds citations, checks policy compatibility, removes weak actions, and uses a cautious fallback when necessary.

Important files:

| File | Content |
|---|---|
| `original_action_items.jsonl` | 376 actions before recovery |
| `checker_a_results.jsonl` | Gate-checker support labels |
| `checker_b_results.jsonl` | Independent evaluator labels |
| `gated_strict_refined_fallback.jsonl` | 160 final recovery plans |
| `refinement_summary.json` | Denominators, support results, disruptive-action counts, calls, and cost |

The final set contains 213 actions: 199 supported and 14 unsupported under the independent evaluator. All 33 disruptive actions present before the gate were removed.

Source configuration: `configs/evidence_gate_wrong_family.json`.
