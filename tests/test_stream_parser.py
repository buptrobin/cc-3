from __future__ import annotations

import io

from cc3.stream_parser import iter_stream_json_lines


def test_iter_stream_json_lines_parses_ndjson() -> None:
    s = io.StringIO('{"type":"init","session_id":"abc"}\n{"type":"delta","delta":"hi"}\n')
    lines = list(iter_stream_json_lines(s))

    assert len(lines) == 2
    assert lines[0].obj and lines[0].obj["session_id"] == "abc"
    assert lines[1].obj and lines[1].obj["delta"] == "hi"


def test_iter_stream_json_lines_handles_invalid_json() -> None:
    s = io.StringIO('{"type":"ok"}\nnot-json\n')
    lines = list(iter_stream_json_lines(s))

    assert len(lines) == 2
    assert lines[0].obj is not None and lines[0].error is None
    assert lines[1].obj is None
    assert lines[1].error and "json_decode_error" in lines[1].error
