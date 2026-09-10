# Contributing

Contributions that improve reproducibility, tests, documentation, retrieval
quality, or safe policy handling are welcome.

1. Create a branch from `main`.
2. Install the development environment with `python -m pip install -e ".[dev]"`.
3. Run `python scripts/reproduce.py smoke` before submitting a change.
4. Add focused tests for behavioral changes.
5. Keep live credentials, private data, and machine-specific paths outside commits.
6. Explain whether a result-changing contribution requires new API calls or
   changes the reference configuration.

Changes to the experiment configuration, attack-family mapping, action policy,
prompt, schema, or result tables should include a scientific rationale.
Any new analysis must be derived from the machine-readable files in
`reports/tables/`.
