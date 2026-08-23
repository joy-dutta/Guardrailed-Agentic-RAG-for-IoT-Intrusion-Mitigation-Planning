# Results and Interpretation

## Short Answer: What Does the Evidence Support?

Yes, with a carefully bounded claim. The results support a system that connects
IoT attack detection to **standards-grounded and guardrailed mitigation
planning**. They do not support a claim of perfect attack detection or fully
autonomous enforcement.

### Single-Line Contribution

> We present a reproducible IoT-gateway safety layer that combines confidence
> routing, relevant standards retrieval, action-specific evidence binding, and
> deterministic guardrails to turn detector alerts into bounded mitigation
> intents while escalating uncertainty and suppressing incompatible disruptive
> actions.

The clearest results-based statement is:

> On CICIoT2023, the proof of concept used detector confidence to separate
> higher-confidence alerts from alerts needing escalation, official-document
> retrieval made the LLM's mitigation advice more traceable to IoT-security
> guidance, action-specific retrieval improved evidence support for the final
> actions, and deterministic guardrails converted every tested proposal into a
> schema-valid and policy-conformant mitigation intent. No network action was
> executed, and universal action-level standards support was not achieved.

### Three Introduction Contribution Bullets

1. An end-to-end, reproducible detector-to-intent workflow that uses calibrated
   confidence and conservative top-two-family reasoning to decide when an IoT
   gateway may prepare a response and when it must escalate.
2. A standards-traceability evaluation that goes beyond citation presence by
   comparing relevant, absent, and wrong-family retrieval and auditing whether
   cited passages actually support each proposed action.
3. A deterministic guardrail and action-specific evidence-binding layer that
   constrains scope, action compatibility, parameters, duration, approval,
   rollback, evidence, and non-execution state, including systematic mutation
   and detector-error stress tests.

This is a meaningful workshop contribution because it demonstrates the full
bridge from a detector alert to a bounded, reviewable response plan, while also
showing where human review is still needed.

## What the System Is For

The proof of concept represents an agent at an IoT gateway or cloud security
service. It receives an intrusion-detector alert, retrieves relevant guidance,
asks an LLM for a compact mitigation proposal, and applies deterministic safety
rules. The final object is a **proposed intent**, not a firewall command. Every
intent is marked `PROPOSED_NOT_EXECUTED`.

The experiment measures four different questions:

1. Can the detector recognize broad IoT attack families?
2. Can uncertain alerts be separated from higher-confidence alerts?
3. Does retrieval attach relevant, valid references to official guidance?
4. Can deterministic guardrails prevent malformed or incompatible proposals
   from reaching an executor-facing interface?

## What a CICIoT2023 Row Represents

One test row is one numerical traffic-flow observation from the official
CICIoT2023 CSV release. A row contains measurements such as protocol flags,
packet sizes, rates, and inter-arrival time. Its folder supplies the known
attack label used only for training and evaluation.

A row is **not** a complete incident, a physical IoT device, or a mitigation
event. CICIoT2023 does not provide a verified device identifier or a live
gateway on which an action can be executed. The experiment therefore evaluates
classification and mitigation-plan generation, not real attack suppression.

The 34 official folder labels are grouped into eight broad families:

| Family | Traffic represented |
|---|---|
| Benign | `Benign_Final` normal traffic |
| BruteForce | dictionary brute-force traffic |
| DDoS | 12 distributed denial-of-service variants |
| DoS | four single-source denial-of-service variants |
| Mirai | Mirai GRE Ethernet flood, GRE IP flood, and UDP-plain traffic |
| Recon | host discovery, OS scan, port scan, and vulnerability scan |
| Spoofing | DNS spoofing and MITM ARP spoofing |
| Web | backdoor malware, browser hijacking, command injection, SQL injection, uploading, vulnerability scan, and XSS traffic |

The exact 34-to-eight mapping is in
`reports/tables/attack_family_mapping.csv`.

## How to Read the Detector Metrics

- **Macro-F1** gives each of the eight families equal importance. It is low
  when minority or difficult families perform poorly, even if common families
  are recognized well.
