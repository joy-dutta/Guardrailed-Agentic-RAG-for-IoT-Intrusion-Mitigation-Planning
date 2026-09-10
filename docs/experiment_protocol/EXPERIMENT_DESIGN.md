# Experiment Design

## Research Questions

- **RQ1: Detector realism.** How does a lightweight calibrated detector perform
  under random-row, attack-type-aware, and strict whole-file evaluation?
- **RQ2: Standards grounding.** Does retrieval from official IoT-security
  documents make the generated proposal more traceable than the same prompt
  without retrieval?
- **RQ3: Retrieval relevance.** Are the top retrieved passages actually useful
  for the predicted threat family?
- **RQ4: Guardrail value.** How often is raw LLM output valid under the compact
  proposal contract, the full executor-facing contract, and the action policy;
  and how do those rates change after deterministic normalization?
- **RQ5: Practicality.** What latency, token use, and estimated API cost does the
  offline pipeline add?
- **RQ6: Error propagation.** When the detector is wrong, can a top-two-family
  policy prevent an unsuitable disruptive response?
- **RQ7: Evidence faithfulness.** Do cited standards excerpts support each
  proposed action, rather than merely providing a valid identifier?
- **RQ8: Guardrail robustness.** Do declared safety invariants survive
  systematically malformed, incompatible, and overbroad proposals?

## Dataset and Labels

The registered CICIoT2023 CSV release contains 309 files under 34 attack or
benign folders. The 39 CSV columns are numeric traffic features; there is no
label column and no verified device identifier. Folder names provide the
ground-truth attack type. Closely related attack types are mapped to eight
broad families so that the mitigation policy is understandable and each
class has enough data for calibration and evaluation.

The preparation code samples up to 60,000 rows per family with a deterministic
priority sampler and removes globally duplicated sampled rows. Three explicit
split protocols are then generated:

1. `stratified_rows` randomly stratifies rows by family. It is an optimistic
   reference because rows from one source file can appear in every split.
2. `attack_type_aware` keeps all 34 folder-level source labels in
   train, calibration, and test. It separates source files for the 17 labels
   having at least three files and uses deterministic ordered row blocks
   for the other 17. This is the primary proof-of-concept protocol.
3. `strict_family_file` holds out whole source files at family level. It is a
   hard distribution-shift stress test because a rare attack subtype may occur
   in only one split.

Cross-split duplicate feature vectors are checked after each split. The
attack-type-aware selected split contains 221,795 training, 78,133 calibration,
and 78,599 test rows.

The primary feature set removes `Number` and `Tot sum`. Inspection of the
official CSVs showed that these fields encode the aggregation-window size; for
example, different folders use characteristic values. A model could therefore
learn a collection shortcut rather than traffic behavior. The all-feature
result is retained only as an ablation.

## Detector and Confidence Routing

The primary model is a class-balanced Random Forest. It is fitted only on the
training split, then calibrated with sigmoid calibration on the separate
calibration split. The confidence threshold is selected on calibration data to
seek at least 95% accuracy among automatically planned cases while retaining at
least 25% coverage. Test labels never select the threshold. If no threshold
meets both targets, the code chooses the calibration point with the highest
selective accuracy and then the highest coverage.

"Automatic coverage" means only that the predicted family and confidence may
continue to the guardrailed planning stage. It does not mean an attack was
automatically blocked or any command was executed. Rows below the threshold
are forced to evidence collection and operator escalation.

The attack-type-aware and strict protocols are repeated across five fixed
split/model seeds while holding the prepared 378,527-row sample fixed. This
distinguishes a stable split observation from an unusually easy or difficult
split without changing the source sample at the same time. The
attack-type-aware protocol averaged macro-F1 0.731 and 96.2% accuracy on 54.0%
covered rows. The strict protocol averaged macro-F1 0.639 and was substantially
more variable.

A separate class-conditional experiment selects one threshold per predicted
family on calibration data. If a family cannot meet the target at the minimum
coverage, it fails closed to escalation. This tests whether a strong global
average hides an unsafe predicted family. Extra Trees and histogram gradient
boosting are evaluated under the same selected attack-type-aware split as
predeclared model-family sensitivity checks, not as a test-set model search.

An Extra Trees model uses the identical leakage-controlled features and splits
as an offline sanity baseline. A hierarchical detector first predicts
attack-versus-benign and then the attack family. Its small macro-F1 increase
(0.720 versus 0.715 on the selected attack-type-aware split) did not justify
replacing the simpler flat model.

## Fixed Agent Cases

The LLM experiment never receives the ground-truth label. It receives the
detector's predicted family, calibrated confidence, confidence threshold,
routing decision, an observed flow-profile scope, and selected numeric
features. Four test cases are selected for each true family:

1. two high-confidence correct predictions;
2. one low-confidence correct prediction; and
3. the highest-confidence error.

This produces 32 fixed cases. Nineteen are routed to planning, nine to
escalation, and four predicted-benign cases to monitoring. Low-confidence LLM
responses are evaluated so the guardrail behavior is visible; their operational
route remains evidence collection and escalation.

## Retrieval Corpus

The corpus contains seven documents downloaded from official publishers:

| Document | Role |
|---|---|
| NISTIR 8259A | IoT device cybersecurity capability baseline |
| NIST SP 800-213 | Federal IoT cybersecurity requirements guidance |
| NIST SP 800-213A | Detailed IoT device requirement catalog |
| NIST SP 800-61 Rev. 3 | Incident-response and continuous-monitoring guidance |
| ETSI EN 303 645 V3.1.3 | Consumer-IoT baseline security provisions |
| RFC 8520 | Manufacturer Usage Description and network access policy |
| RFC 8576 | Internet of Things security threats and mitigations |

