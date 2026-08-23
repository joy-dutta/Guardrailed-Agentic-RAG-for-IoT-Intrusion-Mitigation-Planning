# Run Index

| Run ID | Role | Used in the reference analysis? |
|---|---|---:|
| `paper_main` | Exploratory query-development run | No |
| `paper_final` | Superseded first final run | No |
| `paper_final_v2` | Paired RAG/no-RAG run on 32 fixed alerts | Yes |
| `second_relevance_audit` | Superseded audit-development run | No |
| `second_relevance_audit_v2` | Blinded second model-based relevance audit | Yes |
| `shuffled_rag_control` | Wrong-family official retrieval control | Yes |
| `action_evidence_faithfulness` | Blinded action-to-evidence audit | Yes |
| `action_evidence_binding_audit` | Action-specific retrieval and audit | Yes |

`results.jsonl` is the primary append-only record. `summary.json` is derived
from successful lines. Transport failures retained in development runs are not
counted as successful API responses or usage cost.

Use a new run ID for new paired generation. Do not overwrite the reference
directories when comparing a new model or prompt.
