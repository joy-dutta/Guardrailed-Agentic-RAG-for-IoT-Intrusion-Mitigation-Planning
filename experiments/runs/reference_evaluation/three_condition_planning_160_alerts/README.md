# Three-Condition Planning Study

This is the primary planning run. The same 160 fixed alerts are evaluated under relevant RAG, no RAG, and deliberately wrong-family RAG. The run contains 480 successful outputs produced with GPT-5.4 mini.

- `results.jsonl` contains 480 successful records and three retained transport-error records. Error rows are excluded from performance denominators and API cost.
- `summary.json` reports condition counts, source attachment, schema and policy checks, timing, token use, cost, and configured ceilings.

Source configuration: `configs/planning_study_160_alerts.json`.

Repeat with `python scripts/reproduce.py journal-agent`. Use a new output location for a new model or prompt so the reference records remain unchanged.
