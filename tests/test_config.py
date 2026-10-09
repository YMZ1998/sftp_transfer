import argparse
import json
from pathlib import Path

from sftp_transfer.cli import EXIT_ARGUMENT_ERROR, run_command
from sftp_transfer.config import resolve_config


def namespace(**overrides):
    values = {
        "config": None,
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "password_stdin": False,
        "key": None,
        "local": None,
        "remote": None,
        "no_host_key_check": False,
        "max_retries": 3,
        "mtime_tolerance": 2.0,
        "verbose": False,
        "command": "sync",
        "dry_run": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_cli_overrides_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "host": "1.1.1.1",
                "port": 22,
                "username": "oct",
                "remote_root": "/data/OCT",
            }
        ),
        encoding="utf-8",
    )
    config = resolve_config(
        namespace(
            config=config_path,
            host="2.2.2.2",
            local=str(tmp_path),
        )
    )
    assert config.host == "2.2.2.2"
    assert config.username == "oct"
    assert config.remote == "/data/OCT"
    assert config.local == tmp_path


def test_missing_required_argument_returns_argument_error():
    code = run_command(namespace(host=None, username="oct", local=".", remote="/data/OCT"))
    assert code == EXIT_ARGUMENT_ERROR

