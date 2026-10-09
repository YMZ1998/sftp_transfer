"""Shared dataclasses used by scanners and sync logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Action = Literal["new", "update", "skip", "download"]


@dataclass(frozen=True)
class FileInfo:
    """Local file metadata relative to a scan root."""

    relative_path: str
    absolute_path: Path
    size: int
    mtime: float


@dataclass(frozen=True)
class RemoteFileInfo:
    """Remote file metadata relative to a remote scan root."""

    relative_path: str
    remote_path: str
    size: int
    mtime: float


@dataclass(frozen=True)
class TransferPlan:
    """A planned transfer decision for one relative path."""

    action: Action
    relative_path: str
    local: FileInfo | None = None
    remote: RemoteFileInfo | None = None
    reason: str = ""


@dataclass
class TransferStats:
    """Summary counters for one command execution."""

    transferred: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_transferred: int = 0

