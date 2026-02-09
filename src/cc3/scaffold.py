from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import agent_dir, workspace_dir


@dataclass(frozen=True)
class InitAgentResult:
    agent_path: Path
    workspace_path: Path


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def init_agent(*, repo_root: Path, agent_id: str, overwrite: bool = False) -> InitAgentResult:
    """Create agents/<id>/ and workspaces/<id>/ scaffolding.

    Matches `design.md` directory conventions (agents/ + workspaces/).
    """

    a_dir = agent_dir(repo_root, agent_id)
    w_dir = workspace_dir(repo_root, agent_id)

    # Directories
    (a_dir / "skills").mkdir(parents=True, exist_ok=True)
    (w_dir / "kb").mkdir(parents=True, exist_ok=True)
    (w_dir / "runs").mkdir(parents=True, exist_ok=True)

    # Templates
    _write_text(
        a_dir / "agent.yaml",
        "\n".join(
            [
                f"agent_id: {agent_id}",
                "model: null",
                "# Claude CLI permission mode (passed as --permission-mode)",
                "permission_mode: dontAsk",
                "# Policy preset: safe | dev | open",
                "policy_preset: safe",
                "",
            ]
        ),
        overwrite=overwrite,
    )

    _write_text(
        a_dir / "system_prompt.md",
        "\n".join(
            [
                "# System Prompt (Claude Code CLI executor)",
                "",
                "You are an execution agent running inside a workspace.",
                "",
                "Rules:",
                "- Search before answering. Prefer Grep/Read/Glob over guessing.",
                "- When citing evidence from kb/ or repo files, include citations as `path:line`.",
                "- Stay within allowed directories; do not access unrelated paths.",
                "- If evidence is insufficient, say so and suggest what to add to kb/.",
                "",
                "Output format:",
                "- Be concise and action-oriented.",
                "",
            ]
        ),
        overwrite=overwrite,
    )

    _write_text(
        a_dir / "policies.md",
        "\n".join(
            [
                "# Policies (optional)",
                "",
                "- safe: Read/Grep/Glob only.",
                "- dev: allow Edit/Write/Bash (bounded to workspace + repo via add-dir).",
                "- open: allow web tools if enabled in the environment.",
                "",
            ]
        ),
        overwrite=overwrite,
    )

    _write_text(
        w_dir / ".env",
        "\n".join(
            [
                "# Workspace-local environment for Claude CLI execution.",
                "#",
                "# ANTHROPIC_API_KEY=...",
                "# ANTHROPIC_BASE_URL=...",
                "# MODEL=...",
                "",
            ]
        ),
        overwrite=overwrite,
    )

    return InitAgentResult(agent_path=a_dir, workspace_path=w_dir)
