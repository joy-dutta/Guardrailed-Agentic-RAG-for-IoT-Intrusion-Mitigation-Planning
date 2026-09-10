# Journal Experiment Protocol

This document records the completed larger experiment in the order needed to reproduce it.

## 1. Prepare The Dataset

The official CICIoT2023 CSV archive is verified by size and SHA-256 before extraction. Folder names provide the attack type. Thirty attack types are grouped into eight operational traffic families: Benign, BruteForce, DDoS, DoS, Mirai, Recon, Spoofing, and Web.

Infinite values are converted to missing values and median-imputed from training data. `Number` and `Tot sum` are removed from the primary feature set because they can reveal aggregation-window behavior. Duplicate control and source provenance are recorded before model fitting.

## 2. Build Leakage-Aware Splits

The main protocol keeps source files separate whenever an attack type has enough files. Smaller attack types use deterministic ordered row blocks. Random-row and stricter whole-file controls are also retained so readers can see how the evaluation assumption affects performance.

Training, calibration, threshold selection, and final test evaluation remain logically separate. Final test labels are never used to fit a confidence mapping or select a threshold.

## 3. Train And Calibrate The Detector

The primary Random Forest predicts one of eight traffic families. Raw confidence, sigmoid calibration, and isotonic calibration are compared across five fixed seeds using expected calibration error, multiclass Brier score, negative log-likelihood, and risk-coverage behavior.

Random Forest, histogram gradient boosting, and Extra Trees are then compared using the same split logic. This tests whether confidence-routing behavior depends on one detector design.

## 4. Route Confidence

The global rule chooses one threshold using the validation partition. A row continues to normal planning only when its calibrated confidence meets the selected threshold. Other rows are routed toward evidence collection and review.

The family-aware rule selects a separate threshold for each predicted family using validation data only. A family that cannot meet the validation requirement fails closed. The experiment reports planning coverage, accuracy among retained rows, and the number of wrong retained decisions.

## 5. Select The 160 Planning Alerts

Twenty alerts are selected from each true family. The sample deliberately includes detector-correct, detector-error, confidence-qualified, and escalated cases. Seventy-five alerts are detector errors and eighty fall below the selected threshold.

This is an uncertainty stress sample. It is not intended to reproduce the natural frequency of CICIoT2023 attacks.

The planner receives only the `alert` object. The true family, source file, source row, correctness flag, and selection stratum remain under `evaluation` for later analysis.

## 6. Run Three Planning Conditions

Every alert is sent through three conditions with GPT-5.4 mini:

| Condition | Planner context | Research purpose |
|---|---|---|
| Relevant RAG | Top three chunks retrieved for the detector-predicted family | Test source traceability |
| No RAG | Empty evidence context | Provide a paired retrieval baseline |
| Wrong-family RAG | Top three chunks retrieved for a deliberately different family | Test whether the planner copies valid identifiers from any context |

The wrong-family mapping is deterministic:

```text
Benign -> BruteForce -> DDoS -> DoS -> Mirai -> Recon -> Spoofing -> Web -> Benign
```

The mapping starts from the detector prediction, not the hidden true label. This preserves the same alert and prompt while changing only the retrieval family.

## 7. Normalize And Validate Every Proposal

The model produces compact mitigation intent. Deterministic normalization supplies executor-facing fields, canonical action names, validated scope, bounded parameters, approval, rollback, evidence references, and `PROPOSED_NOT_EXECUTED` status.

The full schema and action policy are then checked independently. Raw and normalized validity are both reported so construction-by-design is visible rather than mistaken for model accuracy.

## 8. Compare Baselines And Models

A policy-only baseline creates a deterministic plan from the same routing and family policy without an LLM. It shows when the agent contributes bounded case-specific variation.

A prespecified 32-alert subset is repeated with GPT-5.4 under all three retrieval conditions. This checks whether the main findings persist with a stronger and more expensive planning model.

## 9. Apply The Relevant-RAG Evidence Gate

The 160 relevant-RAG plans contain 375 proposed actions. Every action receives a fresh query containing the predicted family, action name, active protocols, and important observations.

The gate checks that cited identifiers came from this action-specific retrieval and that the action is permitted for the predicted family. GPT-5.4 mini labels evidence as direct, general, or unsupported. The strict gate retains direct support, accepts general support only for non-disruptive actions, and removes unsupported actions.

If a plan becomes empty, action-weighted retrieval compares cautious candidates such as `CAPTURE_TRAFFIC`, `MONITOR`, and `NOTIFY_OPERATOR`. A separate GPT-5.4 evaluator scores the before and after actions without seeing the gate decision.

## 10. Apply The Wrong-Family Recovery Gate

The same gate is applied to the 376 actions produced after wrong-family retrieval. This stage performs fresh action-level retrieval, so its output no longer depends on accepting the original wrong-family passages.

The experiment records citation rebinding, removed actions, fallbacks, final support labels, and disruptive actions. This is a recovery and failure-containment test.

## 11. Independent Model Reviews

ChatGPT using GPT-5.6 Sol Ultra and Gemini using Gemini Pro Extended independently review blinded records. Each sees 192 plan candidates and 128 evidence items without condition names. Plan scores cover appropriateness, conservativeness, usefulness, and possible incompatibility. Evidence labels distinguish direct, general, and unsupported material.

The condition key is reopened only during analysis. Agreement and condition comparisons are stored with the completed judgments. These reviews provide model-based triangulation and remain separate from the optional human-review packets.

## 12. Statistical Analysis

The analysis uses Wilson intervals for proportions, exact McNemar tests for paired binary outcomes, Wilcoxon tests for paired ordinal comparisons, Friedman tests for three-condition ordinal comparisons, and agreement statistics appropriate to categorical or ordinal labels.

Every reported denominator remains explicit. In particular, evidence-gate support percentages use the final retained action count, not the original proposed action count.

## 13. Cost And Resume Controls

Each paid stage checks a call ceiling and estimated-cost ceiling before starting. One successful response is saved at a time. A repeated command resumes completed case-condition pairs rather than paying for them again.

Transport failures are retained for provenance but excluded from successful-output and billed-usage denominators when no response was produced.

## 14. Reproduction Order

```bash
python scripts/reproduce.py bootstrap
python scripts/reproduce.py offline
python scripts/reproduce.py journal-offline
python scripts/reproduce.py journal-agent
python scripts/reproduce.py model-sensitivity
python scripts/reproduce.py evidence-gate
python scripts/reproduce.py mismatched-evidence-gate
python scripts/reproduce.py model-audit
python scripts/reproduce.py journal-reports
python scripts/reproduce.py verify
```

The saved runs allow no-cost inspection and report reconstruction. Fresh model generation requires a locally supplied `OPENAI_API_KEY` and acceptance of each displayed stage limit.
