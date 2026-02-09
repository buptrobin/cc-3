from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .bootstrap import ensure_cc3_importable

_repo_root = ensure_cc3_importable()

from cc3.locking import acquire_workspace_lock  # noqa: E402


@dataclass(frozen=True)
class ConversationRef:
    user_id: str
    conversation_id: str
    workspace: Path


def users_root(repo_root: Path) -> Path:
    return repo_root / "workspaces" / "users"


def user_root(repo_root: Path, user_id: str) -> Path:
    return users_root(repo_root) / user_id


def conversations_root(repo_root: Path, user_id: str) -> Path:
    return user_root(repo_root, user_id) / "conversations"


def conversation_root(repo_root: Path, user_id: str, conversation_id: str) -> Path:
    return conversations_root(repo_root, user_id) / conversation_id


def ensure_conversation_workspace(repo_root: Path, user_id: str, conversation_id: str) -> ConversationRef:
    ws = conversation_root(repo_root, user_id, conversation_id)
    (ws / "runs").mkdir(parents=True, exist_ok=True)
    (ws / "kb").mkdir(parents=True, exist_ok=True)
    return ConversationRef(user_id=user_id, conversation_id=conversation_id, workspace=ws)


def new_conversation_id() -> str:
    return uuid4().hex


def new_message_id() -> str:
    return uuid4().hex


def new_run_id() -> str:
    # sortable-ish
    return f"{int(time.time())}-{uuid4().hex[:8]}"


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def conversation_meta_path(ws: Path) -> Path:
    return ws / "conversation.json"


def session_path(ws: Path) -> Path:
    return ws / "session.json"


def messages_path(ws: Path) -> Path:
    return ws / "messages.ndjson"


def run_dir(ws: Path, run_id: str) -> Path:
    return ws / "runs" / run_id


def run_status_path(ws: Path, run_id: str) -> Path:
    return run_dir(ws, run_id) / "status.json"


def list_conversations(repo_root: Path, user_id: str) -> list[dict[str, Any]]:
    root = conversations_root(repo_root, user_id)
    if not root.exists():
        return []

    out: list[dict[str, Any]] = []
    for d in sorted(root.iterdir(), key=lambda p: p.name):
        if not d.is_dir():
            continue
        meta = _read_json(conversation_meta_path(d))
        if meta:
            out.append(meta)
        else:
            out.append({"conversation_id": d.name, "title": d.name})
    return out


def create_conversation(repo_root: Path, user_id: str, title: str | None) -> dict[str, Any]:
    cid = new_conversation_id()
    ref = ensure_conversation_workspace(repo_root, user_id, cid)

    meta = {
        "user_id": user_id,
        "conversation_id": cid,
        "title": title or "New conversation",
        "created_at": time.time(),
        "updated_at": time.time(),
    }

    # Initialize files under lock.
    h = acquire_workspace_lock(ref.workspace, timeout_s=5.0)
    try:
        _atomic_write_json(conversation_meta_path(ref.workspace), meta)
        _atomic_write_json(session_path(ref.workspace), {"claude_session_id": None, "updated_at": time.time()})
        (messages_path(ref.workspace)).touch(exist_ok=True)
    finally:
        h.release()

    return meta


def load_messages(ws: Path, *, limit: int = 200) -> list[dict[str, Any]]:
    p = messages_path(ws)
    if not p.exists():
        return []
    msgs: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            msgs.append(obj)
    return msgs[-limit:]


def append_message(ws: Path, msg: dict[str, Any]) -> None:
    p = messages_path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=True))
        f.write("\n")


def load_session_id(ws: Path) -> str | None:
    data = _read_json(session_path(ws))
    sid = data.get("claude_session_id")
    return sid if isinstance(sid, str) and sid else None


def save_session_id(ws: Path, session_id: str | None, *, last_run_id: str | None = None) -> None:
    obj = {
        "claude_session_id": session_id,
        "updated_at": time.time(),
    }
    if last_run_id:
        obj["last_run_id"] = last_run_id
    _atomic_write_json(session_path(ws), obj)


def write_run_status(ws: Path, run_id: str, status: dict[str, Any]) -> None:
    _atomic_write_json(run_status_path(ws, run_id), status)


def read_run_status(ws: Path, run_id: str) -> dict[str, Any]:
    return _read_json(run_status_path(ws, run_id))
