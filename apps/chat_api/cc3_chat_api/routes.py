from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .auth import get_user_id
from .bootstrap import ensure_cc3_importable

repo_root = ensure_cc3_importable()

from cc3.locking import acquire_workspace_lock  # noqa: E402

from .run_manager import RunManager, RunRequest  # noqa: E402
from .storage import (  # noqa: E402
    append_message,
    conversation_root,
    create_conversation,
    list_conversations,
    load_messages,
    new_message_id,
    new_run_id,
    run_dir,
)

router = APIRouter()

_run_manager = RunManager(repo_root=repo_root)


@router.get("/v1/conversations")
def conversations(request: Request) -> list[dict[str, Any]]:
    user_id = get_user_id(request)
    return list_conversations(repo_root, user_id)


@router.post("/v1/conversations")
def conversations_create(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    user_id = get_user_id(request)
    title = None
    if isinstance(body, dict):
        t = body.get("title")
        title = t if isinstance(t, str) and t.strip() else None
    return create_conversation(repo_root, user_id, title)


@router.get("/v1/conversations/{conversation_id}/messages")
def messages(request: Request, conversation_id: str, limit: int = 200) -> list[dict[str, Any]]:
    user_id = get_user_id(request)
    ws = conversation_root(repo_root, user_id, conversation_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="conversation not found")

    # No lock for read (append-only file); acceptable for MVP.
    return load_messages(ws, limit=min(max(limit, 1), 1000))


@router.post("/v1/conversations/{conversation_id}/messages")
def messages_post(request: Request, conversation_id: str, body: dict[str, Any]) -> dict[str, Any]:
    user_id = get_user_id(request)

    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="content required")

    ws = conversation_root(repo_root, user_id, conversation_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="conversation not found")

    run_id = new_run_id()
    msg_id = new_message_id()
    now = time.time()

    # Serialize mutation under conversation workspace lock.
    h = acquire_workspace_lock(ws, timeout_s=10.0)
    try:
        append_message(
            ws,
            {
                "message_id": msg_id,
                "role": "user",
                "content": content,
                "created_at": now,
                "run_id": run_id,
            },
        )
        # Ensure run dir exists so SSE can connect immediately.
        run_dir(ws, run_id).mkdir(parents=True, exist_ok=True)
    finally:
        h.release()

    _run_manager.start(
        RunRequest(
            user_id=user_id,
            conversation_id=conversation_id,
            workspace=ws,
            run_id=run_id,
            content=content,
        )
    )

    return {"run_id": run_id, "user_message_id": msg_id}


@router.get("/v1/conversations/{conversation_id}/runs/{run_id}")
def run_status(request: Request, conversation_id: str, run_id: str) -> dict[str, Any]:
    user_id = get_user_id(request)
    ws = conversation_root(repo_root, user_id, conversation_id)
    if not ws.exists():
        raise HTTPException(status_code=404, detail="conversation not found")

    rd = run_dir(ws, run_id)
    if not rd.exists():
        raise HTTPException(status_code=404, detail="run not found")

    return _run_manager.status(ws, run_id)
