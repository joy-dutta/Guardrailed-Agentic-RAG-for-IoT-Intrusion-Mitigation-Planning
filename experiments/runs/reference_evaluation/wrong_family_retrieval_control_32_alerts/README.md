# Wrong-Family Retrieval Control

This control applies official passages retrieved for a deliberately different attack family to the same 32 pilot alerts. It tests whether a planner can attach a real source identifier even when the supplied context is unsuitable.

- `results.jsonl` contains 32 successful planning outputs plus retained connection-failure records.
- `summary.json` separates successful records, failures, calls, and estimated cost.

The control demonstrates why identifier validity measures traceability but not semantic support.
