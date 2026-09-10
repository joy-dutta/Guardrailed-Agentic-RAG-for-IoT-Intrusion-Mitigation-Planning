# Action-to-Evidence Gate: Refined Result

## The result in one sentence

An action-specific evidence gate made the final mitigation plans more standards-grounded under a separate evaluator, while deliberately producing smaller and more conservative plans.

## What was tested

The experiment reused the 160 RAG alerts from the IEEE Access extension. Their guardrailed plans contained 375 actions. Each action received a new retrieval query containing the predicted attack family, the proposed action, active protocols, and important observed traffic features. A deterministic check first confirmed that the action was permitted by the existing family policy and that every cited identifier belonged to that action's retrieval result.

GPT-5.4 mini then labelled each action's passages as directly supported, generally supported, or unsupported. The strict gate kept direct support, kept general support only for non-disruptive actions, and removed unsupported actions. If no action remained, it used bounded traffic capture, monitoring, or operator notification according to the route. A second model, GPT-5.4, independently evaluated the original and final actions without seeing the first model's labels or gate decisions.

The first fallback retrieval sometimes found attack-family guidance instead of guidance for the fallback action. The refinement repeated the fallback action terms in the retrieval query, considered the safe fallback actions permitted by the route, and selected the candidate with the strongest support from the gate checker. Ties favored evidence collection, then monitoring, then operator notification.

## What changed

| Independent GPT-5.4 evaluation | Before gate | After refined strict gate |
|---|---:|---:|
| Actions judged direct or general support | 69.1% | 91.0% |
| Actions judged unsupported | 30.9% | 9.0% |
| Cases where every action had direct or general support | 46.9% | 88.1% |
| Disruptive actions | 32 | 3 |
| Unsupported disruptive actions | 2 | 0 |

The gate removed 195 original actions and inserted a bounded fallback in 32 cases, leaving 212 final actions. At the whole-plan level, 66 cases improved, none worsened, and the two-sided exact McNemar result was `p = 2.71e-20`. All 160 final plans remained valid under the declared schema and policy checks.

The all-actions-supported rate increased in each of the eight true traffic families and in both fixed 80-case halves. This subgroup check does not turn the iterative experiment into a held-out validation, but it shows that the aggregate gain was not produced by only one attack family or one part of the case list.

## Physical-world meaning

For a gateway operator, the change is simple: an action is no longer retained merely because it cites a real document identifier. The cited passage must also be useful for that particular action. When this link is weak, the prototype chooses a cautious evidence-collection or monitoring step instead of preserving a more aggressive proposal. The output still has status `PROPOSED_NOT_EXECUTED`; it does not configure a gateway or block a device.

## What the paper can safely claim

The experiment supports the claim that action-specific retrieval plus an external evidence gate can reduce action-evidence mismatch. Under the separate GPT-5.4 evaluator, the unsupported-action rate fell by 22.0% percentage points, a 71.0% relative reduction.

It does not support a claim of perfect grounding or autonomous correctness. Nineteen final actions were still judged unsupported by the second model, and agreement between the two model checkers was only moderate. Human review is still needed for a strong semantic-support claim, and any disruptive action still requires explicit approval before execution.

## Run integrity

The base gate and fallback refinement used 19 API calls at an estimated total cost of USD 1.209. The hard limits were 20 calls and USD 2.50. No API key is stored in the project.
