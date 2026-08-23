from iot_poc.guardrails import expected_route, full_policy_conformance, normalize_intent
from iot_poc.schemas import FULL_INTENT_SCHEMA, validate


def alert(
    family: str = "Mirai", route: str = "plan", confidence: float = 0.93
) -> dict:
    return {
        "alert_id": "iot-test",
        "detector": {
            "predicted_family": family,
            "calibrated_confidence": confidence,
            "confidence_threshold": 0.85,
        },
        "routing_decision": route,
        "gateway_scope": "gateway/observed-flow-profile/iot-test",
    }


def test_normalization_removes_incompatible_action_and_uses_bounded_default() -> None:
    raw = {
        "recommended_actions": [
            {
                "action": "REQUIRE_REAUTHENTICATION",
                "target": "all devices",
                "parameters": {},
                "rationale": "Overbroad proposal.",
            }
        ],
        "evidence_used": ["made-up-reference"],
    }
    evidence = [{"chunk_id": "nist-0001"}]
    normalized = normalize_intent(raw, alert(), evidence)

    schema_valid, _ = validate(normalized, FULL_INTENT_SCHEMA)
    policy_valid, _ = full_policy_conformance(normalized, alert(), ["nist-0001"])
    assert schema_valid
    assert policy_valid
    assert normalized["status"] == "PROPOSED_NOT_EXECUTED"
    assert all(action["target"] == alert()["gateway_scope"] for action in normalized["actions"])
    assert all(action["action"] != "REQUIRE_REAUTHENTICATION" for action in normalized["actions"])
    assert all(action["evidence_refs"] == ["nist-0001"] for action in normalized["actions"])


def test_low_confidence_route_forces_collection_and_escalation() -> None:
    low_confidence_alert = alert(family="DDoS", route="escalate", confidence=0.2)
    normalized = normalize_intent(
        {"recommended_actions": [{"action": "BLOCK_TRAFFIC_PROFILE"}]},
        low_confidence_alert,
        [],
    )
    assert [action["action"] for action in normalized["actions"]] == [
        "CAPTURE_TRAFFIC",
        "NOTIFY_OPERATOR",
    ]
    assert normalized["route"] == "escalate"


def test_rate_limit_is_bounded_and_requires_approval() -> None:
    ddos_alert = alert(family="DDoS", route="plan")
    normalized = normalize_intent(
        {
            "recommended_actions": [
                {
                    "action": "RATE_LIMIT",
                    "parameters": {"traffic_fraction": "not-a-number"},
                    "rationale": "Bound traffic while the alert is reviewed.",
                }
            ]
        },
        ddos_alert,
        [],
    )
    action = normalized["actions"][0]
    assert action["parameters"] == {"traffic_fraction": 0.5}
    assert action["approval_required"] is True


def test_benign_route_cannot_become_disruptive() -> None:
    benign_alert = alert(family="Benign", route="monitor")
    normalized = normalize_intent(
        {"recommended_actions": [{"action": "ISOLATE_SEGMENT"}]},
        benign_alert,
        [],
    )
    assert [action["action"] for action in normalized["actions"]] == [
        "NO_ACTION",
        "MONITOR",
    ]


def test_inconsistent_monitor_route_is_recomputed_from_detector_fields() -> None:
    inconsistent_alert = alert(family="DDoS", route="monitor", confidence=0.92)
    normalized = normalize_intent(
        {
            "recommended_actions": [
                {
                    "action": "RATE_LIMIT",
                    "target": "gateway/all-devices",
                    "parameters": {"traffic_fraction": 0.7},
                    "rationale": "Synthetic route-consistency test.",
                }
            ],
            "evidence_used": [],
        },
        inconsistent_alert,
        [],
    )

    assert expected_route(inconsistent_alert) == "plan"
    assert normalized["route"] == "plan"
    policy_valid, errors = full_policy_conformance(normalized, inconsistent_alert, [])
    assert policy_valid, errors
    assert any(
        "Corrected inconsistent route" in note
        for note in normalized["guardrail"]["normalization_notes"]
    )
