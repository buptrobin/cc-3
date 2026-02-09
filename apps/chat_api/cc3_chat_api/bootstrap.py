from __future__ import annotations

import sys
from pathlib import Path


def ensure_cc3_importable() -> Path:
    """Ensure `import cc3` works when running the API without installing the package."""

    repo_root = Path(__file__).resolve().parents[3]
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    return repo_root
