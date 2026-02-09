from __future__ import annotations

from cc3.events import (
    extract_api_key_source,
    extract_result_text,
    extract_session_id,
    extract_text_delta,
    guess_event_kind,
)


def test_extract_session_id_walks_nested() -> None:
    obj = {"foo": {"bar": {"session_id": "sid-123"}}}
    assert extract_session_id(obj) == "sid-123"


def test_extract_text_delta_common_shapes() -> None:
    assert extract_text_delta({"delta": "hello"}) == "hello"
    assert extract_text_delta({"delta": {"text": "world"}}) == "world"
    assert extract_text_delta({"delta": {"nope": 1}}) is None


def test_extract_result_text_common_shapes() -> None:
    assert extract_result_text({"result_text": "A"}) == "A"
    assert extract_result_text({"result": {"text": "B"}}) == "B"


def test_extract_api_key_source() -> None:
    obj = {"init": {"apiKeySource": "env"}}
    assert extract_api_key_source(obj) == "env"


def test_guess_event_kind_heuristics() -> None:
    assert guess_event_kind({"type": "InitEvent", "apiKeySource": "env"}) == "init"
    assert guess_event_kind({"delta": "x"}) == "delta"
    assert guess_event_kind({"result_text": "done", "usage": {}}) == "result"
