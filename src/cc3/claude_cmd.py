from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import AgentConfig


@dataclass(frozen=True)
class ClaudeInvocation:
    argv: list[str]
    prompt: str


def tools_for_preset(preset: str) -> str:
    preset = (preset or "safe").lower()
    if preset == "safe":
        return "Read,Grep,Glob"
    if preset == "dev":
        return "Bash,Edit,Write,Read,Grep,Glob"
    if preset == "open":
        return "Bash,Edit,Write,Read,Grep,Glob,WebFetch,WebSearch"
    # Unknown preset: err on the safe side.
    return "Read,Grep,Glob"


def build_claude_argv(
    *,
    prompt: str,
    cfg: AgentConfig,
    resume: str | None,
    fork: bool,
    add_dirs: list[Path],
    system_prompt: str | None,
    append_system_prompt: str | None,
) -> ClaudeInvocation:
    argv: list[str] = [
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--permission-mode",
        cfg.permission_mode,
        "--tools",
        tools_for_preset(cfg.policy_preset),
    ]

    if cfg.model:
        argv.extend(["--model", cfg.model])

    if resume:
        argv.extend(["--resume", resume])
        if fork:
            argv.append("--fork-session")

    for d in add_dirs:
        argv.extend(["--add-dir", str(d)])

    if system_prompt:
        argv.extend(["--system-prompt", system_prompt])

    if append_system_prompt:
        argv.extend(["--append-system-prompt", append_system_prompt])

    # The prompt is a positional argument.
    argv.append(prompt)

    return ClaudeInvocation(argv=argv, prompt=prompt)
