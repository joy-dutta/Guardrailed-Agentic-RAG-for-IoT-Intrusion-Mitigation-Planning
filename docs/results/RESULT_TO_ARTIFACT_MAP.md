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
| Calibration method comparison | `reports/journal_extension/tables/calibration_benchmark.json` | `iot_poc.journal_calibration` |
| Detector-family sensitivity | `reports/journal_extension/tables/detector_model_sensitivity.json` | `iot_poc.journal_detector_sensitivity` |
| Global versus family-aware routing | `reports/journal_extension/tables/nested_family_aware_routing.json` | `iot_poc.journal_family_routing` |
| Composition of the 160-alert sample | `reports/journal_extension/tables/planning_case_audit.json` | `iot_poc.journal_cases` |
| Three-condition planning summary | `reports/journal_extension/tables/expanded_agent_summary.json` | `iot_poc.journal_agent` |
| Paired statistics and intervals | `reports/journal_extension/tables/expanded_agent_statistics.json` | `iot_poc.journal_statistics` |
| Policy-only comparison | `reports/journal_extension/tables/policy_only_baseline.json` | `iot_poc.journal_policy_baseline` |
| GPT-5.4 sensitivity | `reports/journal_extension/tables/model_sensitivity_comparison.json` | `iot_poc.journal_model_compare` |
| Relevant-RAG evidence gate | `reports/journal_extension/tables/evidence_gate_refined_fallback.json` | `iot_poc.journal_evidence_gate_refinement` |
| Wrong-family recovery gate | `reports/journal_extension/tables/mismatched_evidence_gate_refined_fallback.json` | `iot_poc.journal_evidence_gate_refinement` |
| Independent model-review agreement | `reports/journal_extension/model_audit/inter_model_agreement.json` | `scripts/analyze_model_audits.py` |

The pilot reference records are in `experiments/runs/paper_final_v2/results.jsonl`. The larger planning records are in `experiments/runs/ieee_access_expanded/results.jsonl`, and the two action-level gates preserve their complete intermediate decisions under their corresponding run directories.

The table map is intentionally explicit. It lets a reader move from a statement in the documentation to the saved machine-readable evidence and then to the Python function that regenerates it.
