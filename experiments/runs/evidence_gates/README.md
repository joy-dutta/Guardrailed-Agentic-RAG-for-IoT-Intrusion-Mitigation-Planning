# Evidence-Gate Runs

These two experiments test the action-level evidence gate on the same 160 alerts used in the main planning study.

| Folder | Starting condition | Original actions | Final actions |
|---|---|---:|---:|
| `relevant_rag_160_alerts/` | Retrieval matched to the predicted family | 375 | 212 |
| `wrong_family_recovery_160_alerts/` | Retrieval deliberately taken from a different family | 376 | 213 |

The gate performs fresh retrieval for every proposed action, checks action-policy compatibility, obtains an independent support judgment, removes weak actions, and uses a cautious fallback when necessary. These are support and failure-containment experiments, not measurements of live attack suppression.
