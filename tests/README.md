# Tests

Run the complete fast test suite with:

```bash
python scripts/reproduce.py smoke
```

The tests cover attack-family mapping, path handling, dataset preparation
assumptions, split isolation, retrieval identifiers, schema validation,
family-action compatibility, target-scope rewriting, bounded parameters,
evidence filtering, benign and low-confidence fallbacks, top-two conservative
actions, and strengthening-analysis helpers.

Tests do not call the OpenAI API and do not require the CICIoT2023 archive.
They test deterministic software behavior, not whether a permitted mitigation
will work on a live network.

