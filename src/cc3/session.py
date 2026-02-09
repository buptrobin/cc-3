from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import workspace_dir, workspaces_dir


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _dt_to_str(dt: datetime) -> str:
    return dt.isoformat()


def _str_to_dt(s: Any, *, fallback: datetime) -> datetime:
    if isinstance(s, str) and s:
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return fallback
    return fallback


@dataclass
class SessionRecord:
    agent_id: str
    workspace_path: Path
    claude_session_id: str | None = None

    created_at: datetime = field(default_factory=_now_utc)
    last_active_at: datetime = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "workspace_path": str(self.workspace_path),
            "claude_session_id": self.claude_session_id,
            "created_at": _dt_to_str(self.created_at),
            "last_active_at": _dt_to_str(self.last_active_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, workspace_path: Path, agent_id: str) -> "SessionRecord":
        now = _now_utc()
        return cls(
            agent_id=agent_id,
            workspace_path=workspace_path,
            claude_session_id=(data.get("claude_session_id") if isinstance(data.get("claude_session_id"), str) else None),
            created_at=_str_to_dt(data.get("created_at"), fallback=now),
            last_active_at=_str_to_dt(data.get("last_active_at"), fallback=now),
        )


class SessionManager:
    """Owns workspace/session.json for a single repo root."""

    def __init__(self, repo_root: Path):
        self._repo_root = repo_root

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def ensure_workspace(self, agent_id: str) -> Path:
        # Ensure parent exists so running `cc3 run` doesn't require `init-agent`.
        workspaces_dir(self._repo_root).mkdir(parents=True, exist_ok=True)
        wdir = workspace_dir(self._repo_root, agent_id)
        (wdir / "kb").mkdir(parents=True, exist_ok=True)
        (wdir / "runs").mkdir(parents=True, exist_ok=True)
        return wdir

    def session_path(self, agent_id: str) -> Path:
        return self.ensure_workspace(agent_id) / "session.json"

    def load_or_create(self, agent_id: str) -> SessionRecord:
        path = self.session_path(agent_id)
        if not path.exists():
            rec = SessionRecord(agent_id=agent_id, workspace_path=path.parent)
            self.save(rec)
            return rec

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
        return SessionRecord.from_dict(data, workspace_path=path.parent, agent_id=agent_id)

    def save(self, rec: SessionRecord) -> None:
        rec.last_active_at = _now_utc()
        path = self.session_path(rec.agent_id)
        path.write_text(json.dumps(rec.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
