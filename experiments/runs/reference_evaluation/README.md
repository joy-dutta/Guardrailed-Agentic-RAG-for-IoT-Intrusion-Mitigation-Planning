# Reference Evaluation Runs

These folders contain the planning and evidence records used in the reported analysis.

| Folder | What it verifies |
|---|---|
| `paired_rag_no_rag_32_alerts/` | Pilot paired comparison on 32 alerts and two retrieval conditions |
| `independent_relevance_audit/` | Independent blinded relevance judgments |
| `wrong_family_retrieval_control_32_alerts/` | Retrieval control using passages from a different attack family |
| `action_evidence_faithfulness_audit/` | Whether cited passages support individual actions |
| `action_evidence_binding_audit/` | Whether action-specific retrieval improves evidence binding |
| `three_condition_planning_160_alerts/` | Main comparison across relevant RAG, no RAG, and wrong-family RAG |
| `gpt54_model_sensitivity_32_alerts/` | Stronger-model sensitivity check on a fixed subset |

Each subfolder contains its own README and saved records. The 160-alert comparison is the main planning study; the smaller runs provide the focused controls needed to interpret it.