- **Balanced accuracy** averages recall across the eight families, so a large
  DDoS class cannot dominate the score.
- **Confidence threshold** is the minimum calibrated probability required for
  the alert to continue to bounded mitigation planning.
- **Automatic coverage** is the percentage of test rows above that threshold.
  It means "eligible for automatic planning," not "automatically mitigated."
- **Selective accuracy** is detector accuracy only among those covered rows.
- Rows below the threshold are **escalated** to evidence collection and
  operator review.

## Detector Results Under Three Evaluation Protocols

One split can give a misleading picture, so the detector was evaluated under
three protocols using the same leakage-controlled feature set.

| Protocol | What it tests | Macro-F1 | Balanced accuracy | Coverage | Accuracy on covered rows |
|---|---|---:|---:|---:|---:|
| Random stratified rows | Familiar distribution; source files can occur in all splits | 0.761 | 0.756 | 61.5% | 95.5% |
| Attack-type-aware | Every attack type remains represented; files are separated where possible | 0.715 | 0.712 | 52.1% | 96.5% |
| Strict family/file holdout | Hard stress test with whole files held out, sometimes also holding out rare subtypes | 0.563 | 0.579 | 34.4% | 86.9% |

The **attack-type-aware protocol is the main proof-of-concept result**. It is
more realistic than randomly mixing rows, but it does not accidentally turn a
rare, previously unseen attack subtype into the whole test for a family. Of the
34 attack types, 17 have enough files for file-disjoint splitting; the other 17
use deterministic ordered blocks because fewer than three files are available.

The random-row result is an optimistic reference. The strict result is a useful
distribution-shift stress test and should not be presented as the only measure
of the detector.

### Why the Earlier 0.563 Result Is Not a Failed Implementation

The strict split assigns entire source files to train, calibration, or test.
For attack types represented by very few files, this can also make the test set
contain an attack subtype or collection pattern that was absent during
training. The model then has to generalize across both a new file and, in some
cases, a new subtype. That is substantially harder than recognizing new rows
from represented attack types.

This interpretation was checked rather than assumed:

- the attack-type-aware evaluation improved macro-F1 to 0.715 on the selected
  seed without mixing identical rows across splits;
- random row mixing produced the expected higher reference of 0.761;
- a hierarchical attack-versus-benign then family classifier produced only a
  small gain, macro-F1 0.720 versus 0.715, so extra model complexity is not the
  main answer;
- repeated seeds showed that strict file splitting is much more variable.

The 0.563 value should therefore be described as an honest worst-case stress
result. It shows domain-shift sensitivity and supports cautious escalation. It
does not establish state-of-the-art detection.

## Stability Across Five Fixed Seeds

The two leakage-aware protocols were repeated with five documented seeds.

| Protocol | Macro-F1, mean (range) | Coverage, mean | Selective accuracy, mean (range) |
|---|---:|---:|---:|
| Attack-type-aware | 0.731 (0.706-0.749) | 54.0% | 96.2% (94.8-96.7%) |
| Strict family/file | 0.639 (0.563-0.681) | 41.7% | 93.9% (86.9-98.0%) |

The original strict value of 0.563 was the lowest of the five strict runs. The
attack-type-aware result is both stronger and more stable. Four of its five
seeds reached at least 95% selective accuracy, so the evidence supports risk
reduction, not a universal 95% guarantee.

## Did Family-Specific Thresholds Solve the Weak Classes?

No. A threshold was selected separately for every predicted family using only
calibration data. Across five seeds, this reduced mean planning coverage from
54.0% to 46.0% and increased mean selective accuracy only from 96.2% to 96.7%.
One seed still fell to 94.4%, and several family-level calibration targets did
not transfer to held-out files.

This negative result is important. A gateway should not assume that assigning a
different probability threshold to Web, Recon, or Spoofing makes those classes
reliable. Under distribution shift, these families should remain conservative
or operator-led.

## Exactly What the 0.85 Threshold Result Means

For the selected attack-type-aware run, the data contained 221,795 training
rows, 78,133 calibration rows, and 78,599 final test rows. The threshold was
chosen using the calibration rows only. Test labels were not used to choose it.

