# Security and Responsible Use

This project is an offline research proof of concept. Its output is mitigation
intent with status `PROPOSED_NOT_EXECUTED`; no module should be connected
directly to a production gateway, firewall, device-management service, or cloud
control plane.

Before operational adaptation, independently implement and test authentication,
authorization, local policy translation, target verification, rate limits,
transactional rollback, service-impact monitoring, audit logging, and operator
approval. Treat the standards corpus, prompts, configuration, and model output
as untrusted inputs at every deployment boundary.

The evaluated trust model covers detector uncertainty, incorrect predicted
families, malformed LLM proposals, incompatible actions, excessive parameters,
fabricated evidence identifiers, and overbroad targets. It does not cover a
compromised standards corpus, prompt injection from operational telemetry,
incorrect local policy definitions, software supply-chain compromise, or a
faulty downstream executor.

Please report a suspected vulnerability privately to the repository owner
before opening a public issue containing exploit details.
