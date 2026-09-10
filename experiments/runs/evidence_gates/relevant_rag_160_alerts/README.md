# Evidence Gate After Relevant RAG

The 160 relevant-RAG plans contained 375 proposed actions. The gate performs fresh retrieval for each action, verifies source membership, checks family-action compatibility, and applies an independent support evaluation.

Important files:

| File | Content |
|---|---|
| `original_action_items.jsonl` | 375 actions before filtering |
| `checker_a_results.jsonl` | Gate-checker support labels |
| `checker_b_results.jsonl` | Independent evaluator labels |
| `gated_strict_refined_fallback.jsonl` | 160 final checked plans |
| `refinement_summary.json` | Denominators, before-and-after results, subgroups, calls, and cost |

The final set contains 212 actions: 193 supported and 19 unsupported under the independent evaluator. No unsupported disruptive action remains.

Source configuration: `configs/evidence_gate_relevant_rag.json`.
