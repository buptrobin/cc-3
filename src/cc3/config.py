from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import agent_dir


@dataclass
class AgentConfig:
    agent_id: str

    model: str | None = None

    # Passed through to `claude --permission-mode`.
    permission_mode: str = "dontAsk"

    # cc3-level preset: safe|dev|open.
    policy_preset: str = "safe"

    # Optional system prompt files.
    system_prompt_path: Path | None = None
    append_system_prompt_path: Path | None = None

    # Extra directories allowed for tool access (translated to repeated `--add-dir`).
    add_dirs: list[Path] = field(default_factory=list)


def _as_str(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


def _as_path(v: Any, *, base: Path) -> Path | None:
    s = _as_str(v)
    if s is None:
        return None
    p = Path(s)
    return (base / p).resolve() if not p.is_absolute() else p


def _as_path_list(v: Any, *, base: Path) -> list[Path]:
    if not isinstance(v, list):
        return []
    out: list[Path] = []
    for item in v:
        p = _as_path(item, base=base)
        if p is not None:
            out.append(p)
    return out


def load_agent_config(*, repo_root: Path, agent_id: str) -> AgentConfig:
    """Load agents/<id>/agent.yaml if present; otherwise return defaults."""

    base = agent_dir(repo_root, agent_id)
    yaml_path = base / "agent.yaml"

    data: dict[str, Any] = {}
    if yaml_path.exists():
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded

    cfg = AgentConfig(agent_id=agent_id)

    cfg.model = _as_str(data.get("model"))
    cfg.permission_mode = _as_str(data.get("permission_mode")) or cfg.permission_mode
    cfg.policy_preset = _as_str(data.get("policy_preset")) or cfg.policy_preset

    cfg.system_prompt_path = _as_path(data.get("system_prompt_path"), base=repo_root)
    cfg.append_system_prompt_path = _as_path(data.get("append_system_prompt_path"), base=repo_root)
    cfg.add_dirs = _as_path_list(data.get("add_dirs"), base=repo_root)

    # Default system prompt paths if not specified.
    if cfg.system_prompt_path is None:
        p = base / "system_prompt.md"
        cfg.system_prompt_path = p if p.exists() else None

    if cfg.append_system_prompt_path is None:
        p = base / "append_system_prompt.md"
        cfg.append_system_prompt_path = p if p.exists() else None

    return cfg


def load_dotenv(path: Path) -> dict[str, str]:
    """Parse a minimal .env file (KEY=VALUE lines)."""

    if not path.exists():
        return {}

    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            env[k] = v
    return env


def merge_env(base: dict[str, str], override: dict[str, str]) -> dict[str, str]:
    out = dict(base)
    out.update(override)
    return out


def env_for_claude(*, dotenv: dict[str, str]) -> dict[str, str]:
    """Return process env for spawning `claude`.

    Precedence: existing process env wins; .env values fill in missing keys.
    """

    env = dict(os.environ)
    for k, v in dotenv.items():
        env.setdefault(k, v)
    return env
