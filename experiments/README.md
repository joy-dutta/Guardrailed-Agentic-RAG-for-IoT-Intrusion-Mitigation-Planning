# Experiment Records

This folder preserves the records needed to verify the reported experiments. Every retained run contributes to a result or robustness check. Superseded development runs are not included in the public repository.

Start with [`runs/README.md`](runs/README.md). It gives the recommended reading order and explains every run in plain language.

The records are append-only JSONL files with derived JSON summaries. They contain research inputs and outputs, validation results, timing, token counts, and estimated API cost. They do not contain API keys, authorization headers, or complete provider response objects.

The two independent model reviews are stored under [`reports/comprehensive_evaluation/model_audit/`](../reports/comprehensive_evaluation/model_audit/README.md) because they evaluate saved plans rather than generate new plans.
