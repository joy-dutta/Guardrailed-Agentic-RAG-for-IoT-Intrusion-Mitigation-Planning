# Evidence-Support Gate: Result and Meaning

## Plain-language result

The evidence gate improved action-to-evidence support under the independent evaluator.

The comparison starts from 376 mitigation actions across 160 real planning cases. The gate checks each action against a fresh, action-specific retrieval result. It removes actions that are incompatible with the predicted attack family, unsupported by the cited passage, or too disruptive for only general evidence. If a case is left with no useful action, the system inserts a bounded monitoring, evidence-collection, or operator-notification fallback.

An independent model, which did not make the gate decisions, judged the actions before and after filtering. Its unsupported rate changed from 31.1% to 18.8%. Cases in which every final action had at least general support changed from 43.8% to 75.0%.

## What this means in practice

The gate turns a valid citation identifier into a checked relationship between one proposed action and the passage cited for it. This is stronger than merely showing that the citation exists. It is still not proof that the action is operationally correct. The detector may be wrong, the standards corpus or policy table may be incomplete, and disruptive actions still require human approval before execution.

## Paper-safe interpretation

Use the independent-evaluator result as the main evidence. The checker used inside the gate will naturally show fewer unsupported actions because the gate was built from its labels. That construction-by-design result is useful for implementation auditing, but it should not be presented as independent performance evidence.
