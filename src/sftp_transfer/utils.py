"""Utility helpers for paths, sizes, and time comparisons."""

from __future__ import annotations

import posixpath
import time
from pathlib import PurePosixPath


def normalize_relative_path(relative_path: str) -> str:
    """Normalize any relative path to POSIX separators."""

    normalized = relative_path.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"Unsafe relative path: {relative_path!r}")
    return normalized


def join_remote_path(root: str, relative_path: str) -> str:
    """Join a remote POSIX root with a relative path."""

    relative = normalize_relative_path(relative_path)
    root_path = str(PurePosixPath(root))
    return posixpath.join(root_path, relative)


def remote_parent(path: str) -> str:
    """Return POSIX parent directory for a remote path."""

    return str(PurePosixPath(path).parent)


def mtimes_close(first: float, second: float, tolerance: float = 2.0) -> bool:
    """Return whether two modification times are equivalent enough."""

    return abs(first - second) <= tolerance


def format_bytes(size: float) -> str:
    """Format bytes using binary units."""

    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def format_eta(seconds: float | None) -> str:
    """Format an ETA in HH:MM:SS or MM:SS."""

    if seconds is None or seconds < 0:
        return "--:--"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def now() -> float:
    """Wrapper for time.time to ease tests."""

    return time.time()

