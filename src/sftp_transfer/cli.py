"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import AppConfig, resolve_config
from .sftp_client import SftpClient, SftpConnectionError, prompt_password_if_needed
from .sync import SyncManager

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_ARGUMENT_ERROR = 2
EXIT_CONNECTION_ERROR = 3


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add connection and behavior options to a parser."""

    parser.add_argument("--config", type=Path, help="Path to config.json")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument("--key", type=Path, help="SSH private key path")
    parser.add_argument("--no-host-key-check", action="store_true", help="UNSAFE: disable host key verification")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--mtime-tolerance", type=float, default=2.0)
    parser.add_argument("--delete", action="store_true", help="Delete remote files missing locally during upload/sync")
    parser.add_argument("--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""

    parser = argparse.ArgumentParser(prog="sftp-transfer")
    add_common_arguments(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("upload", "download", "sync"):
        sub = subparsers.add_parser(command, argument_default=argparse.SUPPRESS)
        add_common_arguments(sub)
        sub.add_argument("--local")
        sub.add_argument("--remote")
    return parser


def configure_logging(verbose: bool) -> None:
    """Configure standard logging."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("paramiko").setLevel(logging.DEBUG if verbose else logging.WARNING)


def validate_config(config: AppConfig) -> str | None:
    """Return an argument error message, if any."""

    if not config.host:
        return "--host is required"
    if not config.username:
        return "--username is required"
    if config.local is None:
        return "--local is required"
    if not config.remote:
        return "--remote is required"
    return None


def run_command(args) -> int:  # noqa: ANN001
    """Run one CLI command and return an exit code."""

    configure_logging(args.verbose)
    config = resolve_config(args)
    error = validate_config(config)
    if error:
        logging.error(error)
        return EXIT_ARGUMENT_ERROR

    assert config.host is not None
    assert config.username is not None
    assert config.local is not None
    assert config.remote is not None

    config.password = prompt_password_if_needed(
        config.password,
        config.private_key,
        password_stdin=args.password_stdin,
    )
    client = SftpClient(
        host=config.host,
        username=config.username,
        port=config.port,
        password=config.password,
        private_key=config.private_key,
        no_host_key_check=config.no_host_key_check,
    )
    try:
        client.connect()
    except SftpConnectionError as error:
        logging.error("Connection failed: %s", error)
        return EXIT_CONNECTION_ERROR

    try:
        manager = SyncManager(
            client,
            max_retries=config.max_retries,
            mtime_tolerance=config.mtime_tolerance,
        )
        if args.command == "upload":
            stats = manager.upload(config.local, config.remote, dry_run=args.dry_run, delete=config.delete)
        elif args.command == "download":
            stats = manager.download(config.remote, config.local, dry_run=args.dry_run)
        else:
            stats = manager.sync(config.local, config.remote, dry_run=args.dry_run, delete=config.delete)
    finally:
        client.close()

    return EXIT_PARTIAL_FAILURE if stats.failed else EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return run_command(args)
