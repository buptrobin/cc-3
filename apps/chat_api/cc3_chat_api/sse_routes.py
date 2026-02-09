from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .auth import get_user_id
from .bootstrap import ensure_cc3_importable
from .storage import conversation_root, run_dir

repo_root = ensure_cc3_importable()

router = APIRouter()


def _format_sse(data: str, *, event: str | None = None) -> bytes:
    # Basic SSE framing.
    out = []
    if event:
        out.append(f"event: {event}\n")
    for line in data.splitlines() or [""]:
        out.append(f"data: {line}\n")
    out.append("\n")
    return "".join(out).encode("utf-8")


async def _tail_events_ndjson(events_path: Path, status_path: Path) -> AsyncIterator[bytes]:
    # Initial comment to establish connection.
    yield b": connected\n\n"

    offset = 0
    while True:
        if events_path.exists():
            with events_path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                # Avoid mixing file iteration (`for line in f`) with tell(); on
                # some platforms/Python versions that raises:
                # "OSError: telling position disabled by next() call".
                while True:
                    line = f.readline()
                    if not line:
                        break
                    offset = f.tell()
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    yield _format_sse(line)

        status = {}
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                status = {}

        state = status.get("state")
        if state in {"completed", "failed"}:
            # Send final status event, then exit.
            yield _format_sse(json.dumps(status, ensure_ascii=True), event="status")
            break

        await asyncio.sleep(0.25)


@router.get("/v1/conversations/{conversation_id}/runs/{run_id}/events.sse")
async def run_events(request: Request, conversation_id: str, run_id: str):
    # EventSource cannot set headers; allow query param for SSE.
    user_id = get_user_id(request, allow_query_param=True)

    ws = conversation_root(repo_root, user_id, conversation_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="conversation not found")

    rd = run_dir(ws, run_id)
    if not rd.exists():
        raise HTTPException(status_code=404, detail="run not found")

    events_path = rd / "events.ndjson"
    status_path = rd / "status.json"

    return StreamingResponse(
        _tail_events_ndjson(events_path, status_path),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
