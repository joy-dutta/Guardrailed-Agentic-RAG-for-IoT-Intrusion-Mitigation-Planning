# Run Index

| Run ID | Role | Used in the reference analysis? |
|---|---|---:|
| `paper_main` | Early query-development record | No |
| `paper_final` | First frozen planning record | No |
| `paper_final_v2` | Paired RAG/no-RAG run on 32 fixed alerts | Yes |
| `second_relevance_audit` | Early audit-development record | No |
| `second_relevance_audit_v2` | Blinded second model-based relevance audit | Yes |
| `shuffled_rag_control` | Wrong-family official retrieval control | Yes |
| `action_evidence_faithfulness` | Blinded action-to-evidence audit | Yes |
| `action_evidence_binding_audit` | Action-specific retrieval and audit | Yes |
| `ieee_access_expanded` | 160 alerts across relevant, absent, and wrong-family retrieval | Yes |
| `ieee_access_gpt54_sensitivity` | Fixed 32-alert GPT-5.4 sensitivity run | Yes |
| `ieee_access_evidence_gate` | Relevant-RAG action-level evidence gate and refinement | Yes |
| `ieee_access_mismatched_evidence_gate` | Recovery gate after wrong-family retrieval | Yes |

`results.jsonl` is the primary append-only record. `summary.json` is derived
from successful lines. Transport failures retained in development runs are not
counted as successful API responses or usage cost.

Use a new run ID for new paired generation. Do not overwrite the reference
directories when comparing a new model or prompt.

Each journal run has its own README describing its inputs, files, denominators, and safe interpretation. The earlier runs remain available because the journal experiment builds on the same detector, retrieval, guardrail, and mutation-testing foundation.
