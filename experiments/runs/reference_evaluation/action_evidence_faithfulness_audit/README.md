# Action-Evidence Faithfulness Audit

This run evaluates whether cited passages directly support, generally relate to, or fail to support individual mitigation actions. Eight blinded model calls cover relevant and deliberately wrong-family evidence.

- `results.jsonl` preserves the item-level judgments.
- `summary.json` reports labels, paired comparisons, token use, cost, and audit status.

The run separates a valid citation identifier from evidence that actually supports an action.