The selected confidence threshold was 0.85:

- 40,919 of 78,599 test rows were above the threshold, so coverage was 52.1%;
- 39,475 of those covered rows were classified correctly;
- 1,444 covered rows were classified incorrectly;
- 37,680 rows were below the threshold and were routed to escalation;
- selective accuracy among covered rows was 96.5%.

In simple terms, the detector allowed roughly half of the alerts to continue to
guardrailed response planning and stopped the less-certain half for review. It
did **not** automatically block 52.1% of attacks, and it made no gateway change.

## Which Attacks the Detector Handles Better

For the selected attack-type-aware test, family-level F1 was:

| Family | F1 | Plain-language reading |
|---|---:|---|
| Mirai | 0.998 | Very strong on these sampled Mirai patterns |
| DoS | 0.872 | Strong, with some confusion with DDoS |
| DDoS | 0.846 | Strong, with some confusion with DoS |
| Spoofing | 0.781 | Useful but not complete |
| Benign | 0.616 | Too many normal rows still raise alerts |
| Recon | 0.586 | Moderate; overlaps with benign/Web patterns |
| BruteForce | 0.530 | Weak; only one source file limits robust splitting |
| Web | 0.494 | Weakest and internally heterogeneous |

When the eight attack families are collapsed to **attack versus benign**, the
detector found 58,573 of 63,613 attack rows and missed 5,040. Attack recall was
92.1%, precision was 90.6%, and attack F1 was 0.913. However, it also marked
6,070 of 14,986 benign rows as attacks, a 40.5% benign false-positive rate.

This is a mixed but informative result: the detector recognizes most attack
traffic, but it is not suitable for unconditional autonomous enforcement
because benign false alarms remain high. The confidence gate and guardrails are
therefore part of the contribution, not cosmetic additions.

Two stronger model families did not materially change this result. Extra Trees
reduced macro-F1 to 0.695. Histogram gradient boosting reached 0.720, only 0.005
above the Random Forest, while its confidence-routed accuracy was slightly
lower. The detector limitation is therefore not explained by one obviously
weak classifier choice.

## What Was Sent to the LLM

The paired agent experiment used 32 fixed test alerts, four for each true
family. For every family, the selector chose two high-confidence correct
predictions, one lower-confidence correct prediction, and one
highest-confidence error. This deliberately includes easy, uncertain, and
wrong detector outputs instead of showing only favorable examples.

The final routes were 19 `plan`, nine `escalate`, and four `monitor` cases. Both
RAG and no-RAG conditions received the same 32 alerts. The LLM saw the predicted
family and confidence, not the hidden ground-truth label.

## RAG Versus No RAG

With retrieval, 31 of 32 responses attached at least one valid identifier from
the retrieved official corpus. Without retrieval, zero of 32 attached a
standards identifier. The paired exact test gives `p = 9.31e-10`.

This strongly supports one narrow claim: official-document RAG makes response
plans more traceable to security guidance. It does not prove that every
sentence is entailed by a standard or that the advice will suppress a real
attack.

The corpus contained 666 chunks from seven official documents: NISTIR 8259A,
NIST SP 800-213, NIST SP 800-213A, NIST SP 800-61 Rev. 3, ETSI EN 303 645
V3.1.3, RFC 8520, and RFC 8576.

## Why Valid Citations Were Not Enough

A stronger control supplied three official chunks retrieved for the wrong
attack family while keeping the same model, prompt, context format, and
citation instruction. All 32 wrong-family responses still copied valid chunk
identifiers. Identifier validity is therefore a formatting and traceability
check, not evidence that the cited passage supports the action.

A blinded action-to-evidence audit evaluated 84 original RAG actions and 96
wrong-family-control actions:

| Retrieval condition | Directly supported | Directly or generally supported | Unsupported |
|---|---:|---:|---:|
| Relevant RAG | 6.0% | 42.9% | 57.1% |
| Wrong-family retrieval | 2.1% | 13.5% | 86.5% |

