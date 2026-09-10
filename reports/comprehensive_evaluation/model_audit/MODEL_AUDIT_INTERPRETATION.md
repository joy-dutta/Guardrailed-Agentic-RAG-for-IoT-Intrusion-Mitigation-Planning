# Independent Model-Audit Interpretation

## What was reviewed

Two language models independently reviewed blinded experiment records:

- Reviewer A: ChatGPT using GPT-5.6 Sol Ultra.
- Reviewer B: Gemini using Gemini Pro Extended.

Each model saw 192 mitigation plans: 64 RAG plans, 64 no-RAG plans, and 64 deterministic policy-only plans. The models did not see these condition names while scoring. They rated whether each plan was appropriate, conservative, useful, and potentially unsafe.

They also reviewed 128 action-evidence records: 64 using retrieved evidence from the intended standards query and 64 using deliberately mismatched retrieval. These were independently sampled items, not 64 matched pairs. The models judged whether a passage directly supported an action, was only generally related, or was unsupported. They separately judged whether the action itself was reasonable.

This is a model-based audit. It is not human validation.

## Plain-Language Result

Both models viewed most generated plans positively. In physical terms, an operator would usually receive a bounded and understandable next step, such as monitoring, collecting traffic, increasing logging, notifying an operator, or considering an approval-gated response. The similar RAG and no-RAG plan scores help define the retrieval contribution precisely: retrieval connects a plan to external security guidance, while the guardrails shape its safety and structure.

The policy-only baseline exposed a practical weakness of fixed response rules. Reviewer A flagged four policy-only plans as potentially unsafe or incompatible. Two involved a 50% rate limit that was too aggressive for the observed low-rate traffic. Gemini also gave those same two plans its lowest appropriateness and conservativeness scores. This is a useful result: fixed rules can select a technically allowed action without considering enough case detail.

## Plan-quality findings

Reviewer A scored RAG and no-RAG plans almost identically and rated both as highly useful. It rated policy-only plans lower for usefulness. The RAG-versus-policy-only usefulness difference was statistically significant after Holm correction, but the same advantage appeared for no RAG. The result therefore reflects the value of context-sensitive language-model planning over the fixed baseline, not a unique RAG benefit.

Reviewer B also rated most plans as strong. It found RAG plans more conservative than policy-only plans, but found no statistically reliable RAG-versus-no-RAG difference in appropriateness, conservativeness, or usefulness. Across both reviews, the safe conclusion is that the guardrailed planning pipeline usually creates reasonable mitigation intent, while policy-only responses can be less sensitive to the specific alert.

## Evidence-grounding findings

Reviewer A found a strong retrieval effect. None of the 64 intended-RAG evidence items was unsupported, compared with 28 of 64 mismatched-retrieval items. Reviewer B used a stricter and more uniform interpretation: it marked four intended-RAG and six mismatched items unsupported, which was not a statistically reliable difference by itself.

Despite this difference in strictness, every item that both reviewers marked unsupported came from the mismatched-retrieval condition: six mismatched items and no intended-RAG items. At least one reviewer marked evidence unsupported for 28 mismatched items, compared with four intended-RAG items. These cross-reviewer comparisons are exploratory, but their direction is consistent with the claim that retrieving the right standards material reduces clearly irrelevant evidence.

Most passages were judged generally related rather than directly supportive. Reviewer A used `direct` only three times, and Reviewer B did not use it. The paper should therefore describe the output as standards-informed or standards-grounded mitigation planning with evidence traceability. It should not say that a retrieved passage formally authorizes or proves the operational suitability of each action.

## Reviewer agreement

For plan ratings, the models agreed within one point for 99.0% of appropriateness judgments, 83.3% of conservativeness judgments, and 99.0% of usefulness judgments. Exact agreement was lower because Reviewer A used the maximum score much more often. Quadratic weighted kappa ranged from 0.096 to 0.287, showing that the models differed substantially in rating strictness.

Unsafe-plan labels agreed in 97.9% of rows, but this number is inflated by the rarity of unsafe labels. Reviewer A identified four concerns and Reviewer B marked every row `no`, producing a kappa of zero. Evidence-support agreement was 77.3% with kappa 0.203. Action-appropriateness agreement was 86.7%, but kappa was zero because Reviewer A labelled every action appropriate.

The agreement results should not be presented as strong inter-rater reliability. They show broad agreement that the plans are useful, alongside meaningful disagreement about grading strictness and evidence specificity.

## How To Use The Model Reviews

Reviewer B supplied complete labels and used a compact set of repeated notes. Reviewer A left many optional plan notes blank while providing more varied evidence notes. The numerical labels remain complete, and these note patterns are reported so readers can judge the depth and style of each review.

The two model audits provide useful supplementary triangulation. A security-aware human review of a blinded subset would add practical expertise, and two human reviewers would allow a separate inter-rater agreement analysis.

## Safe paper takeaway

The two model-based audits suggest that the guardrailed pipeline usually produces useful, bounded mitigation intent and avoids some overly broad fixed-policy responses. Matched standards retrieval appears to reduce clearly irrelevant evidence, but it does not measurably improve plan quality over no RAG and does not guarantee direct action-level support.

## Responsible Claim Boundary

- Describe these files as independent model-based reviews.
- Use RAG results to support traceability and evidence access rather than a general plan-quality advantage.
- Distinguish direct, general, and unsupported evidence.
- Report agreement together with the reviewers' different scoring patterns.
- Keep operational claims within the offline mitigation-planning setting.
