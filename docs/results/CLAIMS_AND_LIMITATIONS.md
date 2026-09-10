# Supported Claims And Operating Boundaries

This page separates what the saved experiments demonstrate from what a future deployment would still need to validate. Keeping that distinction clear makes the positive contribution easier to understand.

## What The Evidence Supports

- The detector and confidence-routing stages provide a repeatable way to separate stronger predictions from alerts that deserve more evidence or review.
- Predicted-family-specific thresholds reduce wrong retained decisions compared with one global threshold, at the cost of routing more traffic to review.
- Official-document RAG supplies traceable source identifiers. Relevant RAG attached valid retrieved identifiers in 158 of 160 cases, compared with none under no RAG.
- Valid identifiers alone do not establish semantic support. The wrong-family control also attached valid identifiers in 151 cases, which motivates the action-level evidence gate.
- Deterministic normalization enforces the declared executor schema, action policy, target scope, parameter limits, approval fields, rollback fields, and non-execution status in the evaluated outputs.
- The implemented guardrails contained all 576 tested mutation cases.
- Action-specific retrieval and filtering produced a smaller set of retained actions with a lower unsupported rate under both the relevant-RAG and wrong-family starting conditions.
- After deliberately wrong-family retrieval, the recovery gate removed all disruptive actions in the tested plans. This supports a failure-containment claim.
- GPT-5.6 Sol Ultra and Gemini Pro Extended generally rated the final plans as useful and cautious, while also showing that evidence-specificity judgments depend on reviewer strictness.

## The Most Defensible Contribution

This work provides a reproducible safety layer that converts uncertain IoT alerts into bounded mitigation intent. It combines confidence routing, official-document retrieval, deterministic policy checks, action-specific evidence checking, and conservative fallback behavior before any gateway or cloud action is considered.

## How To Read The Evidence-Gate Percentages

The post-gate values of 91.0% and 93.4% are not classification or planning accuracy. They describe direct-or-general documentary support among the actions that remained after filtering.

- Relevant RAG: 375 proposed actions became 212 final actions; 193 were judged directly or generally supported and 19 unsupported.
- Wrong-family RAG: 376 proposed actions became 213 final actions; 199 were judged directly or generally supported and 14 unsupported.

The gate did not repair the original source by declaration. It performed fresh retrieval for every action, checked policy compatibility, removed weak actions, and inserted cautious fallbacks when a plan became empty. The practical gain is reduced exposure to weak or disruptive recommendations.

## Operating Boundaries

- The detector is an alert source, not a claimed state-of-the-art classifier.
- A retained detector row is sent to planning; it is not automatically mitigated.
- The RAG comparison demonstrates traceability more strongly than improved plan quality.
- Most retained evidence was general rather than direct. It should inform an operator, not be treated as formal authorization.
- The two completed reviewers are language models. Their results strengthen triangulation but do not replace security-aware human judgment.
- CICIoT2023 contains traffic observations without a verified device identity, so the prototype cannot justify device-specific targeting.
- The experiment produces `PROPOSED_NOT_EXECUTED` intent. It does not measure attack suppression, service impact, rollback success, or live gateway enforcement.
- A deployed system would still need trusted policy ownership, corpus protection, authentication, authorization, rollback, monitoring, and operator governance.

These boundaries do not reduce the value of the experiment. They identify exactly where the present evidence is strong and provide a clear path from an offline planning prototype to a future controlled deployment study.
