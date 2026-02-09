from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Find the repository root by walking up to a directory containing pyproject.toml.

    This keeps behavior predictable when invoking `cc3` from subdirectories.
    """

    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").exists():
            return p
    # Fallback: current directory.
    return cur


def agents_dir(repo_root: Path) -> Path:
    return repo_root / "agents"


def agent_dir(repo_root: Path, agent_id: str) -> Path:
    return agents_dir(repo_root) / agent_id


def workspaces_dir(repo_root: Path) -> Path:
    return repo_root / "workspaces"


def workspace_dir(repo_root: Path, agent_id: str) -> Path:
    return workspaces_dir(repo_root) / agent_id
