# Expanded 160-Alert Planning Run

This is the primary journal-scale planning run. The same 160 fixed alerts were evaluated under relevant RAG, no RAG, and deliberately wrong-family RAG, producing 480 successful outputs with GPT-5.4 mini.

`results.jsonl` stores each alert, hidden evaluation metadata, condition, retrieved evidence, raw proposal, normalized intent, validation results, timing, token use, and estimated cost. Three earlier transport-error rows are retained for provenance and excluded from the successful-record denominator.

`summary.json` records the condition totals, evidence-attachment rates, schema and policy checks, timing, cost, call ceilings, and run integrity.

Source configuration: `configs/ieee_access_extension.json`

Repeat this stage with `python scripts/reproduce.py journal-agent`. A new scientific run should use a new run ID rather than overwriting these reference records.