PDF and text content is divided into 1,400-character chunks with 180-character
overlap. TF-IDF with unigrams and bigrams retrieves the top three chunks. Query
templates are based only on the predicted family and observed protocols. Each
saved excerpt is centered on matched query terms so the agent receives the
relevant part of a long ranked chunk rather than blindly receiving its first
characters.

Early development checks showed that generic phrases such as "incident
response" overweighted introductory passages. The final query templates were
therefore made threat-specific and the returned excerpts were centered on the
matched terms. The public package keeps the resulting fixed 32-alert reference
run in `experiments/runs/reference_evaluation/paired_rag_no_rag_32_alerts/`.
Superseded development runs are intentionally excluded so a reader cannot
mistake them for evidence used in the reported analysis.

## RAG Versus No RAG

Each fixed alert is evaluated once in each condition with randomized task
order. The model snapshot, compact JSON schema, action list, token limit, and
prompt are otherwise identical. `no_rag` receives an empty context and must
return an empty evidence list. `rag` receives three retrieved excerpts and is
asked to copy relevant chunk identifiers exactly.

The primary grounding endpoint is the rate of answers containing at least one
valid retrieved identifier. It is objective and does not count a fabricated or
malformed citation. Retrieval quality is separately audited on two cases per
predicted family, covering 16 cases and 48 chunks.

The first audit assigns `direct`, `supporting`, or `irrelevant`. A second
model-based auditor receives the excerpts and predicted family without the
first labels. The reference result reports exact three-way agreement,
Cohen's kappa, each auditor's counts, and the conservative count accepted by
both. This is explicitly described as a blinded model-based second audit. A
label-free CSV packet is also provided for independent human review.

## Guardrail Ablation

The LLM is intentionally asked for a compact mitigation proposal under
non-strict structured output. This lets the experiment observe malformed or
overlong proposals. Raw outputs are measured at three levels:

- valid JSON;
- valid compact proposal schema; and
- compatible actions for the predicted family.

The same raw object is also checked against the richer executor-facing schema.
It is expected to fail because fields such as canonical scope, bounded duration,
rollback, approval status, evidence references, and non-executed state belong
to deterministic normalization.

Normalization removes incompatible actions, canonicalizes action names,
replaces untrusted targets with the validated alert scope, bounds parameters
and duration, requires approval for disruptive actions, fixes evidence IDs,
and independently revalidates schema and policy. Low-confidence cases are
forced to traffic capture plus operator notification; benign cases are limited
to no-action plus monitoring.

## Statistical Checks

- The paired RAG/no-RAG grounding endpoint uses a two-sided exact binomial form
  of McNemar's test on discordant alert pairs.
- Raw-versus-normalized schema and policy endpoints use the same exact paired
  test on individual records.
- Detector performance reports accuracy, balanced accuracy, macro-F1,
  per-family precision/recall/F1, log loss, Brier score, and 15-bin expected
  calibration error.
- Confidence routing reports coverage, escalation rate, selective accuracy,
  and wrong automatic decisions.
- Detector stability reports mean, sample standard deviation, minimum, and
  maximum over five fixed seeds for the two leakage-aware protocols.
- Retrieval inter-rater analysis reports exact three-way agreement and
  three-way Cohen's kappa. Binary kappa is not interpreted when one auditor has
  no irrelevant labels because that statistic is then degenerate.

The second relevance audit is independent of the first labels but model-based.
The prepared blind packet lets an independent assessor add a human
audit without repeating retrieval or making another API call.

## Wrong-Family Retrieval and Action Faithfulness

The wrong-family control rotates the predicted-family retrieval query to a
different family while leaving the true detector alert, model, prompt, three
official chunks, output schema, and citation instruction unchanged. The agent
receives the condition label `rag`, so it is not told that it is in a control.
This isolates passage relevance from context length and identifier-copying.

A blinded action-to-evidence auditor receives the predicted family, one action,
its rationale, and only the excerpts cited by that response. It does not receive
the experimental condition. Labels are `directly_supported`,
`generally_supported`, and `unsupported`. Cases with every action supported are
also reported.

Because a global evidence list can be relevant to the family without
supporting every action, a deterministic post-normalization stage retrieves two
action-and-family-specific excerpts for each final bounded action. The same
blinded rubric evaluates this evidence binding. A label-free packet is saved
for independent human review.

## Detector Errors and Conservative Actions

The agent cases deliberately include one high-confidence detector error per
true family. An oracle analysis uses the hidden dataset label only to determine
whether the resulting action set would be compatible with the real family. The
deployable conservative policy never sees this label: it restricts final
actions to the intersection of the detector's two most probable families. If
there is no bounded shared action, it escalates.

Two outcomes are kept separate. Strict true-family compatibility asks whether
the plan suits the hidden attack label. Wrong-family disruption asks the
narrower safety question of whether a detector error caused a disruptive action
that the true-family policy would reject. Harmless monitoring can pass the
second test while remaining insufficient for the first.

## Guardrail Mutation Stress Test

Each of the 64 saved proposals is subjected to nine deterministic mutations:
overbroad targets, incompatible actions, extreme numeric parameters, fabricated
evidence, excessive actions, missing actions, non-object output,
low-confidence disruption, and benign disruption. This creates 576 proposals.
The experiment measures raw compact-schema and action-policy validity, followed
by full-schema, policy, and eight invariant checks after normalization.

The mutation test evaluates the declared enforcement contract. It does not
claim resistance to arbitrary software attacks or operational mitigation
effectiveness.
