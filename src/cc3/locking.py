from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout


@dataclass(frozen=True)
class LockHandle:
    lock: FileLock

    def release(self) -> None:
        if self.lock.is_locked:
            self.lock.release()


def workspace_lock(workspace: Path) -> FileLock:
    locks_dir = workspace / ".locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(locks_dir / "workspace.lock"))


def acquire_workspace_lock(workspace: Path, *, timeout_s: float) -> LockHandle:
    lock = workspace_lock(workspace)
    try:
        lock.acquire(timeout=timeout_s)
    except Timeout as e:
        raise TimeoutError(f"Workspace is locked: {lock.lock_file}") from e
    return LockHandle(lock=lock)
