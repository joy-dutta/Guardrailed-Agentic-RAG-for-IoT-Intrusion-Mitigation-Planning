# Claims and Limitations

## Supported by the Saved Experiments

- Official-document RAG adds valid and mostly relevant traceable evidence when
  compared with the same prompts without retrieval.
- Relevant retrieval supports more actions than equally formatted wrong-family
  retrieval.
- Action-specific evidence binding improves support for final bounded actions,
  although it does not provide universal support.
- Deterministic normalization enforces the implemented executor schema, action
  policy, target scope, parameter limits, approval, rollback, and non-execution
  status.
- The declared invariants survived all 576 tested proposal mutations.
- Conservative top-two filtering removed wrong-family disruptive actions in
  the deliberately misclassified cases.
- Confidence routing reduces exposure to detector errors by escalating a
  substantial share of uncertain rows.

## Not Supported or Out of Scope

- The detector is not claimed to be state of the art.
- A covered row is not an automatically mitigated attack.
- RAG does not make raw model actions policy-conformant by itself.
- A valid chunk identifier is not proof that every action is semantically
  supported.
- The two relevance auditors are model-based, not two independent humans.
- The experiment does not execute mitigation, measure attack suppression,
  preserve-service impact, or rollback success.
- Dataset rows cannot justify device-specific targeting because they contain no
  verified device identity.
- The mutation test does not prove protection against arbitrary prompt
  injection, a compromised corpus, incorrect policy code, or a faulty executor.

## Appropriate One-Sentence Contribution

This work presents a reproducible IoT-gateway safety layer that combines
confidence routing, relevant standards retrieval, action-specific evidence
binding, and deterministic guardrails to turn detector alerts into bounded
mitigation intent while escalating uncertainty and suppressing incompatible
disruptive actions.

