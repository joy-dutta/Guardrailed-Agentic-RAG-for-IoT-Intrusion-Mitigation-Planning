# Experiment Records

`runs/` contains append-only JSONL records and derived summaries. One successful
API response is written immediately, allowing an interrupted run to resume
without repeating completed case-condition pairs.

The reference analysis uses `paper_final_v2`,
`second_relevance_audit_v2`, `shuffled_rag_control`,
`action_evidence_faithfulness`, and `action_evidence_binding_audit`.

Earlier `paper_main`, `paper_final`, and `second_relevance_audit` runs are kept
as transparent development provenance. They show how generic retrieval queries
and excerpt positioning were corrected. They are not used as final evidence.

No API key, authorization header, or complete provider response object is
stored. Each record contains the structured research input/output, validation
results, timing, token counts, and estimated usage cost needed for analysis.