Among 28 paired cases with auditable raw actions, relevant retrieval was clearly
better: eight cases succeeded only with relevant RAG and one only with the
wrong-family control (`p = 0.039`). However,
the original global evidence list still left most individual actions without
adequate passage-level support. A valid identifier alone does not show that a
standard supports the associated action.

## Action-Specific Evidence Binding

The strengthened pipeline performs a second deterministic retrieval after the
guardrail has fixed the final action set. Each bounded action receives its own
two action-and-family-specific excerpts. This does not change the LLM output or
execute anything; it makes the final intent easier for an operator to inspect.

Across 80 final actions, blinded model-based auditing found 15.0% directly
supported, 68.8% directly or generally supported, and 31.3% unsupported. All
actions were supported in 15 of 32 cases (46.9%). The evidence-bound intents
remained 100% schema-valid and policy-conformant.

This improves the standards-grounding story substantially, but it is not
universal entailment. Unsupported actions should be removed, replaced with a
bounded default, or explicitly marked for operator review in a future live
system.

## Independent Second Relevance Auditor

Sixteen cases, two per predicted family, contributed 48 top-three retrieved
excerpts. A first semantic audit labelled each excerpt `direct`, `supporting`,
or `irrelevant`. A second, separately run model-based auditor judged the same
excerpts without seeing the first labels. Items were separated by family to
reduce cross-family confusion.

| Audit view | Direct | Supporting | Irrelevant | Relevant or supporting |
|---|---:|---:|---:|---:|
| First audit | 40 | 6 | 2 | 46/48 |
| Blinded second audit | 40 | 8 | 0 | 48/48 |
| Conservative agreement | - | - | - | 46/48 |

The auditors gave exactly the same three-way label to 46 of 48 excerpts
(95.8%), with three-way Cohen's kappa 0.854. Both disagreements concerned the
same third-ranked general RFC excerpt for two Web cases: the first audit called
it irrelevant, while the second considered it supporting context. The
conservative result remains 46/48 relevant or supporting.

This is an independent **model-based** audit, not a human assessment.
`reports/tables/retrieval_audit_blind_packet.csv` hides both existing judgments
so an independent assessor can evaluate the passages without seeing prior
labels.

## What the Guardrail Ablation Shows

All 64 LLM responses were parseable JSON. Raw compact-proposal schema validity
was 90.6% without RAG and 87.5% with RAG. Raw full executor-schema validity was
0% in both conditions because the LLM was intentionally asked for a compact
mitigation proposal, while mandatory target, duration, rollback, approval,
status, and validated-evidence fields belong to deterministic normalization.

Raw action-policy conformance was 75.0% without RAG and 62.5% with RAG. Thus,
RAG did not make raw actions safer. After deterministic normalization, all 64
records passed both the full schema and action policy.

| Check | Raw result | After deterministic guardrails |
|---|---:|---:|
| Full executor schema | 0/64 | 64/64 |
| Action compatibility policy | 44/64 | 64/64 |

The all-or-nothing schema transition is expected: every raw answer expressed a
compact mitigation idea but lacked the same executor-facing fields. The
guardrail populated those fields from the validated alert and predefined
bounded policy defaults, then independently revalidated the result.

This supports the intended separation of responsibilities; it is not evidence
that the LLM is perfect. The experiment shows that RAG and guardrails solve different
problems: RAG provides standards context; guardrails enforce the output
contract and action policy.

### Mutation Stress Test

The guardrails were additionally tested on 576 systematically damaged
proposals covering overbroad targets, incompatible actions, extreme numeric
parameters, fabricated evidence, excessive or missing actions, non-object
output, low-confidence disruption, and benign disruption.

Before normalization, 69.3% passed the compact schema and 37.5% passed the
action policy. After guardrails, all 576 passed the full schema, policy, and
eight explicit invariants: validated scope, bounded duration, approval for
disruptive actions, retrieved evidence only, at most three actions,
non-disruptive escalation, benign non-disruption, and
`PROPOSED_NOT_EXECUTED` status.

This demonstrates deterministic enforcement against the tested mutation
classes. It does not prove resistance to arbitrary software attacks or that a
permitted action is operationally effective.

## What Happens When the Detector Is Wrong?

