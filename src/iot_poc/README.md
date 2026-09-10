# `iot_poc` Package Guide

The package is deliberately organized as small research stages. Each stage reads a frozen configuration, writes machine-readable artifacts, and can be rerun independently.

## Data And Detection

| Modules | Purpose |
|---|---|
| `dataset`, `split_protocols` | Read folder labels, clean numerical features, remove cross-split duplicates, and build evaluation splits |
| `detector`, `detector_protocols`, `detector_repeated_seeds` | Train, calibrate, and evaluate the primary detector |
| `detector_alternatives`, `detector_benchmark`, `hierarchical_detector` | Compare alternative detector designs |
| `alerts`, `alerts_protocol` | Build the fixed pilot planning cases |
| `journal_calibration`, `journal_detector_sensitivity` | Compare calibration methods and detector families across five seeds |
| `journal_family_routing`, `journal_cases` | Compare routing rules and select the fixed 160-alert journal sample |

## Retrieval And Planning

| Modules | Purpose |
|---|---|
| `retrieval` | Extract, chunk, index, and search the official standards corpus |
| `agent` | Make one bounded OpenAI Responses API request for compact mitigation intent |
| `experiment` | Run the paired pilot conditions with resumability and cost checks |
| `journal_agent` | Run relevant RAG, no RAG, and wrong-family RAG on the 160 fixed alerts |
| `journal_model_sensitivity`, `journal_model_compare` | Repeat and compare the stronger-model subset |
| `journal_policy_baseline` | Construct the deterministic no-LLM response baseline |

## Guardrails And Evidence

| Modules | Purpose |
|---|---|
| `schemas`, `guardrails`, `revalidate` | Normalize compact proposals and independently enforce the full schema and action policy |
| `guardrail_stress` | Apply nine mutation classes to 576 proposals |
| `error_propagation` | Study planning behavior when detector labels are wrong |
| `audit`, `audit_second`, `faithfulness_audit` | Evaluate retrieval relevance and action-level support in the pilot study |
| `action_evidence_binding` | Bind evidence separately to each pilot action |
| `journal_evidence_gate` | Retrieve and check evidence for every journal action |
| `journal_evidence_gate_refinement` | Select better-supported cautious fallbacks and rebuild final plans |

## Analysis And Provenance

| Modules | Purpose |
|---|---|
| `metrics`, `analysis` | Shared metrics and base result generation |
| `journal_statistics` | Confidence intervals and exact paired tests for the expanded run |
| `journal_human_audit`, `journal_human_audit_analysis` | Prepare blinded human-review files and compute agreement |
| `cost_estimator` | Estimate API use before a paid stage begins |
| `provenance`, `common` | Hashes, environment records, and shared JSON/JSONL helpers |

The package never calls a network executor. The only external service used by the experiments is the configured language-model API. Final intents remain `PROPOSED_NOT_EXECUTED`.
