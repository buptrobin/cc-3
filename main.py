from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Convenience shim when running from repo root.
    # Prefer `python -m cc3 ...` or the `cc3` console script after installation.
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from cc3.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
