# Results in Plain Language

## The Short Takeaway

The experiment supports a safety-layer contribution, not a claim that an AI
agent can autonomously stop every IoT attack. Stronger detector alerts can be
turned into traceable, machine-checkable response plans. Uncertain alerts are
held for evidence and review, and deterministic code prevents a free-form model
response from becoming an overbroad action.

## Detector and Confidence Routing

Across five attack-type-aware runs, the detector averaged macro-F1 0.731. This
means it was useful but uneven across the eight families. Mirai, DoS, and DDoS
were easier; Web, BruteForce, Recon, Spoofing, and benign traffic created more
confusion.

Confidence routing averaged 96.2% accuracy on the 54.0% of test rows allowed to
continue. In the selected run, a threshold of 0.85 covered 52.1% of 78,599 test
rows at 96.5% accuracy. The remaining rows were not ignored: they were routed
to evidence collection and review. In a gateway, this means the system prepares
plans for stronger alerts and becomes conservative when the detector is unsure.

## RAG Versus No RAG

RAG produced at least one valid official-document identifier in 31 of 32
answers. No-RAG produced none, as required by its empty context. Two model-based
audits examined 48 retrieved passages. The conservative result accepted 46 as
directly relevant or useful supporting context.

This supports the claim that official retrieval improves traceability. It does
not prove that every recommended action follows from its citations.

## Action-Level Evidence

Relevant RAG directly or generally supported 42.9% of the original proposed
actions, compared with 13.5% when the same workflow received deliberately
mismatched threat-family retrieval. Action-specific retrieval after guardrails
raised support to 68.8%. The remaining 31.3% was unsupported.

In practice, a citation beside a plan is not enough. Each action needs its own
evidence check, and an unsupported action should be removed, replaced, or sent
for review before any real executor is considered.

## Guardrails

All 64 raw model responses were parseable JSON, but none met the full
executor-facing schema. This was expected because the model produced compact
mitigation intent and deterministic normalization supplied the mandatory
target, duration, approval, rollback, evidence, and status fields. After that
stage, all 64 records passed the implemented schema and action policy.

The guardrails were also tested on 576 deliberately damaged proposals covering
nine mutation types. Every normalized result passed the declared schema,
policy, and safety invariants. This demonstrates enforcement for the tested
mutations; it does not prove operational effectiveness or resistance to every
possible software attack.

## Detector Errors

The 32 fixed cases include eight deliberately misclassified detector outputs,
giving 16 paired RAG/no-RAG planning records. A conservative top-two-family rule
removed all three wrong-category disruptive cases and improved compatibility
with the hidden true family from 50.0% to 62.5%. Across all 64 planning records,
it reduced disruptive actions from 20 to four.

The physical meaning is straightforward: when two attack explanations are
plausible, the gateway should prefer monitoring and escalation over a
restrictive action that is safe for only one explanation.

## Cost and Runtime

The reference paired run used 64 successful calls at an estimated USD
0.1675. The strengthening controls used 48 successful calls at an estimated USD
0.2383. RAG calls averaged 3.508 seconds end to end, while retrieval itself
averaged about 7.2 milliseconds.

These figures describe the recorded environment and configured historical API
prices. They are not guarantees for another account, region, model revision, or
future price.
