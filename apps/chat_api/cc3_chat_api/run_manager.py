from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bootstrap import ensure_cc3_importable

_repo_root = ensure_cc3_importable()

from cc3.locking import acquire_workspace_lock  # noqa: E402
from cc3.runner import RunConfig, run_one_step  # noqa: E402

from .storage import (  # noqa: E402
    append_message,
    load_session_id,
    read_run_status,
    run_dir,
    save_session_id,
    write_run_status,
)


@dataclass(frozen=True)
class RunRequest:
    user_id: str
    conversation_id: str
    workspace: Path
    run_id: str
    content: str


class RunManager:
    """Run coordinator.

    MVP: uses a background thread per run. This keeps FastAPI endpoints simple
    (sync handlers) and avoids event-loop/threadpool edge cases.
    """

    def __init__(self, *, repo_root: Path):
        self._repo_root = repo_root
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self, req: RunRequest) -> None:
        with self._lock:
            if req.run_id in self._threads:
                return
            t = threading.Thread(target=self._run_sync, args=(req,), daemon=True)
            self._threads[req.run_id] = t
            t.start()

    def _run_sync(self, req: RunRequest) -> None:
        started_at = time.time()
        try:
            # Read session id + set running under lock.
            h = acquire_workspace_lock(req.workspace, timeout_s=10.0)
            try:
                session_id = load_session_id(req.workspace)
                write_run_status(
                    req.workspace,
                    req.run_id,
                    {
                        "run_id": req.run_id,
                        "state": "running",
                        "started_at": started_at,
                    },
                )
            finally:
                h.release()

            result = run_one_step(
                repo_root=self._repo_root,
                workspace=req.workspace,
                instruction=req.content,
                session_id=session_id,
                run_id=req.run_id,
                fork=False,
                run_cfg=RunConfig(policy_preset="safe", permission_mode="dontAsk"),
                timeout_s=600.0,
                lock_timeout_s=30.0,
            )

            finished_at = time.time()

            # Persist assistant message + session update under lock.
            h2 = acquire_workspace_lock(req.workspace, timeout_s=10.0)
            try:
                append_message(
                    req.workspace,
                    {
                        "message_id": f"asst-{req.run_id}",
                        "role": "assistant",
                        "content": result.final_text,
                        "created_at": finished_at,
                        "run_id": req.run_id,
                    },
                )
                save_session_id(req.workspace, result.session_id_after, last_run_id=req.run_id)
                write_run_status(
                    req.workspace,
                    req.run_id,
                    {
                        "run_id": req.run_id,
                        "state": "completed",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "exit_code": result.exit_code,
                        "timed_out": result.timed_out,
                        "session_id_after": result.session_id_after,
                    },
                )
            finally:
                h2.release()

        except Exception as e:
            finished_at = time.time()
            tb = traceback.format_exc()

            h3 = acquire_workspace_lock(req.workspace, timeout_s=10.0)
            try:
                write_run_status(
                    req.workspace,
                    req.run_id,
                    {
                        "run_id": req.run_id,
                        "state": "failed",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "error": str(e),
                        "traceback": tb,
                    },
                )
            finally:
                h3.release()

    def status(self, workspace: Path, run_id: str) -> dict[str, Any]:
        return read_run_status(workspace, run_id)

    def artifacts_dir(self, workspace: Path, run_id: str) -> Path:
        return run_dir(workspace, run_id)
