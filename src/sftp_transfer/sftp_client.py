"""Paramiko-backed SFTP client wrapper."""

from __future__ import annotations

import getpass
import logging
from pathlib import Path
from typing import Callable

import paramiko

from .utils import remote_parent

ProgressCallback = Callable[[int, int], None]


class SftpConnectionError(RuntimeError):
    """Raised when SSH/SFTP connection setup fails."""


class PromptingMissingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Prompt before accepting an unknown host key."""

    def missing_host_key(self, client, hostname, key) -> None:  # noqa: ANN001
        fingerprint = key.get_fingerprint().hex(":")
        answer = input(
            f"Unknown host key for {hostname} ({key.get_name()} {fingerprint}). "
            "Accept? [y/N] "
        )
        if answer.strip().lower() not in {"y", "yes"}:
            raise SftpConnectionError(f"Host key rejected for {hostname}")
        client.get_host_keys().add(hostname, key.get_name(), key)


class SftpClient:
    """High-level SFTP wrapper hiding Paramiko details from sync code."""

    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: str | None = None,
        private_key: Path | None = None,
        no_host_key_check: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.private_key = private_key.expanduser() if private_key else None
        self.no_host_key_check = no_host_key_check
        self.timeout = timeout
        self._ssh: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self.logger = logging.getLogger(__name__)

    def connect(self) -> None:
        """Open SSH and SFTP sessions."""

        self.logger.info("Connecting to %s:%s", self.host, self.port)
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        if self.no_host_key_check:
            self.logger.warning(
                "--no-host-key-check is enabled; host key verification is unsafe"
            )
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            ssh.set_missing_host_key_policy(PromptingMissingHostKeyPolicy())

        pkey = None
        if self.private_key:
            pkey = paramiko.RSAKey.from_private_key_file(str(self.private_key))

        try:
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                pkey=pkey,
                timeout=self.timeout,
                banner_timeout=self.timeout,
                auth_timeout=self.timeout,
            )
            self._sftp = ssh.open_sftp()
            self._ssh = ssh
            self.logger.info("Authentication successful")
        except Exception as error:
            ssh.close()
            raise SftpConnectionError(str(error)) from error

    def close(self) -> None:
        """Close open SFTP and SSH sessions."""

        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    @property
    def sftp(self) -> paramiko.SFTPClient:
        """Return active Paramiko SFTP object."""

        if self._sftp is None:
            raise SftpConnectionError("SFTP client is not connected")
        return self._sftp

    def exists(self, remote_path: str) -> bool:
        """Return whether remote path exists."""

        try:
            self.sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def stat(self, remote_path: str):
        """Return remote stat result."""

        return self.sftp.stat(remote_path)

    def listdir_attr(self, remote_dir: str):
        """Return Paramiko directory entries for remote_dir."""

        return self.sftp.listdir_attr(remote_dir)

    def mkdir_p(self, remote_path: str) -> None:
        """Create a remote directory and missing parents."""

        normalized = remote_path.replace("\\", "/").rstrip("/")
        if not normalized or normalized == ".":
            return
        parts = [part for part in normalized.split("/") if part]
        current = "/" if normalized.startswith("/") else ""
        for part in parts:
            current = f"{current.rstrip('/')}/{part}" if current else part
            if not self.exists(current):
                self.sftp.mkdir(current)

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        callback: ProgressCallback | None = None,
    ) -> None:
        """Upload one local file, creating remote parents."""

        self.mkdir_p(remote_parent(remote_path))
        self.sftp.put(str(local_path), remote_path, callback=callback)

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        callback: ProgressCallback | None = None,
    ) -> None:
        """Download one remote file, creating local parents."""

        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.sftp.get(remote_path, str(local_path), callback=callback)

    def remove_file(self, remote_path: str) -> None:
        """Delete one remote file."""

        self.sftp.remove(remote_path)


def prompt_password_if_needed(
    password: str | None,
    private_key: Path | None,
    password_stdin: bool = False,
) -> str | None:
    """Resolve password from args, stdin, or interactive prompt."""

    if password:
        return password
    if password_stdin:
        return input().rstrip("\n")
    if private_key:
        return None
    return getpass.getpass("Password: ")
