"""Configuration loading and merging."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """Runtime configuration resolved from JSON and CLI flags."""

    host: str | None = None
    port: int = 22
    username: str | None = None
    password: str | None = None
    private_key: Path | None = None
    local: Path | None = None
    remote: str | None = None
    no_host_key_check: bool = False
    max_retries: int = 3
    mtime_tolerance: float = 2.0


def load_config(path: Path | None) -> dict:
    """Load JSON configuration if path is provided."""

    if path is None:
        return {}
    with path.expanduser().open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object")
    return data


def resolve_config(args) -> AppConfig:  # noqa: ANN001
    """Merge config file values with argparse namespace; CLI wins."""

    raw = load_config(args.config)
    private_key = args.key or raw.get("private_key")
    remote = args.remote or raw.get("remote_root") or raw.get("remote")
    local = args.local or raw.get("local")
    return AppConfig(
        host=args.host or raw.get("host"),
        port=args.port or int(raw.get("port", 22)),
        username=args.username or raw.get("username"),
        password=args.password or raw.get("password") or None,
        private_key=Path(private_key).expanduser() if private_key else None,
        local=Path(local).expanduser() if local else None,
        remote=remote,
        no_host_key_check=args.no_host_key_check,
        max_retries=args.max_retries,
        mtime_tolerance=args.mtime_tolerance,
    )

