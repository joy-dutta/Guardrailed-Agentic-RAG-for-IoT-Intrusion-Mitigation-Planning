# Machine-Readable Results

These CSV and JSON files are the source of truth for reported values. The most
useful starting points are:

| File | Contents |
|---|---|
| `reference_analysis.json` | combined reference analysis and claim boundaries |
| `detector_split_protocols.json` | detector metrics, calibration, and routing |
| `detector_repeated_seeds.csv` | five-seed stability |
| `agent_results.json` | RAG/no-RAG, schema, policy, latency, and cost |
| `retrieval_audit_independent_agreement.json` | two model-based relevance audits |
| `wrong_family_retrieval_control.json` | deliberately mismatched retrieval control |
| `action_evidence_faithfulness.json` | relevant versus mismatched evidence support |
| `action_evidence_binding.json` | action-specific evidence support |
| `guardrail_mutation_stress.json` | nine mutation types and guardrail dispositions |
| `detector_error_propagation.json` | wrong-label and top-two action analysis |

Files ending in `_items.csv` provide item-level evidence. Files containing
`blind_packet` intentionally leave human labels blank so another assessor can
review them without seeing prior judgments.

See `docs/results/RESULT_TO_ARTIFACT_MAP.md` for the module associated with each
table.
