from __future__ import annotations

from cc3.session import SessionManager


def test_session_manager_creates_session_json(tmp_path) -> None:
    sm = SessionManager(tmp_path)
    rec = sm.load_or_create("demo")

    assert rec.agent_id == "demo"
    assert rec.workspace_path.exists()
    assert (rec.workspace_path / "session.json").exists()


def test_session_manager_persists_session_id(tmp_path) -> None:
    sm = SessionManager(tmp_path)
    rec = sm.load_or_create("demo")
    rec.claude_session_id = "sid-1"
    sm.save(rec)

    rec2 = sm.load_or_create("demo")
    assert rec2.claude_session_id == "sid-1"
