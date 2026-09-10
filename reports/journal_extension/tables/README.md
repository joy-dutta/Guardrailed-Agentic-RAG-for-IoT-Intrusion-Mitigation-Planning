# Journal Result Tables

These machine-readable files are the numerical source for the larger experiment. JSON files preserve nested details and CSV files make the main comparisons easy to inspect in a spreadsheet.

## Detector And Routing

| File prefix | Contents |
|---|---|
| `calibration_benchmark` | Raw, sigmoid, and isotonic calibration over five fixed seeds |
| `detector_model_sensitivity` | Random Forest, histogram gradient boosting, and Extra Trees comparison |
| `nested_family_aware_routing` | Global and predicted-family-specific confidence thresholds |
| `planning_case_audit` | Composition and provenance of the fixed 160-alert planning sample |

## Planning And Baselines

| File prefix | Contents |
|---|---|
| `expanded_agent_summary` | Primary relevant-RAG, no-RAG, and wrong-family-RAG results |
| `expanded_agent_statistics` | Confidence intervals and exact paired tests |
| `policy_only_baseline` | Fixed-rule plans and their comparison with agent plans |
| `gpt54_sensitivity` | Saved stronger-model subset summary |
| `model_sensitivity_comparison` | Paired comparison between GPT-5.4 mini and GPT-5.4 |

## Evidence Gates

| File prefix | Contents |
|---|---|
| `evidence_gate_ablation` | First action-level gate on relevant-RAG plans |
| `evidence_gate_refined_fallback` | Final relevant-RAG gate with action-weighted fallbacks |
| `evidence_gate_refined_items` | One row per final action with retrieval and keep/remove reasoning |
| `mismatched_evidence_gate_ablation` | First gate after wrong-family retrieval |
| `mismatched_evidence_gate_refined_fallback` | Final wrong-family recovery result |
| `mismatched_evidence_gate_refined_items` | Item-level recovery evidence and decisions |

The `91.0%` and `93.4%` values in the refined summaries are support rates among retained actions. They are not classification accuracy. Each refined summary records the original action count, removals, fallbacks, final count, support labels, disruptive-action totals, and exact paired test.

Regenerate summaries from the preserved runs with `python scripts/reproduce.py journal-reports`. Paid gate runs are separate commands and remain protected by their configuration limits.
