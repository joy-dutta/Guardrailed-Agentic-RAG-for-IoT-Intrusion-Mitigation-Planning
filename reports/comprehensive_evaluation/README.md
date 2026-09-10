# Comprehensive Evaluation: Results And Meaning

This folder contains the complete expanded evaluation: more alerts, stronger statistical controls, model sensitivity, action-level evidence checking, and independent model review. The contribution remains mitigation **planning**, with a clear path toward future controlled deployment testing.

## Plain-Language Takeaway

The results support a clear claim: an IoT detector does not have to pass every alert directly to an LLM or a firewall. The detector can first route uncertain alerts to review. For the remaining alerts, retrieval can show the official security text used by the planner, while deterministic guardrails and action-level evidence checks turn the proposal into a smaller and more cautious plan.

Every produced action remains `PROPOSED_NOT_EXECUTED`. This makes the experiment a focused evaluation of decision support and failure containment, without implying that a live device was blocked.

## What Data Entered Each Experiment?

The detector uses the downloaded CICIoT2023 CSV archive. Thirty-three attack
types plus benign traffic are mapped to eight operational traffic families: normal (Benign),
BruteForce, DDoS, DoS, Mirai, Reconnaissance, Spoofing, and Web attacks. Files
or ordered row blocks are kept separate across training, calibration, and test
partitions where the dataset structure permits. The canonical final test
partition contains 78,599 numerical traffic rows.

The agent experiment does not use all test rows. It uses 160 traceable alerts,
20 from each true family. The sample deliberately contains detector-correct,
detector-error, confidence-qualified, and escalated alerts. Seventy-five of the
160 alerts are detector errors, and 80 are below the selected confidence
threshold. This is an uncertainty stress test, not an estimate of how often
attacks occur in the real world.

For each alert, the agent receives one of three conditions:

| Condition | What the planner sees | Why it is included |
|---|---|---|
| Relevant RAG | Three retrieved chunks based on the predicted traffic family | Tests standards traceability |
| No RAG | No retrieved text | Shows what changes without retrieval |
| Wrong-family RAG | Three chunks retrieved using a deliberately different family | Controls for merely copying citations from any supplied text |

The standards corpus contains 666 chunks prepared from ETSI EN 303 645, NISTIR
8259A, NIST SP 800-213, NIST SP 800-213A, NIST SP 800-61r3, RFC 8520, and RFC
8576. Retrieval uses TF-IDF with 1,400-character chunks, 180-character overlap,
and top-three selection.

## 1. Detector and Confidence Results

The original calibration partition is split again. One half fits the confidence
mapping; the other half selects both the mapping and the confidence threshold.
Final test labels are never used for fitting, method selection, or threshold
selection. The process is repeated over five fixed seeds.

### Calibration comparison

| Method | Mean ECE | Mean Brier | Mean NLL | Planning coverage | Accuracy among covered rows |
|---|---:|---:|---:|---:|---:|
| Raw score | 0.0317 | 0.3130 | 0.6222 | 53.4% | 96.2% |
| Sigmoid | 0.0785 | 0.3205 | 0.6798 | 54.0% | 96.2% |
| Isotonic | **0.0278** | **0.3091** | 0.6276 | 54.6% | 96.0% |

Lower calibration error is better. Isotonic calibration gives the best mean ECE
and Brier score and is selected independently under all five seeds. The raw
score has a slightly better NLL. The routing outcome is similar across methods,
so the confidence result is stable rather than dependent on one mapping.

### Detector-family sensitivity

| Detector | Mean macro-F1 | Mean ECE | Planning coverage | Accuracy among covered rows |
|---|---:|---:|---:|---:|
| Random Forest | 0.7328 | **0.0278** | 54.6% | 96.0% |
| Histogram gradient boosting | **0.7365** | 0.0398 | 54.1% | 95.9% |
| Extra Trees | 0.7054 | 0.0313 | 47.4% | 95.0% |

Histogram gradient boosting gives the highest mean macro-F1, while Random
Forest gives the best calibration and almost the same routing accuracy. This
shows that the confidence-routing finding is not unique to one classifier. It
does not claim a new state-of-the-art intrusion detector.

### Global versus family-aware routing

| Routing rule | Mean planning coverage | Mean covered-row accuracy | Mean wrong covered rows |
|---|---:|---:|---:|
| One global threshold | 54.6% | 96.0% | 1,744.2 |
| Predicted-family thresholds | 47.7% | **96.8%** | **1,214.6** |

One overall percentage can hide a weak traffic family. The family-aware rule
selects separate thresholds using only the threshold-validation partition and
fails closed when a family cannot meet the rule there. It sends about seven
additional percentage points of traffic to review and reduces wrong retained
decisions by about 30% on average. Benign predictions fail closed under all five
seeds, and Web predictions remain the least stable under test shift. The honest
claim is risk reduction, not guaranteed correct classification.

## 2. Expanded Agent Experiment

The primary run uses `gpt-5.4-mini-2026-03-17` for 160 alerts under all three
conditions, giving 480 paired outputs.

