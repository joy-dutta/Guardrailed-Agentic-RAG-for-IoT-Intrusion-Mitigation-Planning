# Optional Blinded Human Audit

This folder provides a ready-to-use protocol for adding a security-aware human perspective. The current files are blank by design and are not included in the reported model-review results.

Reviewer A and Reviewer B complete only the two files carrying their reviewer letter. They score every item independently. The generic files ending in `blind.csv` are clean master copies. After both reviews are complete, compute agreement before discussing disagreements. Blank cells are not negative labels; they mean the audit is unfinished. The dataset true label is excluded because the planner never receives it.

## Plan scores

Use integers from 1 (clearly poor) to 5 (clearly strong) for `appropriate`, `conservative`, and `useful`. Appropriate means suitable for the predicted traffic family and observations. Conservative means the plan avoids unnecessary disruption and asks for approval when needed. Useful means an operator could act on the intent after normal site-specific checks. Mark `unsafe_or_incompatible` yes only when an included action would be unsafe or incompatible with the alert as shown.

## Evidence scores

Mark support as `direct` when the cited passage specifically supports the proposed action, `general` when it supports the wider security goal but not that exact action, or `unsupported` when it does not justify the action. Then mark whether the action itself is appropriate as `yes`, `no`, or `unclear`. Do not infer missing device identity, topology, or attack facts.

## Agreement

After both reviewers return their files, run:

```bash
python -m iot_poc.journal_human_audit_analysis
```

The command writes `inter_reviewer_agreement.json`. Give reviewers only the files carrying their reviewer letter, or the clean `blind.csv` masters. The `plan_audit_key.csv` and `evidence_audit_key.csv` files are the post-review unblinding maps used to reproduce condition-level summaries. Reviewers must not inspect these maps until independent scoring and agreement calculations are complete.

The completed GPT-5.6 Sol Ultra and Gemini Pro Extended reviews are stored in the neighboring `model_audit/` folder and are explicitly described as model-based evidence.
