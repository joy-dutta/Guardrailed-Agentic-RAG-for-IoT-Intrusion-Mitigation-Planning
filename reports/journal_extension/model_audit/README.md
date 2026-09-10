# Independent Model Reviews

This folder preserves two independent, blinded reviews of the planning and action-evidence records.

| Reviewer | Model | Plan rows | Evidence rows |
|---|---|---:|---:|
| Reviewer A | ChatGPT using GPT-5.6 Sol Ultra | 192 | 128 |
| Reviewer B | Gemini using Gemini Pro Extended | 192 | 128 |

The models did not see the experimental condition names while scoring. Plan candidates came from relevant RAG, no RAG, and the deterministic policy baseline. Evidence items came from relevant and deliberately mismatched retrieval.

## Files

| File | Meaning |
|---|---|
| `chatgpt_A_plan_completed.csv` | Reviewer A plan scores and notes |
| `chatgpt_A_evidence_completed.csv` | Reviewer A evidence labels and notes |
| `gemini_B_plan_judgments_final.csv` | Reviewer B plan judgments in blind-packet order |
| `gemini_B_evidence_judgments_final.csv` | Reviewer B evidence judgments in blind-packet order |
| `plan_condition_summary.csv` | Scores summarized after reopening the condition key |
| `evidence_condition_summary.csv` | Evidence labels summarized by condition |
| `inter_model_agreement.json` | Exact agreement, weighted kappa, and related diagnostics |
| `condition_analysis.json` | Statistical comparison of the experimental conditions |
| `MODEL_AUDIT_INTERPRETATION.md` | Plain-language interpretation and claim boundary |

Run the analysis with:

```bash
python scripts/reproduce.py model-audit
```

The two reviews are useful because they provide separate readings of the same blinded records. Both generally viewed the final plans as useful and cautious. Their differences in scoring strictness help identify where human expertise would add the most value.

These files are model-based supplementary evidence. They are not labelled as human review, and they are not used to claim that every action is operationally correct.