| Result | Relevant RAG | No RAG | Wrong-family RAG |
|---|---:|---:|---:|
| Complete outputs | 160 | 160 | 160 |
| Compact proposal schema valid | 95.6% | 91.9% | 92.5% |
| Full executor schema valid before normalization | 0% | 0% | 0% |
| Raw policy conformant | 69.4% | 63.8% | 68.8% |
| Valid retrieved identifier attached | **98.8%** | **0%** | 94.4% |
| Full schema valid after guardrails | 100% | 100% | 100% |
| Policy conformant after guardrails | 100% | 100% | 100% |

Relevant RAG versus no RAG produces a decisive paired difference in valid
evidence attachment (158 cases versus none; exact McNemar
`p = 5.47e-48`). The smaller differences in compact schema validity and raw
policy conformance are not statistically significant. In simple terms,
retrieval supplies traceability; it does not replace validation.

Wrong-family RAG also attaches well-formed identifiers in most cases. This is
expected: a model can copy a real identifier from irrelevant context. Identifier
validity proves where a citation came from, not whether that passage truly
supports the action. The action-level evidence gate and blinded model audits
therefore evaluate semantic support separately. A security-aware human audit
would provide the strongest additional validation of that judgment.

The 0% to 100% full-schema change is also expected by design. The model creates
a compact proposal. Deterministic normalization then adds the validated alert
identity, bounded parameters, approval and rollback fields, canonical action
names, and the non-execution state before the independent full-schema and policy
checks. This proves enforcement of declared invariants, not operational wisdom.

## 3. Does the LLM Add Anything?

A policy-only baseline builds a valid plan from fixed rules without an LLM. It
is schema-valid and policy-conformant in all 160 cases by construction.

The RAG agent contributes at least one action that survives validation in
156/160 cases. Its final action set exactly matches the policy-only baseline in
75.6% of cases and differs in 24.4%. For escalated and monitor-only alerts, the
guardrail deliberately reduces both approaches to the same conservative plan.
For the 61 alerts eligible for planning, only 36.1% exactly match the fixed
baseline. Thus, the LLM mainly adds bounded variation where planning is allowed,
while fixed rules dominate when uncertainty calls for caution.

This result establishes nontrivial LLM participation. It does not establish
that every difference is better. The blinded plan audit tests that question.

## 4. Stronger-Model Sensitivity

A predeclared 32-alert subset contains four alerts from each true traffic
family and an almost even mix of the four uncertainty strata. The same 96 tasks
are repeated with `gpt-5.4-2026-03-05`.

| Observation on the paired subset | GPT-5.4 mini | GPT-5.4 |
|---|---:|---:|
| Compact schema validity, relevant RAG | 31/32 | 32/32 |
| Raw policy conformance, relevant RAG | 24/32 | 25/32 |
| Valid evidence attachment, relevant RAG | 31/32 | 32/32 |
| Guardrailed policy conformance, all conditions | 96/96 | 96/96 |
| Total estimated API cost | USD 0.26 | USD 0.83 |

The stronger model removes a few compact-output misses, but none of its paired
endpoint improvements is statistically significant on this sensitivity sample.
The models' normalized action sets have mean Jaccard overlap from 0.82 to 0.85
across conditions. GPT-5.4 is about 15-18% slower and 3.1 times more expensive
for these tasks. The balanced conclusion is to retain GPT-5.4 mini as the main
model and use GPT-5.4 as evidence that the central findings persist at a higher
model capacity.

## 5. Action-To-Evidence Support And Recovery Gates

The 160 relevant-RAG plans contain 375 actions. A new gate retrieves three
passages for each individual action using the predicted traffic family, action,
active protocols, and observed traffic indicators. It confirms that each
citation came from that retrieval result, checks family/action compatibility,
and asks a blinded checker to label the evidence as direct, general, or
unsupported. The strict version removes unsupported actions and requires more
than general evidence for disruptive actions.

The first fallback retrieval sometimes returned attack guidance rather than
guidance for the fallback itself. Action-weighted retrieval corrected this by
searching separately for traffic capture, monitoring, and operator
notification, then choosing the supported safe candidate. A different,
stronger model evaluated the plans without seeing the gate decisions.

| Independent evaluation | Before gate | After refined gate |
|---|---:|---:|
| Actions with direct or general support | 69.1% | **91.0%** |
| Unsupported actions | 30.9% | **9.0%** |
| Cases with support for every action | 75/160 (46.88%) | **141/160 (88.12%)** |
| Disruptive actions | 32 | 3 |
| Unsupported disruptive actions | 2 | 0 |

The gate removed 195 original actions and inserted a bounded fallback in 32
cases, leaving 212 actions. At case level, 66 plans improved and none worsened
on the independent all-actions-supported measure (two-sided exact McNemar
`p = 2.71e-20`). All final plans remained schema-valid and policy-conformant.
The all-actions-supported rate also increased in every true traffic family and
in both fixed 80-case halves.

