# Contribution and Physical-World Impact

## Single-Line Contribution

We present a reproducible IoT-gateway safety layer that combines confidence
routing, relevant standards retrieval, action-specific evidence binding, and
deterministic guardrails to turn detector alerts into bounded mitigation intents
while escalating uncertainty and suppressing incompatible disruptive actions.

## Three Introduction Contribution Bullets

1. An end-to-end detector-to-intent workflow that uses calibrated confidence
   and conservative top-two-family reasoning to determine when an IoT gateway
   may prepare a response and when it must escalate.
2. A standards-traceability evaluation that compares no retrieval, relevant
   retrieval, and wrong-family retrieval and audits whether cited passages
   actually support each proposed action.
3. A deterministic guardrail and action-specific evidence-binding layer that
   constrains target scope, compatible actions, parameters, duration, approval,
   rollback, evidence, and non-execution state, tested under detector errors and
   576 systematically damaged proposals.

## Translating the Experiment Into the Physical World

| Experimental term | Physical-world meaning |
|---|---|
| CICIoT2023 row | One numerical network-traffic observation, not a complete incident or uniquely identified device |
| Detector family | The gateway's current hypothesis about the type of suspicious traffic |
| Confidence threshold | The minimum evidence needed to prepare a bounded plan without immediate operator triage |
| Covered row | Eligible for mitigation planning only; no traffic is blocked |
| Escalated row | Collect evidence and notify an operator before considering disruption |
| RAG evidence | Official guidance shown beside the proposal so an operator can inspect its basis |
| Action-specific binding | Separate official excerpts retrieved for each final action rather than one generic citation list |
| Guardrailed intent | A proposed, machine-checkable plan with validated scope, limits, approval, rollback, and no execution status |
| Top-two policy | Permit only actions suitable for both leading detector hypotheses, otherwise escalate |

## What the Results Mean

- The detector is useful for feeding a planning workflow, but difficult Web,
  Recon, BruteForce, Spoofing, and benign traffic prevent unconditional
  enforcement.
- A global confidence gate raises accuracy on retained alerts, but
  family-specific thresholds still fail under some held-out-file shifts.
  Confidence routing reduces risk; it does not guarantee correctness.
- Relevant official retrieval supports more actions than equally formatted
  wrong-family retrieval. Valid identifiers alone are not proof of grounding.
- Action-specific evidence binding raises direct-or-general support to 68.8%,
  but 31.3% remains unsupported. Such actions require replacement or review.
- On deliberately wrong detector labels, top-two action filtering eliminated
  incompatible disruptive actions in this test, while becoming more
  conservative.
- Guardrails preserved every declared invariant across 576 mutated proposals.
  This supports deterministic enforcement, not real attack suppression.

## Evidence-Based Takeaway

The practical value is not that the agent can autonomously block every IoT
attack. The value is that it can prepare a traceable response for stronger
alerts, refuse or escalate uncertain cases, and prevent an LLM proposal from
directly becoming an overbroad gateway action.

The present experiment does not measure attack suppression, service impact,
rollback success, or live gateway execution. Those require a contained network
emulator or physical testbed.
