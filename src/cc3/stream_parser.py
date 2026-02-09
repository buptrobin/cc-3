from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class StreamLine:
    raw: str
    obj: dict | None
    error: str | None


def iter_stream_json_lines(text_stream) -> Iterator[StreamLine]:
    """Iterate a text stream producing NDJSON (one JSON object per line)."""

    for raw in text_stream:
        line = raw.rstrip("\n")
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            yield StreamLine(raw=line, obj=None, error=f"json_decode_error: {e}")
            continue
        if isinstance(obj, dict):
            yield StreamLine(raw=line, obj=obj, error=None)
        else:
            # Stream-json should be objects; keep non-dict as parse error.
            yield StreamLine(raw=line, obj=None, error=f"unexpected_json_type: {type(obj).__name__}")
