from __future__ import annotations

import json
import secrets
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .claude_cmd import build_claude_argv
from .config import AgentConfig, env_for_claude, load_dotenv
from .events import normalize_event
from .locking import acquire_workspace_lock
from .stream_parser import iter_stream_json_lines


@dataclass(frozen=True)
class ExecutionResult:
    run_id: str
    run_dir: Path
    exit_code: int
    timed_out: bool

    session_id_before: str | None
    session_id_after: str | None

    api_key_source: str | None

    final_text: str


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_run_id() -> str:
    ts = _now_utc().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{secrets.token_hex(3)}"


def _read_text_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _jsonl_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=True))
        f.write("\n")


class ClaudeCliExecutor:
    def __init__(self, *, repo_root: Path, timeout_s: float = 600.0, lock_timeout_s: float = 30.0):
        self._repo_root = repo_root
        self._timeout_s = timeout_s
        self._lock_timeout_s = lock_timeout_s

    def execute(
        self,
        *,
        instruction: str,
        workspace: Path,
        cfg: AgentConfig,
        session_id: str | None,
        fork: bool = False,
        run_id: str | None = None,
        run_dir: Path | None = None,
    ) -> ExecutionResult:
        """Execute one Claude Code CLI run.

        `run_id`/`run_dir` can be provided by the caller (e.g. a web server) so that
        clients can subscribe to artifacts immediately (SSE tailing `events.ndjson`).
        """

        if run_id is None and run_dir is None:
            run_id = _new_run_id()

        if run_dir is None:
            assert run_id is not None
            run_dir = workspace / "runs" / run_id
        else:
            # Derive a stable run_id from directory name if not provided.
            if run_id is None:
                run_id = run_dir.name

        run_dir.mkdir(parents=True, exist_ok=True)

        events_path = run_dir / "events.ndjson"
        norm_events_path = run_dir / "events_norm.ndjson"
        stderr_path = run_dir / "stderr.log"
        meta_path = run_dir / "meta.json"
        result_path = run_dir / "result.txt"
        step_path = run_dir / "step.json"

        system_prompt = _read_text_file(cfg.system_prompt_path) if cfg.system_prompt_path else None
        append_system_prompt = (
            _read_text_file(cfg.append_system_prompt_path) if cfg.append_system_prompt_path else None
        )

        add_dirs = [
            workspace,
            workspace / "kb",
            self._repo_root,
            *cfg.add_dirs,
        ]

        invocation = build_claude_argv(
            prompt=instruction,
            cfg=cfg,
            resume=session_id,
            fork=fork,
            add_dirs=add_dirs,
            system_prompt=system_prompt,
            append_system_prompt=append_system_prompt,
        )

        dotenv = load_dotenv(workspace / ".env")
        env = env_for_claude(dotenv=dotenv)

        started_at = _now_utc()
        timed_out = False

        # Shared state updated by stdout reader.
        state_lock = threading.Lock()
        session_id_after: str | None = session_id
        api_key_source: str | None = None
        deltas: list[str] = []
        result_text: str | None = None

        def reader_thread(proc: subprocess.Popen[str]) -> None:
            nonlocal session_id_after, api_key_source, result_text

            assert proc.stdout is not None
            with events_path.open("w", encoding="utf-8") as events_f:
                for sl in iter_stream_json_lines(proc.stdout):
                    # Always persist the raw line as emitted.
                    events_f.write(sl.raw)
                    events_f.write("\n")
                    events_f.flush()

                    if sl.obj is None:
                        _jsonl_write(
                            norm_events_path,
                            {"kind": "parse_error", "error": sl.error, "raw": sl.raw},
                        )
                        continue

                    norm = normalize_event(sl.obj)
                    _jsonl_write(
                        norm_events_path,
                        {
                            "kind": norm.kind,
                            "session_id": norm.session_id,
                            "text_delta": norm.text_delta,
                            "result_text": norm.result_text,
                            "api_key_source": norm.api_key_source,
                        },
                    )

                    with state_lock:
                        if norm.session_id:
                            session_id_after = norm.session_id
                        if norm.api_key_source:
                            api_key_source = norm.api_key_source
                        if norm.text_delta:
                            deltas.append(norm.text_delta)
                        if norm.result_text:
                            result_text = norm.result_text

        lock_handle = acquire_workspace_lock(workspace, timeout_s=self._lock_timeout_s)
        try:
            with stderr_path.open("w", encoding="utf-8") as stderr_f:
                proc = subprocess.Popen(
                    invocation.argv,
                    cwd=str(workspace),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=stderr_f,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                t = threading.Thread(target=reader_thread, args=(proc,))
                t.start()

                try:
                    exit_code = proc.wait(timeout=self._timeout_s)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.kill()
                    exit_code = proc.wait(timeout=30)

                # Deterministically drain stdout so artifacts are complete.
                t.join()
        finally:
            lock_handle.release()

        finished_at = _now_utc()

        with state_lock:
            final_text = result_text if result_text is not None else "".join(deltas)
            sid_after = session_id_after
            aks = api_key_source

        result_path.write_text(final_text, encoding="utf-8")

        step_path.write_text(
            json.dumps(
                {
                    "instruction": instruction,
                    "session_id_before": session_id,
                    "session_id_after": sid_after,
                    "fork": fork,
                    "timed_out": timed_out,
                    "exit_code": exit_code,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

        meta_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_dir": str(run_dir),
                    "argv": invocation.argv,
                    "cwd": str(workspace),
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "session_id_before": session_id,
                    "session_id_after": sid_after,
                    "apiKeySource": aks,
                    "permission_mode": cfg.permission_mode,
                    "policy_preset": cfg.policy_preset,
                    "model": cfg.model,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

        assert run_id is not None
        return ExecutionResult(
            run_id=run_id,
            run_dir=run_dir,
            exit_code=exit_code,
            timed_out=timed_out,
            session_id_before=session_id,
            session_id_after=sid_after,
            api_key_source=aks,
            final_text=final_text,
        )
