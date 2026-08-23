import numpy as np

from iot_poc.error_propagation import conservative_normalize
from iot_poc.family_routing import choose_family_thresholds
from iot_poc.schemas import DISRUPTIVE_ACTIONS


def test_family_threshold_fails_closed_when_target_is_unreachable() -> None:
    classes = np.asarray(["A", "B"])
    probabilities = np.asarray(
        [[0.8, 0.2], [0.9, 0.1], [0.2, 0.8], [0.1, 0.9]]
    )
    predictions = classes[np.argmax(probabilities, axis=1)]
    true = np.asarray(["A", "B", "B", "A"])

    thresholds, audit = choose_family_thresholds(
        true,
        predictions,
        probabilities,
        classes,
        target_accuracy=0.95,
        minimum_coverage=0.25,
    )

    assert thresholds == {"A": 1.01, "B": 1.01}
    assert all(item["status"].startswith("fail_closed") for item in audit.values())


def test_top_two_policy_removes_wrong_family_disruption() -> None:
    alert = {
        "alert_id": "iot-top-two",
        "detector": {
            "predicted_family": "Spoofing",
            "calibrated_confidence": 0.9,
        },
        "routing_decision": "plan",
        "gateway_scope": "gateway/observed-flow-profile/iot-top-two",
    }
    raw = {
        "recommended_actions": [
            {
                "action": "RESTRICT_EGRESS",
                "target": "gateway/all-devices",
                "parameters": {},
                "rationale": "Potentially disruptive wrong-family action.",
            }
        ],
        "evidence_used": [],
    }

    normalized = conservative_normalize(
        raw, alert, [], candidate_families=["Spoofing", "Benign"]
    )

    assert normalized["status"] == "PROPOSED_NOT_EXECUTED"
    assert all(
        action["action"] not in DISRUPTIVE_ACTIONS
        for action in normalized["actions"]
    )
