"""Resolve application data and static paths locally and in Cloud Run."""

from __future__ import annotations

import os
from pathlib import Path


def find_app_root() -> Path:
    """Locate the directory containing data/ and static/."""

    configured_root = os.getenv("APP_ROOT")

    candidates = [
        Path(configured_root) if configured_root else None,
        Path.cwd(),
        Path(__file__).resolve().parents[2],
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        resolved = candidate.resolve()

        if (resolved / "data").is_dir() and (resolved / "static").is_dir():
            return resolved

    raise RuntimeError(
        "Application root could not be located. Expected data/ and static/ "
        "directories. Set APP_ROOT to the deployed application directory."
    )


APP_ROOT = find_app_root()
DATA_DIR = APP_ROOT / "data"
STATIC_DIR = APP_ROOT / "static"