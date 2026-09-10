# Results In Plain Language

## The Short Story

The system does not ask an AI model to control an IoT gateway. It asks the model to prepare a proposal, then checks that proposal before any operational use is considered.

The experiments show that this layered approach is useful. Confidence routing sends uncertain detector outputs toward review. Retrieval makes the source material visible. Deterministic guardrails enforce the required format and action limits. The evidence gate then checks each action separately and removes weak or risky recommendations.

## 1. Detector And Confidence Routing

The attack-type-aware detector averaged a macro-F1 of about 0.73 across five seeds. This is strong enough to provide a realistic alert stream for the planning experiment, while still leaving meaningful uncertainty for the routing stage to handle.

Three calibration approaches were compared. Isotonic calibration gave the lowest average calibration error and Brier score. The routing result remained similar across methods, which shows that it was not created by one convenient confidence transformation.

A second experiment compared one global threshold with a different threshold for each predicted traffic family. Family-aware routing retained fewer rows for planning but reduced wrong retained decisions by about 30%. In physical terms, the gateway becomes more selective for families where confidence is less dependable.

## 2. Three Planning Conditions

The same 160 alerts were evaluated three ways:

- Relevant RAG retrieved passages for the detector's predicted family.
- No RAG supplied no retrieved text.
- Wrong-family RAG deliberately retrieved passages for a different family.

Relevant RAG attached at least one valid retrieved identifier in 158 cases. No RAG attached none. This is clear evidence that retrieval adds source traceability.

Wrong-family RAG still attached an identifier in 151 cases. That result is valuable because it exposes the limit of citation counting. A planner can copy a real identifier from unsuitable context. A valid identifier answers "where did this citation come from?" It does not answer "does this passage support the action?"

## 3. What The Guardrails Add

The model produced a compact proposal. It was not asked to recreate the complete executor contract. Deterministic normalization added the validated alert reference, bounded parameters, fixed scope, approval and rollback fields, canonical action names, and the non-execution status. Independent validation then checked the full result.

All tested normalized outputs passed the declared schema and action policy. The separate mutation experiment also challenged the guardrails with 576 damaged proposals, and every final result passed the implemented invariants.

This is a positive enforcement result. It shows that required fields and policy limits do not depend on the model remembering them. It does not claim that every policy definition is perfect or that every plan would work on a live network.

## 4. Why The Evidence Gate Matters

The relevant-RAG plans initially contained 375 actions. The wrong-family plans contained 376. These totals are larger than 160 because one plan can recommend several actions, such as monitoring, traffic capture, and operator notification.

The evidence gate performs fresh retrieval for each action. It also checks whether the action is allowed for the predicted family, whether cited identifiers came from the new retrieval set, and whether a separate checker sees direct, general, or no support.

| Starting condition | Before gate | After gate |
|---|---:|---:|
| Relevant RAG | 259 supported, 116 unsupported | 193 supported, 19 unsupported |
| Wrong-family RAG | 259 supported, 117 unsupported | 199 supported, 14 unsupported |

The number of supported actions did not increase. The gate made the plans smaller by removing weak actions and adding cautious fallbacks where necessary. The support percentage improved because the remaining action set was cleaner.

This is the practical gain: the gate contains the effect of weak retrieval rather than pretending the original evidence was correct. After the wrong-family starting condition, disruptive actions fell from 33 to zero. The system moved toward monitoring, evidence collection, and operator notification.

## 5. What The Model Reviewers Saw

ChatGPT using GPT-5.6 Sol Ultra and Gemini using Gemini Pro Extended independently reviewed blinded plan and evidence records. Both models generally viewed the final plans as useful and cautious. Neither provided convincing evidence that RAG plans were better than no-RAG plans as plans. This helps focus the RAG contribution on traceability and evidence access rather than claiming a general improvement in plan quality.

The reviewers differed in how strictly they classified documentary support. Their results are therefore useful as supplementary views, while a security-aware human assessment remains the stronger next validation step.

## 6. Physical-World Meaning

Imagine that an IoT gateway detects suspicious traffic and the detector is uncertain or retrieves a weak section of a security document. The system does not immediately block a device. It can hold the alert for review, retrieve again for each proposed action, remove disruptive recommendations without adequate support, and return a bounded plan for an operator.

The work therefore contributes a cautious bridge between intrusion detection and mitigation planning. It makes uncertainty, sources, filtering decisions, and final action limits visible before execution becomes possible.