The same gate was then applied after deliberately wrong-family retrieval. It did not keep the original wrong-family evidence. It retrieved again for each proposed action, rebound citations, checked policy compatibility, and removed weak actions.

| Wrong-family recovery result | Before gate | After refined gate |
|---|---:|---:|
| Actions with direct or general support | 68.9% | **93.4%** |
| Unsupported actions | 31.1% | **6.6%** |
| Cases with support for every action | 70/160 (43.75%) | **146/160 (91.25%)** |
| Disruptive actions | 33 | **0** |
| Unsupported disruptive actions | 9 | **0** |

The recovery gate removed 205 of the original 376 actions and inserted 42 cautious fallbacks, leaving 213 actions. The higher percentage describes the documentary support of this smaller retained set. It is not planning accuracy. The strongest physical-world result is that no disruptive action survived the wrong-family recovery path.

Together, the two gate experiments demonstrate reduced action/citation mismatch and cautious failure containment. They do not turn an initially wrong source into correct evidence by declaration. Nineteen relevant-RAG actions and fourteen wrong-family-starting actions were still judged unsupported by the independent evaluator, so those items remain visible for review.

## 6. Independent Model Reviews

Two models reviewed the blinded audit records independently:

- Reviewer A: ChatGPT using GPT-5.6 Sol Ultra.
- Reviewer B: Gemini using Gemini Pro Extended.

Both generally rated the final plans as useful and cautious. They found no dependable plan-quality advantage for RAG over no RAG, which keeps the retrieval claim focused on traceability and access to supporting material. They also differed in evidence-label strictness. This variation is informative because it identifies the records where expert interpretation is most valuable.

The completed files and agreement statistics are in `model_audit/`. They are model-based reviews and are not presented as human validation. Blank human-review packets are maintained separately in `human_audit/`.

## 7. Cost And Run Integrity

All 480 primary calls and all 96 stronger-model calls completed. Three earlier
local-network connection rows are retained for provenance but were unbilled and
excluded from analysis. The primary run cost an estimated USD 1.32; the
stronger-model run cost USD 0.83. Their independent hard limits were USD 4.00
and USD 3.00, respectively. No key is stored in this project.

## Next Validation Step

The computational package includes five-seed calibration, three detector families, global and family-aware routing, 480 planning outputs, relevant/no/wrong retrieval, a no-LLM baseline, a stronger-model sensitivity check, two evidence-gate conditions, confidence intervals, exact paired tests, and two independent model reviews.

A security-aware human review would add an expert perspective to the model-based triangulation. Each human reviewer can receive 192 blinded plan candidates and 128 blinded action-evidence items. Agreement should be computed before conditions are revealed. The current package already supports source traceability, deterministic conformance, and retrieval-failure containment; human labels would strengthen claims about practical appropriateness and evidence specificity.

A contained gateway testbed would strengthen a future deployment claim by
measuring attack reduction, benign-service impact, rollback, and latency. It is
not required for the current mitigation-planning claim as long as the manuscript
clearly says no actions were executed. Docker is not used by the detector, RAG,
API, or statistical experiments reported here.

## Reproducing and Inspecting the Results

- `tables/calibration_benchmark.json`: all calibration runs, reliability bins,
  thresholds, and test metrics.
- `tables/detector_model_sensitivity.json`: three detector families over five
  seeds.
- `tables/nested_family_aware_routing.json`: global and family-aware routing.
- `tables/planning_case_audit.json`: provenance and composition of the 160
  planning alerts.
- `tables/expanded_agent_summary.json`: primary 480-output summary.
- `tables/expanded_agent_statistics.json`: Wilson intervals and exact paired
  McNemar tests.
- `tables/policy_only_baseline.json`: fixed-policy versus agent comparison.
- `tables/gpt54_sensitivity_case_audit.json`: prespecified stronger-model sample.
- `tables/gpt54_sensitivity_summary.json`: complete stronger-model run.
- `tables/model_sensitivity_comparison.json`: paired model comparison.
- `tables/evidence_gate_ablation.json`: original and first-pass gate metrics.
- `tables/evidence_gate_refined_fallback.json`: final action-weighted fallback
  result and paired test.
- `tables/evidence_gate_refined_items.csv`: item-level retrieval, checker
  judgments, and keep/remove reasons for the final gate.
- `RELEVANT_RAG_EVIDENCE_GATE.md`: plain-language meaning and
  paper-safe claim.
- `WRONG_FAMILY_RECOVERY_GATE.md`: interpretation of the deliberately
  mismatched retrieval recovery test.
- `human_audit/README.md`: blinded review procedure and scoring definitions.
- Local plots can be generated from the stored tables. Publication figures are
  deliberately excluded from this repository.

Regenerate the no-cost analyses with:

```powershell
python scripts/reproduce.py journal-reports
```

API runs require a locally supplied `OPENAI_API_KEY` and remain subject to the
hard caps in their JSON configuration files. The primary and stronger-model
scripts are restartable because each successful response is saved immediately.
