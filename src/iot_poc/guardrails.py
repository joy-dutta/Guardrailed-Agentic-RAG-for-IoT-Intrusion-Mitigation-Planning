from __future__ import annotations

import math
import re
from typing import Any

from .schemas import ACTION_COMPATIBILITY, DISRUPTIVE_ACTIONS, FULL_INTENT_SCHEMA, validate


DEFAULT_ACTIONS = {
    "Benign": ["NO_ACTION", "MONITOR"],
    "DDoS": ["RATE_LIMIT", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"],
    "DoS": ["RATE_LIMIT", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"],
    "Recon": ["INCREASE_LOGGING", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"],
    "Web": ["RATE_LIMIT", "INCREASE_LOGGING", "NOTIFY_OPERATOR"],
    "BruteForce": ["RATE_LIMIT", "REQUIRE_REAUTHENTICATION", "NOTIFY_OPERATOR"],
    "Spoofing": ["RESTRICT_EGRESS", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"],
    "Mirai": ["RESTRICT_EGRESS", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"],
}


def expected_route(alert: dict[str, Any]) -> str:
    detector = alert["detector"]
    confidence = float(detector["calibrated_confidence"])
    threshold = float(detector.get("confidence_threshold", 0.85))
    if confidence < threshold:
        return "escalate"
    if detector["predicted_family"] == "Benign":
        return "monitor"
    return "plan"


def canonical_action(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").upper()
    aliases = {
        "BLOCK": "BLOCK_TRAFFIC_PROFILE",
        "BLOCK_FLOW": "BLOCK_TRAFFIC_PROFILE",
        "QUARANTINE": "ISOLATE_SEGMENT",
        "ISOLATE": "ISOLATE_SEGMENT",
        "LOG": "INCREASE_LOGGING",
        "CAPTURE": "CAPTURE_TRAFFIC",
        "ALERT": "NOTIFY_OPERATOR",
    }
    return aliases.get(text, text)


def raw_policy_conformance(raw: Any, predicted_family: str) -> tuple[bool, list[str]]:
    if not isinstance(raw, dict):
        return False, ["Raw output is not a JSON object."]
    actions = raw.get("recommended_actions")
    if not isinstance(actions, list) or not actions:
        return False, ["No recommended actions were supplied."]
    allowed = ACTION_COMPATIBILITY[predicted_family]
    problems = []
    for item in actions:
        action = canonical_action(item.get("action") if isinstance(item, dict) else item)
        if action not in allowed:
            problems.append(f"{action or 'EMPTY'} is not allowed for {predicted_family}.")
    return not problems, problems


def bounded_parameters(action: str, supplied: Any) -> dict[str, Any]:
    values = supplied if isinstance(supplied, dict) else {}
    if action == "RATE_LIMIT":
        try:
            ratio = float(values.get("traffic_fraction", values.get("rate_fraction", 0.5)))
        except (TypeError, ValueError):
            ratio = 0.5
        if not math.isfinite(ratio):
            ratio = 0.5
        return {"traffic_fraction": min(0.8, max(0.1, ratio))}
    if action == "CAPTURE_TRAFFIC":
        try:
            seconds = int(values.get("capture_seconds", 120))
        except (TypeError, ValueError):
            seconds = 120
        return {"capture_seconds": min(300, max(30, seconds))}
    if action == "INCREASE_LOGGING":
        return {"level": "enhanced", "include_payload": False}
    if action == "BLOCK_TRAFFIC_PROFILE":
        return {"match": "validated_observed_profile_only"}
    if action == "RESTRICT_EGRESS":
        return {"mode": "deny_unapproved_destinations"}
    if action == "ISOLATE_SEGMENT":
        return {"mode": "candidate_segment_isolation"}
    if action == "REQUIRE_REAUTHENTICATION":
        return {"mode": "gateway_reauthentication"}
    if action == "MONITOR":
        return {"level": "enhanced"}
    if action == "NOTIFY_OPERATOR":
        return {"priority": "high"}
    return {}


def normalize_intent(
    raw: Any,
    alert: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    predicted = alert["detector"]["predicted_family"]
    confidence = float(alert["detector"]["calibrated_confidence"])
    supplied_route = alert["routing_decision"]
    route = expected_route(alert)
    scope = alert["gateway_scope"]
    available_evidence = [item["chunk_id"] for item in evidence]
    notes: list[str] = []
    if supplied_route != route:
        notes.append(
            f"Corrected inconsistent route {supplied_route} to {route} from detector confidence and category."
        )

    raw_actions = raw.get("recommended_actions", []) if isinstance(raw, dict) else []
    candidates = []
    for item in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(item, dict):
            continue
        action = canonical_action(item.get("action"))
        if action not in ACTION_COMPATIBILITY[predicted]:
            notes.append(f"Removed policy-incompatible action {action or 'EMPTY'}.")
            continue
        candidates.append((action, item))

    if route == "escalate":
        candidates = [
            ("CAPTURE_TRAFFIC", {"rationale": "Collect additional evidence before a disruptive decision."}),
            ("NOTIFY_OPERATOR", {"rationale": "Detector confidence is below the validated threshold."}),
        ]
        notes.append("Low-confidence routing replaced autonomous planning with evidence collection and escalation.")
    elif predicted == "Benign":
        candidates = [
            ("NO_ACTION", {"rationale": "The detector classified the observation as benign."}),
            ("MONITOR", {"rationale": "Continue non-disruptive observation."}),
        ]
        notes.append("Benign routing restricted the intent to no-action and monitoring.")
    elif not candidates:
        candidates = [
            (action, {"rationale": "Applied the predefined bounded policy default."})
            for action in DEFAULT_ACTIONS[predicted]
        ]
        notes.append("Applied predefined bounded defaults because no compatible raw action remained.")

    raw_evidence = raw.get("evidence_used", []) if isinstance(raw, dict) else []
    if not isinstance(raw_evidence, list):
        raw_evidence = []
        notes.append("Ignored a non-list evidence field from the raw proposal.")
    valid_raw_evidence = [ref for ref in raw_evidence if ref in available_evidence]
    evidence_refs = valid_raw_evidence or available_evidence[:2]
    if raw_evidence and len(valid_raw_evidence) != len(raw_evidence):
        notes.append("Removed evidence identifiers that were not present in retrieval results.")

    actions = []
    for action, item in candidates[:3]:
        duration = 0 if action in {"NO_ACTION", "NOTIFY_OPERATOR"} else 900
        approval_required = action in DISRUPTIVE_ACTIONS
        actions.append(
            {
                "action": action,
                "target": scope,
                "parameters": bounded_parameters(action, item.get("parameters", {})),
                "duration_seconds": duration,
                "rollback": "Expire the temporary gateway policy and restore the previous validated configuration.",
                "approval_required": approval_required,
                "evidence_refs": evidence_refs,
                "rationale": str(item.get("rationale") or "Bounded response to the detector alert.")[:500],
            }
        )

    intent = {
        "schema": "iot.mitigation.intent.v1",
        "intent_id": f"intent-{alert['alert_id']}",
        "alert_ref": alert["alert_id"],
        "route": route,
        "predicted_threat": predicted,
        "confidence": confidence,
        "scope": scope,
        "actions": actions,
        "status": "PROPOSED_NOT_EXECUTED",
        "guardrail": {
            "schema_validated": True,
            "policy_validated": True,
            "normalization_notes": notes,
        },
    }
    schema_valid, errors = validate(intent, FULL_INTENT_SCHEMA)
    intent["guardrail"]["schema_validated"] = schema_valid
    if errors:
        intent["guardrail"]["normalization_notes"].extend(errors)
    policy_valid, policy_errors = full_policy_conformance(intent, alert, available_evidence)
    intent["guardrail"]["policy_validated"] = policy_valid
    if policy_errors:
        intent["guardrail"]["normalization_notes"].extend(policy_errors)
    return intent


def full_policy_conformance(
    intent: Any,
    alert: dict[str, Any],
    available_evidence: list[str],
) -> tuple[bool, list[str]]:
    if not isinstance(intent, dict):
        return False, ["Intent is not an object."]
    predicted = alert["detector"]["predicted_family"]
    allowed = ACTION_COMPATIBILITY[predicted]
    problems = []
    route = intent.get("route")
    required_route = expected_route(alert)
    if route != required_route:
        problems.append(
            f"The intent route {route} does not match the detector-derived route {required_route}."
        )
    if intent.get("scope") != alert["gateway_scope"]:
        problems.append("The target scope differs from the validated alert scope.")
    actions = intent.get("actions", [])
    if not isinstance(actions, list):
        return False, ["The actions field is not a list."]
    for item in actions:
        if not isinstance(item, dict):
            problems.append("An action entry is not an object.")
            continue
        action = item.get("action")
        if action not in allowed and route != "escalate":
            problems.append(f"{action} is incompatible with {predicted}.")
        if route in {"monitor", "escalate"} and action in DISRUPTIVE_ACTIONS:
            problems.append(f"{action} is disruptive but the route is {route}.")
        if action in DISRUPTIVE_ACTIONS and not item.get("approval_required"):
            problems.append(f"{action} requires explicit approval.")
        if not 0 <= int(item.get("duration_seconds", -1)) <= 3600:
            problems.append(f"{action} has an out-of-range duration.")
        if any(ref not in available_evidence for ref in item.get("evidence_refs", [])):
            problems.append(f"{action} cites unavailable evidence.")
    return not problems, problems
