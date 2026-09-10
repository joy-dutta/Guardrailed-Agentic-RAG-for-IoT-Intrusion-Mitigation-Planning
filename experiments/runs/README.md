# Final Experiment Run Index

Only runs used in the reported evaluation are kept here. They are grouped by purpose:

1. [`reference_evaluation/`](reference_evaluation/README.md) contains the planning comparisons, retrieval controls, and evidence audits.
2. [`evidence_gates/`](evidence_gates/README.md) contains the two action-level filtering experiments.

For the shortest path through the evidence, read these four folders in order:

1. `reference_evaluation/three_condition_planning_160_alerts/`
2. `reference_evaluation/gpt54_model_sensitivity_32_alerts/`
3. `evidence_gates/relevant_rag_160_alerts/`
4. `evidence_gates/wrong_family_recovery_160_alerts/`

The remaining reference folders support the pilot comparison, retrieval relevance, citation faithfulness, and action-specific evidence binding. [`run_catalog.csv`](run_catalog.csv) provides a machine-readable index with the purpose and denominator of every retained run.

Within a run, `results.jsonl` is the saved record and `summary.json` is the derived overview. Some runs also contain intermediate gate decisions. Each run README explains those files and the correct denominator.

Fresh pilot reproductions use `experiments/runs/local_reproduction/` by default. That local workspace is ignored by Git, which protects the published reference records from accidental replacement.
