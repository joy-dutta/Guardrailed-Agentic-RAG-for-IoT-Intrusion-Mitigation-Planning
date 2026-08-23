# Method: From Alert to Bounded Intent

## 1. Detect the Traffic Family

A class-balanced Random Forest predicts one of eight families. The primary
model uses 140 trees, maximum depth 22, minimum leaf size 2, and 37
leakage-controlled features. A separate calibration split adjusts confidence
with sigmoid calibration.

## 2. Route by Confidence

The threshold is selected on calibration data to seek at least 95% accuracy on
rows allowed to continue while retaining at least 25% coverage. If both targets
cannot be met, the code chooses the calibration point with the highest
selective accuracy and then the highest coverage.

Coverage means eligible for guardrailed planning. It does not mean the traffic
was blocked. Lower-confidence cases are routed to evidence collection and
operator review.

## 3. Retrieve Official Guidance

The retriever divides seven NIST, ETSI, and IETF documents into 1,400-character
chunks with 180-character overlap. TF-IDF over unigrams and bigrams returns the
top three chunks for a query based on the predicted family and observed
protocols. Query-centered excerpts show the agent the matched part of a long
chunk.

## 4. Ask for Compact Mitigation Intent

The model receives a validated alert and, in the RAG condition, three official
excerpts. It returns a compact proposal containing recommended actions,
rationales, and copied evidence identifiers. The no-RAG condition receives no
excerpts and must return an empty evidence list.

The LLM is not asked to create the complete executor contract. This design
keeps target scope, duration, approval, rollback, and execution status under
deterministic control.

## 5. Normalize and Validate Deterministically

The guardrail layer:

- copies target scope from the validated alert;
- removes actions incompatible with the predicted family;
- replaces uncertain or benign disruption with monitoring and escalation;
- clips durations and action parameters to predefined limits;
- removes fabricated evidence identifiers;
- limits the plan to three actions;
- requires approval and rollback for disruptive actions;
- adds the fixed `PROPOSED_NOT_EXECUTED` status;
- independently revalidates the final object against the full schema and policy.

This is why raw and final schema validity answer different questions. Raw
validity measures the LLM proposal. Final validity measures the deterministic
contract produced by the complete pipeline.

## 6. Bind Evidence to Final Actions

An additional stage retrieves two focused excerpts for each final bounded
action. A blinded model-based auditor labels support as direct, general, or
unsupported. Unsupported actions remain visible in the research output; they
are not evidence of operational approval.

## 7. Keep Execution Out of Scope

No code translates intent into firewall rules or device commands. A deployment
would require gateway-specific authorization, target verification, local
policy, transaction handling, rollback, and live safety testing.

