# Configuration

`experiment.json` is the single frozen source for the random seed, data sample,
detector, retrieval, model snapshot, token limit, call cap, dollar cap, and
retry limit. A reported run should identify this file and its run ID.

The strengthening controls share a combined ceiling of 50 successful API calls
and USD 0.35. Local sub-caps prevent either the wrong-family generation or the
two evidence audits from consuming the full allowance.

Changing the model, query templates, standards corpus, seed, split, or policy
creates a new experimental condition and should use a new run ID.
