from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


ALLOWED_ACTIONS = [
    "NO_ACTION",
    "MONITOR",
    "RATE_LIMIT",
    "BLOCK_TRAFFIC_PROFILE",
    "RESTRICT_EGRESS",
    "ISOLATE_SEGMENT",
    "INCREASE_LOGGING",
    "CAPTURE_TRAFFIC",
    "REQUIRE_REAUTHENTICATION",
    "NOTIFY_OPERATOR",
]

ACTION_COMPATIBILITY = {
    "Benign": {"NO_ACTION", "MONITOR"},
    "DDoS": {"RATE_LIMIT", "BLOCK_TRAFFIC_PROFILE", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"},
    "DoS": {"RATE_LIMIT", "BLOCK_TRAFFIC_PROFILE", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"},
    "Recon": {"MONITOR", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "BLOCK_TRAFFIC_PROFILE", "NOTIFY_OPERATOR"},
    "Web": {"RATE_LIMIT", "BLOCK_TRAFFIC_PROFILE", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"},
    "BruteForce": {"RATE_LIMIT", "BLOCK_TRAFFIC_PROFILE", "REQUIRE_REAUTHENTICATION", "INCREASE_LOGGING", "NOTIFY_OPERATOR"},
    "Spoofing": {"MONITOR", "BLOCK_TRAFFIC_PROFILE", "RESTRICT_EGRESS", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "REQUIRE_REAUTHENTICATION", "NOTIFY_OPERATOR"},
    "Mirai": {"RESTRICT_EGRESS", "ISOLATE_SEGMENT", "RATE_LIMIT", "BLOCK_TRAFFIC_PROFILE", "INCREASE_LOGGING", "CAPTURE_TRAFFIC", "NOTIFY_OPERATOR"},
}

DISRUPTIVE_ACTIONS = {
    "RATE_LIMIT",
    "BLOCK_TRAFFIC_PROFILE",
    "RESTRICT_EGRESS",
    "ISOLATE_SEGMENT",
    "REQUIRE_REAUTHENTICATION",
}

RAW_INTENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "threat_assessment",
        "recommended_actions",
        "evidence_used",
        "requires_human_approval",
        "uncertainty_note",
    ],
    "properties": {
        "summary": {"type": "string", "minLength": 1},
        "threat_assessment": {
            "type": "object",
            "additionalProperties": False,
            "required": ["predicted_family", "confidence", "rationale"],
            "properties": {
                "predicted_family": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
        },
        "recommended_actions": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "target", "parameters", "rationale"],
                "properties": {
                    "action": {"type": "string", "enum": ALLOWED_ACTIONS},
                    "target": {"type": "string"},
                    "parameters": {"type": "object"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "evidence_used": {"type": "array", "items": {"type": "string"}},
        "requires_human_approval": {"type": "boolean"},
        "uncertainty_note": {"type": "string"},
    },
}

ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "action",
        "target",
        "parameters",
        "duration_seconds",
        "rollback",
        "approval_required",
        "evidence_refs",
        "rationale",
    ],
    "properties": {
        "action": {"type": "string", "enum": ALLOWED_ACTIONS},
        "target": {"type": "string", "minLength": 1},
        "parameters": {"type": "object"},
        "duration_seconds": {"type": "integer", "minimum": 0, "maximum": 3600},
        "rollback": {"type": "string", "minLength": 1},
        "approval_required": {"type": "boolean"},
        "evidence_refs": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string", "minLength": 1},
    },
}

FULL_INTENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "intent_id",
        "alert_ref",
        "route",
        "predicted_threat",
        "confidence",
        "scope",
        "actions",
        "status",
        "guardrail",
    ],
    "properties": {
        "schema": {"const": "iot.mitigation.intent.v1"},
        "intent_id": {"type": "string"},
        "alert_ref": {"type": "string"},
        "route": {"enum": ["plan", "monitor", "escalate"]},
        "predicted_threat": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "scope": {"type": "string"},
        "actions": {"type": "array", "minItems": 1, "maxItems": 3, "items": ACTION_SCHEMA},
        "status": {"const": "PROPOSED_NOT_EXECUTED"},
        "guardrail": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_validated", "policy_validated", "normalization_notes"],
            "properties": {
                "schema_validated": {"type": "boolean"},
                "policy_validated": {"type": "boolean"},
                "normalization_notes": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def validate(instance: Any, schema: dict[str, Any]) -> tuple[bool, list[str]]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    return not errors, [f"{'/'.join(map(str, error.path)) or '$'}: {error.message}" for error in errors]
