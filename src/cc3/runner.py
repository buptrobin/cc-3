from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AgentConfig
from .executor import ClaudeCliExecutor, ExecutionResult


@dataclass(frozen=True)
class RunConfig:
    """High-level config used by server integrations."""

    policy_preset: str = "safe"  # safe|dev|open
    permission_mode: str = "dontAsk"
    model: str | None = None


def run_one_step(
    *,
    repo_root: Path,
    workspace: Path,
    instruction: str,
    session_id: str | None,
    run_id: str,
    fork: bool = False,
    run_cfg: RunConfig | None = None,
    timeout_s: float = 600.0,
    lock_timeout_s: float = 30.0,
) -> ExecutionResult:
    """Run one step using the Claude Code CLI executor.

    This is a library-friendly entrypoint for servers (e.g., chat_api) that manage
    user/conversation workspaces themselves.
    """

    rc = run_cfg or RunConfig()

    cfg = AgentConfig(agent_id="server")
    cfg.policy_preset = rc.policy_preset
    cfg.permission_mode = rc.permission_mode
    cfg.model = rc.model

    ex = ClaudeCliExecutor(repo_root=repo_root, timeout_s=timeout_s, lock_timeout_s=lock_timeout_s)
    return ex.execute(
        instruction=instruction,
        workspace=workspace,
        cfg=cfg,
        session_id=session_id,
        fork=fork,
        run_id=run_id,
    )
