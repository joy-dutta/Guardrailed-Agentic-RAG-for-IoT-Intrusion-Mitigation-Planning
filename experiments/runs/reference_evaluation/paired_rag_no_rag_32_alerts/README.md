# Paired RAG and No-RAG Pilot

This reference run applies two planning conditions to the same 32 fixed alerts: relevant RAG and no RAG. It contains 64 successful planning outputs produced with GPT-5.4 mini.

- `results.jsonl` contains the alert, condition, retrieved passages, raw proposal, checked intent, validation results, timing, token use, and estimated cost.
- `summary.json` aggregates successful records by condition.

This run supports the pilot traceability and guardrail analyses. The larger 160-alert comparison is the primary planning experiment.
