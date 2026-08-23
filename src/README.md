# Source Modules

- `dataset.py`: folder labels, streaming sample, split assignment, cleaning, duplicate control
- `detector.py`: Random Forest training, calibration, metrics, and predictions
- `detector_benchmark.py`: fixed-split Extra Trees sanity baseline
- `split_protocols.py`: explicit row, attack-type-aware, and strict stress-test splits
- `detector_protocols.py`: detector comparison under all three split questions
- `hierarchical_detector.py`: attack-versus-benign stage followed by attack-family classification
- `detector_repeated_seeds.py`: five-seed stability check for primary and stress-test splits
- `family_routing.py`: fail-closed predicted-family-specific threshold experiment
- `detector_alternatives.py`: Extra Trees and histogram-gradient-boosting sensitivity check
- `alerts.py`: balanced selection of fixed detector alerts
- `alerts_protocol.py`: attack-type-aware detector alerts for the final strengthened run
- `retrieval.py`: PDF/DOCX/text extraction, chunking, and TF-IDF retrieval
- `agent.py`: bounded OpenAI Responses API call and compact JSON schema
- `schemas.py`: compact and executor-facing JSON schemas plus action policy
- `guardrails.py`: deterministic normalization and independent policy validation
- `experiment.py`: paired RAG/no-RAG orchestration, resume logic, and cost caps
- `audit.py`: applies the visible manual retrieval judgments
- `audit_second.py`: blinded model-based second audit and inter-rater agreement
- `analysis.py`: statistical checks, result tables, and claim assessment
- `revalidate.py`: reapplies updated deterministic policy to saved raw outputs without new API calls
- `error_propagation.py`: true-family oracle analysis and deployable top-two conservative actions
- `guardrail_stress.py`: 576 deterministic malformed and unsafe proposal mutations
- `shuffled_control.py`: blinded wrong-family official-retrieval control with combined cost caps
- `faithfulness_audit.py`: blinded action-to-cited-evidence support audit
- `action_evidence_binding.py`: action-specific post-guardrail retrieval and audit
- `provenance.py`: input hashes, environment lock, and platform record

The LLM cannot execute a command. Only the deterministic code constructs the
executor-facing intent, and its status remains `PROPOSED_NOT_EXECUTED`.
