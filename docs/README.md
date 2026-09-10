# Documentation Map

This folder explains the experiment without requiring readers to reverse
engineer the Python modules.

| Document | Question it answers |
|---|---|
| [`dataset/DATA_CARD.md`](dataset/DATA_CARD.md) | What data was used, and how were labels and splits constructed? |
| [`experiment_protocol/EXPERIMENT_DESIGN.md`](experiment_protocol/EXPERIMENT_DESIGN.md) | What research questions and controls were evaluated? |
| [`experiment_protocol/JOURNAL_EXPERIMENT_PROTOCOL.md`](experiment_protocol/JOURNAL_EXPERIMENT_PROTOCOL.md) | How was the completed 160-alert extension run from calibration through evidence gating? |
| [`method/PIPELINE.md`](method/PIPELINE.md) | How does one alert move from detection to bounded intent? |
| [`standards/README.md`](standards/README.md) | Which official documents were retrieved, and why? |
| [`results/RESULTS_IN_PLAIN_LANGUAGE.md`](results/RESULTS_IN_PLAIN_LANGUAGE.md) | What do the results mean in a real IoT gateway? |
| [`results/CLAIMS_AND_LIMITATIONS.md`](results/CLAIMS_AND_LIMITATIONS.md) | What can and cannot be claimed? |
| [`results/RESULT_TO_ARTIFACT_MAP.md`](results/RESULT_TO_ARTIFACT_MAP.md) | Which file supports each reported result? |
| [`technical/REPRODUCIBILITY_GUIDE.md`](technical/REPRODUCIBILITY_GUIDE.md) | How can another researcher reproduce the complete experiment? |
| [`legal/THIRD_PARTY_NOTICES.md`](legal/THIRD_PARTY_NOTICES.md) | Which dataset, standards, and package terms remain with their publishers? |

The standards provide grounding evidence. The deterministic schemas, action
matrix, normalization, parameter bounds, and approval rules provide the
guardrails. Keeping those roles separate is important when interpreting the
results. The expanded evaluation is indexed under `reports/comprehensive_evaluation/`, including the two completed model reviews and the relevant and wrong-family evidence gates.
