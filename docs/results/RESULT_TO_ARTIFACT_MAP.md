# Result-to-Artifact Map

| Result | Primary machine-readable source | Regeneration code |
|---|---|---|
| Dataset size, features, and files | `reports/tables/dataset_audit.json` | `iot_poc.dataset` |
| 34-to-8 mapping | `reports/tables/attack_family_mapping.csv` | `iot_poc.dataset` |
| Split construction | `reports/tables/split_protocols.json` | `iot_poc.split_protocols` |
| Detector performance and calibration | `reports/tables/detector_split_protocols.json` | `iot_poc.detector_protocols` |
| Five-seed stability | `reports/tables/detector_repeated_seeds.csv` | `iot_poc.detector_repeated_seeds` |
| Family-specific routing | `reports/tables/family_specific_routing.json` | `iot_poc.family_routing` |
| RAG/no-RAG and schema ablation | `reports/tables/agent_results.json` | `iot_poc.analysis` |
| Retrieval relevance | `reports/tables/retrieval_audit_interrater_agreement_v2.json` | `iot_poc.audit`, `iot_poc.audit_second` |
| Wrong-family retrieval | `reports/tables/shuffled_rag_control.json` | `iot_poc.shuffled_control` |
| Action evidence support | `reports/tables/action_evidence_faithfulness.json` | `iot_poc.faithfulness_audit` |
| Action-specific binding | `reports/tables/action_evidence_binding.json` | `iot_poc.action_evidence_binding` |
| Guardrail mutations | `reports/tables/guardrail_mutation_stress.json` | `iot_poc.guardrail_stress` |
| Detector-error containment | `reports/tables/detector_error_propagation.json` | `iot_poc.error_propagation` |

The exact reference agent records are in
`experiments/runs/paper_final_v2/results.jsonl`. Earlier runs are retained to
show how the retrieval query and excerpt selection were corrected; they do not
feed the final analysis.
