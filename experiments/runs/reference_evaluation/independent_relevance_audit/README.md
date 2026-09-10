# Independent Retrieval-Relevance Audit

This run contains eight blinded audit batches, one for each predicted traffic family. The evaluator received the retrieved passages and query context without seeing the first audit labels.

`results.jsonl` stores the independent relevance judgments. The corresponding agreement summary is `reports/tables/retrieval_audit_independent_agreement.json`.

This is a model-based relevance audit. It provides an independent second view of retrieval quality and is not labelled as human validation.