The 32 agent cases intentionally include eight detector errors. Across the two
LLM conditions, current normalized actions were strictly compatible with the
hidden true family in 50.0% of those error records. Three of 16 paired error
records contained a disruptive action incompatible with the true family.

A conservative alternative restricted actions to those shared by the top two
detector hypotheses. It eliminated all wrong-family disruptive actions in this
test, reduced the total number of disruptive actions from 20 to four, and kept
100% schema and predicted-family policy validity. Strict true-family action
compatibility improved to 62.5%, because a harmless monitoring action may still
be insufficient for the actual attack.

In physical terms, top-two filtering reduces the chance that one incorrect
label produces an unsuitable restrictive gateway policy. It trades aggressive
response for observation and escalation, which is appropriate for an offline
safety-first proof of concept.

## Latency and Cost

In `paper_final_v2`, no-RAG calls averaged 3.294 seconds end to end and RAG
calls averaged 3.508 seconds. Retrieval itself averaged 7.2 milliseconds. This
small sample does not establish a meaningful latency advantage for either
condition.

The final 64 calls cost an estimated USD 0.1675. The new strengthening package
used 48 successful calls and an estimated USD 0.2383, below its 50-call and USD
0.35 hard limits. Including all preserved exploratory, reference, and audit runs,
estimated API development cost was USD 0.7717. Forty sandbox-blocked transport
attempts produced no API response and no estimated usage cost; they remain in
the run ledger for transparency.

## What Can Be Said With Confidence

- The detector is useful as an alert source, especially for Mirai, DoS, and
  DDoS, but it is not reliable enough for unconditional enforcement.
- Attack-type-aware evaluation gives a reproducible mean macro-F1 of 0.731 over
  five seeds; strict whole-file shift remains harder and more variable.
- Confidence routing substantially increases accuracy on the retained alerts
  while explicitly escalating the rest.
- Official-document RAG adds valid, relevant, and traceable standards evidence
  compared with the same prompts without RAG.
- Relevant retrieval supports more proposed actions than equally formatted
  wrong-family retrieval, and action-specific evidence binding improves support
  further.
- The independent second audit agrees strongly with the first relevance audit;
  the conservative relevance result remains 46/48.
- RAG does not replace safety checks. Deterministic guardrails are what make the
  final intent conform to the executor schema and predefined action policy.
- The guardrails maintained all declared invariants across 576 mutated
  proposals, and top-two filtering eliminated wrong-family disruptive actions
  in the intentionally misclassified test cases.
- The proof of concept produces mitigation intent only. It does not demonstrate
  live attack blocking, benign-service preservation, or rollback execution.

## Interpretation Boundaries

- The detector is a workflow component, not a state-of-the-art benchmark claim.
- The 52.1% coverage result means that those test rows were eligible for
  guardrailed planning; it does not mean that 52.1% of attacks were mitigated.
- Selective accuracy depends on the evaluated split and does not always reach
  95%.
- RAG adds traceable context but did not improve raw policy compliance in this
  run.
- A valid citation identifier does not prove action support. The model-based
  audit left 31.3% of action-specific evidence bindings unsupported.
- Both relevance auditors are model-based; the blank audit packet supports a
  separate human assessment.
- The prototype does not execute actions or measure mitigation effectiveness.
- Dataset rows lack verified device identities, so the generated scope is a
  flow profile rather than a specific device.

## Strengthening Work Completed and Remaining

The low-cost strengthening experiments are complete: three split protocols,
five fixed seeds, family-specific routing, alternative detectors, detector
error propagation, top-two conservative actions, paired RAG/no-RAG,
wrong-family retrieval, action-level faithfulness, action-specific evidence
binding, 576 guardrail mutations, and two retrieval-relevance audits. No
additional paid LLM experiment is needed for the current offline proof of
concept.

Two future additions would answer different, stronger questions. First, an
independent assessor can label the prepared blind audit packet to add human
relevance evidence. Second, a contained gateway or network emulator could
measure attack suppression, benign impact, rollback success, and action latency.
That emulator study would support mitigation-effectiveness claims that the
present dataset cannot answer.
