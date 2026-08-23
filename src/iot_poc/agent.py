from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .schemas import ALLOWED_ACTIONS, RAW_INTENT_SCHEMA


@dataclass
class AgentResponse:
    raw_intent: dict[str, Any]
    raw_text: str
    input_tokens: int
    output_tokens: int


class OpenAIMitigationAgent:
    def __init__(self, model: str, max_output_tokens: int):
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not available to the experiment process.")
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model
        self.max_output_tokens = max_output_tokens

    def generate(
        self,
        alert: dict[str, Any],
        evidence: list[dict[str, Any]],
        condition: str,
    ) -> AgentResponse:
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You prepare IoT gateway mitigation intent for offline evaluation. "
                "Use only the supplied detector alert; never assume a device identity. "
                "Use only allowed actions. Do not provide shell commands, executable code, "
                "or claim that an action was executed. For low-confidence alerts, prefer "
                "evidence collection and operator escalation. Evidence identifiers must be "
                "copied exactly from retrieved_context; when no context is supplied, return "
                "an empty evidence_used array. When retrieved context is supplied, cite one "
                "or more relevant identifiers; leave the array empty only when none is relevant."
            ),
            input=json.dumps(
                {
                    "task": "Produce a concise, bounded IoT mitigation-intent proposal.",
                    "condition": condition,
                    "detector_alert": alert,
                    "retrieved_context": [
                        {
                            "source": item["source"],
                            "chunk_id": item["chunk_id"],
                            "excerpt": item["excerpt"],
                        }
                        for item in evidence
                    ],
                    "allowed_actions": ALLOWED_ACTIONS,
                    "limits": {
                        "maximum_actions": 3,
                        "rationale_words": 60,
                        "intent_only": True,
                        "execution_forbidden": True,
                    },
                },
                indent=2,
            ),
            reasoning={"effort": "none"},
            max_output_tokens=self.max_output_tokens,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "iot_mitigation_proposal",
                    "schema": RAW_INTENT_SCHEMA,
                    "strict": False,
                }
            },
        )
        raw_text = getattr(response, "output_text", None) or response_text(response) or "{}"
        try:
            raw_intent = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raw_intent = {"_raw_output": raw_text, "_json_parse_error": str(exc)}
        usage = getattr(response, "usage", None)
        return AgentResponse(
            raw_intent=raw_intent,
            raw_text=raw_text,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        )


def response_text(response: Any) -> str | None:
    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "".join(chunks) if chunks else None
