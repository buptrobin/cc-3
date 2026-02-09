from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


def _walk(obj: Any) -> Iterable[Any]:
    """Yield all nested dict/list nodes (including obj itself)."""

    stack = [obj]
    while stack:
        cur = stack.pop()
        yield cur
        if isinstance(cur, dict):
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)


def extract_session_id(obj: dict[str, Any]) -> str | None:
    for node in _walk(obj):
        if isinstance(node, dict):
            for k in ("session_id", "sessionId", "session", "sessionID"):
                v = node.get(k)
                if isinstance(v, str) and v:
                    return v
    return None


def extract_text_delta(obj: dict[str, Any]) -> str | None:
    # Common shapes: {"delta": "..."}, or {"delta": {"text": "..."}}
    d = obj.get("delta")
    if isinstance(d, str) and d:
        return d
    if isinstance(d, dict):
        t = d.get("text")
        if isinstance(t, str) and t:
            return t
    return None


def extract_result_text(obj: dict[str, Any]) -> str | None:
    # Try several likely fields.
    for key in ("result_text", "resultText", "result", "text", "output"):
        v = obj.get(key)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):
            for sub in ("text", "result_text", "output"):
                t = v.get(sub)
                if isinstance(t, str) and t:
                    return t
    return None


def extract_api_key_source(obj: dict[str, Any]) -> str | None:
    for node in _walk(obj):
        if isinstance(node, dict):
            v = node.get("apiKeySource")
            if isinstance(v, str) and v:
                return v
    return None


def extract_tools(obj: dict[str, Any]) -> list[str] | None:
    v = obj.get("tools")
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    return None


def extract_skills(obj: dict[str, Any]) -> list[str] | None:
    v = obj.get("skills")
    if isinstance(v, list) and all(isinstance(x, str) for x in v):
        return list(v)
    return None


def guess_event_kind(obj: dict[str, Any]) -> str:
    # Best-effort classification for internal use.
    t = obj.get("type")
    if isinstance(t, str):
        low = t.lower()
        if "init" in low:
            return "init"
        if "result" in low:
            return "result"
        if "error" in low:
            return "error"
        if "delta" in low or "assistant" in low:
            return "delta"

    # Heuristics based on fields.
    if extract_api_key_source(obj) is not None or obj.get("permissionMode") is not None:
        return "init"

    if extract_result_text(obj) is not None and ("usage" in obj or "cost" in obj):
        return "result"

    if extract_text_delta(obj) is not None:
        return "delta"

    if obj.get("error") is not None or obj.get("message") is not None and obj.get("code") is not None:
        return "error"

    return "unknown"


@dataclass(frozen=True)
class NormalizedEvent:
    kind: str
    session_id: str | None
    text_delta: str | None
    result_text: str | None
    api_key_source: str | None
    raw: dict[str, Any]


def normalize_event(obj: dict[str, Any]) -> NormalizedEvent:
    kind = guess_event_kind(obj)
    return NormalizedEvent(
        kind=kind,
        session_id=extract_session_id(obj),
        text_delta=extract_text_delta(obj) if kind == "delta" else None,
        result_text=extract_result_text(obj) if kind == "result" else None,
        api_key_source=extract_api_key_source(obj) if kind == "init" else None,
        raw=obj,
    )
