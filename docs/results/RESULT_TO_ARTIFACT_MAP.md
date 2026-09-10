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
| Retrieval relevance | `reports/tables/retrieval_audit_independent_agreement.json` | `iot_poc.audit`, `iot_poc.audit_second` |
| Wrong-family retrieval | `reports/tables/wrong_family_retrieval_control.json` | `iot_poc.shuffled_control` |
| Action evidence support | `reports/tables/action_evidence_faithfulness.json` | `iot_poc.faithfulness_audit` |
| Action-specific binding | `reports/tables/action_evidence_binding.json` | `iot_poc.action_evidence_binding` |
| Guardrail mutations | `reports/tables/guardrail_mutation_stress.json` | `iot_poc.guardrail_stress` |
| Detector-error containment | `reports/tables/detector_error_propagation.json` | `iot_poc.error_propagation` |
| Calibration method comparison | `reports/comprehensive_evaluation/tables/calibration_benchmark.json` | `iot_poc.journal_calibration` |
| Detector-family sensitivity | `reports/comprehensive_evaluation/tables/detector_model_sensitivity.json` | `iot_poc.journal_detector_sensitivity` |
| Global versus family-aware routing | `reports/comprehensive_evaluation/tables/nested_family_aware_routing.json` | `iot_poc.journal_family_routing` |
| Composition of the 160-alert sample | `reports/comprehensive_evaluation/tables/planning_case_audit.json` | `iot_poc.journal_cases` |
| Three-condition planning summary | `reports/comprehensive_evaluation/tables/expanded_agent_summary.json` | `iot_poc.journal_agent` |
| Paired statistics and intervals | `reports/comprehensive_evaluation/tables/expanded_agent_statistics.json` | `iot_poc.journal_statistics` |
| Policy-only comparison | `reports/comprehensive_evaluation/tables/policy_only_baseline.json` | `iot_poc.journal_policy_baseline` |
| GPT-5.4 sensitivity | `reports/comprehensive_evaluation/tables/model_sensitivity_comparison.json` | `iot_poc.journal_model_compare` |
| Relevant-RAG evidence gate | `reports/comprehensive_evaluation/tables/evidence_gate_refined_fallback.json` | `iot_poc.journal_evidence_gate_refinement` |
| Wrong-family recovery gate | `reports/comprehensive_evaluation/tables/mismatched_evidence_gate_refined_fallback.json` | `iot_poc.journal_evidence_gate_refinement` |
| Independent model-review agreement | `reports/comprehensive_evaluation/model_audit/inter_model_agreement.json` | `scripts/analyze_model_audits.py` |

The paired pilot records are in `experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/results.jsonl`. The primary 160-alert records are in `experiments/runs/reference_evaluation/three_condition_planning_160_alerts/results.jsonl`. Both action-level gates preserve their inputs, checker judgments, removal reasons, fallbacks, and final plans under `experiments/runs/evidence_gates/`.

The table map is intentionally explicit. It lets a reader move from a statement in the documentation to the saved machine-readable evidence and then to the Python function that regenerates it.
