# Experiment Protocol

`EXPERIMENT_DESIGN.md` records the eight research questions, split assumptions,
fixed case selection, RAG/no-RAG pairing, retrieval audits, action-evidence
controls, guardrail ablation, mutation classes, error propagation, and cost
controls.

`retrieval_audit_judgments.json` contains the frozen first semantic audit used
by `python -m iot_poc.audit`. Item-level and blind human-review packets are in
`reports/tables/`.

`JOURNAL_EXPERIMENT_PROTOCOL.md` explains the completed 160-alert extension step by step. It covers five-seed calibration, three detector families, global and family-aware routing, relevant/no/wrong retrieval, the policy baseline, stronger-model sensitivity, both evidence gates, GPT-5.6 Sol Ultra and Gemini Pro Extended reviews, statistics, and cost controls.
