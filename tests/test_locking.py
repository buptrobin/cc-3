from __future__ import annotations

from cc3.locking import acquire_workspace_lock


def test_workspace_lock_blocks(tmp_path) -> None:
    w = tmp_path / "workspace"
    w.mkdir()

    h1 = acquire_workspace_lock(w, timeout_s=0.1)
    try:
        raised = False
        try:
            acquire_workspace_lock(w, timeout_s=0.1)
        except TimeoutError:
            raised = True
        assert raised
    finally:
        h1.release()
