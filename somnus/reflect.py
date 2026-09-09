"""Read-only, structured Hindsight Reflect execution."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from .memory_router import HindsightClient, redact_sensitive


DEFAULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "summary": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "recommended_route": {"type": "string"},
        "requires_human_review": {"type": "boolean"},
    },
    "required": ["domain", "summary", "facts", "contradictions", "recommended_route", "requires_human_review"],
}

@dataclass(frozen=True)
class ReflectRequest:
    query: str
    budget: str = "low"
    max_tokens: int = 1200
    include_facts: bool = True
    include_tool_calls: bool = False
    fact_types: tuple[str, ...] = ("world", "experience", "observation")
    exclude_mental_models: bool = True
    exclude_mental_model_ids: tuple[str, ...] = ()
    response_schema: Mapping[str, Any] = field(default_factory=lambda: DEFAULT_SCHEMA)

    def payload(self) -> dict[str, Any]:
        if self.budget not in {"low", "mid", "high"}:
            raise ValueError("budget must be low, mid, or high")
        if not 128 <= self.max_tokens <= 8192:
            raise ValueError("max_tokens must be between 128 and 8192")
        allowed = {"world", "experience", "observation"}
        if not self.query.strip() or not set(self.fact_types) <= allowed:
            raise ValueError("query and fact_types are invalid")
        payload: dict[str, Any] = {
            "budget": self.budget,
            "max_tokens": self.max_tokens,
            "query": redact_sensitive(self.query),
            "include": {"facts": {}, **({"tool_calls": {}} if self.include_tool_calls else {})},
            "fact_types": list(self.fact_types),
            "exclude_mental_models": self.exclude_mental_models,
            "response_schema": dict(self.response_schema),
        }
        if self.exclude_mental_model_ids:
            payload["exclude_mental_model_ids"] = list(self.exclude_mental_model_ids)
        if not self.include_facts:
            payload["include"].pop("facts", None)
        return payload


def _sanitize(value: Any, *, key: str = "") -> Any:
    sensitive = re.compile(r"(?i)(key|token|secret|password|authorization|connection|credential)")
    identifier = re.compile(r"(?i)(^id$|_id$|^id_|memory_id|directive_id|mental_model_id)")
    if isinstance(value, Mapping):
        return {k: ("[REDACTED]" if sensitive.search(str(k)) else ("[ID_OMITTED]" if identifier.search(str(k)) else _sanitize(v, key=str(k)))) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, key=key) for item in value]
    if isinstance(value, str):
        return redact_sensitive(value)
    return value


def sanitize_response(response: Any) -> Any:
    return _sanitize(response)


class Reflector:
    def __init__(self, client: HindsightClient) -> None:
        self.client = client

    def run(self, bank_id: str, request: ReflectRequest) -> dict[str, Any]:
        raw = self.client.request("POST", f"/v1/default/banks/{bank_id}/reflect", payload=request.payload())
        if not isinstance(raw, Mapping):
            raise RuntimeError("Hindsight Reflect returned an invalid response")
        return sanitize_response(raw)
