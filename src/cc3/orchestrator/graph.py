from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..config import AgentConfig
from ..executor import ClaudeCliExecutor


class AgentState(TypedDict, total=False):
    agent_id: str
    workspace_path: str

    goal: str
    instruction: str

    claude_session_id: str | None
    fork: bool

    run_id: str
    run_dir: str

    final_text: str


def build_graph(*, executor: ClaudeCliExecutor, cfg: AgentConfig, workspace: Path) -> Any:
    """Build the minimal START -> Planner -> Exec -> END LangGraph."""

    def planner_node(state: AgentState) -> AgentState:
        # MVP planner: one step equals the goal.
        return {**state, "instruction": state["goal"]}

    def exec_node(state: AgentState) -> AgentState:
        res = executor.execute(
            instruction=state["instruction"],
            workspace=workspace,
            cfg=cfg,
            session_id=state.get("claude_session_id"),
            fork=bool(state.get("fork")),
        )
        return {
            **state,
            "claude_session_id": res.session_id_after,
            "run_id": res.run_id,
            "run_dir": str(res.run_dir),
            "final_text": res.final_text,
        }

    g: StateGraph = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("exec", exec_node)
    g.set_entry_point("planner")
    g.add_edge("planner", "exec")
    g.add_edge("exec", END)
    return g.compile()
