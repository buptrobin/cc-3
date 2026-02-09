from __future__ import annotations

import io

from cc3.config import AgentConfig
from cc3.executor import ClaudeCliExecutor


class FakePopen:
    def __init__(
        self,
        argv,
        cwd=None,
        env=None,
        stdout=None,
        stderr=None,
        text=None,
        encoding=None,
        errors=None,
    ):
        self.argv = argv
        self.cwd = cwd
        self.env = env

        # Minimal stream-json fixture.
        self.stdout = io.StringIO(
            "\n".join(
                [
                    '{"type":"init","session_id":"sid-123","apiKeySource":"env"}',
                    '{"type":"delta","delta":"hello"}',
                    '{"type":"result","session_id":"sid-123","result_text":"OK","usage":{}}',
                    "",
                ]
            )
        )

        if stderr is not None:
            stderr.write("fake stderr\n")

        self._exit_code = 0

    def wait(self, timeout=None):
        return self._exit_code

    def kill(self):
        self._exit_code = 137


def test_executor_writes_artifacts(tmp_path, monkeypatch) -> None:
    # Arrange
    workspace = tmp_path / "workspaces" / "demo"
    (workspace / "kb").mkdir(parents=True)
    (workspace / "runs").mkdir(parents=True)

    monkeypatch.setattr("cc3.executor.subprocess.Popen", FakePopen)

    ex = ClaudeCliExecutor(repo_root=tmp_path, timeout_s=5.0, lock_timeout_s=1.0)
    cfg = AgentConfig(agent_id="demo", permission_mode="dontAsk", policy_preset="safe")

    # Act
    res = ex.execute(instruction="hi", workspace=workspace, cfg=cfg, session_id=None, fork=False)

    # Assert
    assert res.exit_code == 0
    assert res.session_id_after == "sid-123"
    assert res.final_text == "OK"

    assert (res.run_dir / "events.ndjson").exists()
    assert (res.run_dir / "events_norm.ndjson").exists()
    assert (res.run_dir / "meta.json").exists()
    assert (res.run_dir / "result.txt").exists()
    assert (res.run_dir / "step.json").exists()
    assert (res.run_dir / "stderr.log").exists()
