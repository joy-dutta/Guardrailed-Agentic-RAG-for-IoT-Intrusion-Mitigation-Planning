# Machine-Readable Results

These CSV and JSON files are the source of truth for reported values. The most
useful starting points are:

| File | Contents |
|---|---|
| `final_analysis.json` | combined analysis and supported claims |
| `detector_split_protocols.json` | detector metrics, calibration, and routing |
| `detector_repeated_seeds.csv` | five-seed stability |
| `agent_results.json` | RAG/no-RAG, schema, policy, latency, and cost |
| `retrieval_audit_interrater_agreement_v2.json` | two model-based relevance audits |
| `action_evidence_faithfulness.json` | relevant versus mismatched evidence support |
| `action_evidence_binding.json` | action-specific evidence support |
| `guardrail_mutation_stress.json` | nine mutation types and guardrail dispositions |
| `detector_error_propagation.json` | wrong-label and top-two action analysis |

Files ending in `_items.csv` provide item-level evidence. Files containing
`blind_packet` intentionally leave human labels blank so another assessor can
review them without seeing prior judgments.

See `docs/results/RESULT_TO_ARTIFACT_MAP.md` for the module associated with each
table.
