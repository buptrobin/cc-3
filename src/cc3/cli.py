from __future__ import annotations

from pathlib import Path

import typer

from .config import load_agent_config
from .executor import ClaudeCliExecutor
from .orchestrator.graph import build_graph
from .paths import find_repo_root
from .scaffold import init_agent as init_agent_scaffold
from .session import SessionManager

app = typer.Typer(add_completion=False, help="cc3: LangGraph + Claude Code CLI executor")


@app.command("init-agent")
def init_agent(
    agent_id: str = typer.Argument(..., help="Agent identifier (directory name)"),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repository root (defaults to auto-detect via pyproject.toml)",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing templates"),
) -> None:
    repo_root = (root.resolve() if root else find_repo_root())

    try:
        result = init_agent_scaffold(repo_root=repo_root, agent_id=agent_id, overwrite=overwrite)
    except FileExistsError as e:
        typer.secho(f"Refusing to overwrite existing file: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=2) from e

    typer.secho(f"Created agent scaffold: {result.agent_path}", fg=typer.colors.GREEN)
    typer.secho(f"Created workspace scaffold: {result.workspace_path}", fg=typer.colors.GREEN)


@app.command()
def run(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent id under agents/<id>"),
    goal: str = typer.Option(..., "--goal", help="User goal/prompt to execute"),
    mode: str = typer.Option("safe", "--mode", help="Policy preset: safe|dev|open"),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Repository root (defaults to auto-detect via pyproject.toml)",
    ),
    resume: str | None = typer.Option(None, "--resume", help="Override stored session id"),
    fork: bool = typer.Option(False, "--fork", help="Fork a session (requires resume id)"),
    timeout_s: float = typer.Option(600.0, "--timeout-s", help="Kill claude run after this many seconds"),
    lock_timeout_s: float = typer.Option(30.0, "--lock-timeout-s", help="Seconds to wait for workspace lock"),
) -> None:
    repo_root = (root.resolve() if root else find_repo_root())

    sm = SessionManager(repo_root)
    rec = sm.load_or_create(agent)

    cfg = load_agent_config(repo_root=repo_root, agent_id=agent)
    cfg.policy_preset = mode

    # Default to stored session id unless overridden.
    session_id = resume if resume is not None else rec.claude_session_id
    if fork and not session_id:
        typer.secho("--fork requires an existing session id (use --resume or run once first)", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    executor = ClaudeCliExecutor(repo_root=repo_root, timeout_s=timeout_s, lock_timeout_s=lock_timeout_s)
    graph = build_graph(executor=executor, cfg=cfg, workspace=rec.workspace_path)

    final_state = graph.invoke(
        {
            "agent_id": agent,
            "workspace_path": str(rec.workspace_path),
            "goal": goal,
            "claude_session_id": session_id,
            "fork": fork,
        }
    )

    rec.claude_session_id = final_state.get("claude_session_id")
    sm.save(rec)

    typer.echo(final_state.get("final_text", ""))
    run_dir = final_state.get("run_dir")
    if run_dir:
        typer.secho(f"Artifacts: {run_dir}", fg=typer.colors.GREEN)


def main() -> None:
    # Entry point for console script.
    app()


if __name__ == "__main__":
    main()
