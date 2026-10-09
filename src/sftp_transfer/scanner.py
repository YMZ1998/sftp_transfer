"""Local and remote file scanners."""

from __future__ import annotations

from pathlib import Path
from stat import S_ISDIR, S_ISREG

from .models import FileInfo, RemoteFileInfo
from .utils import join_remote_path


class FileScanner:
    """Scan local directories into FileInfo objects."""

    def scan(self, root: Path) -> list[FileInfo]:
        """Recursively scan regular files under root."""

        root = root.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(root)

        files: list[FileInfo] = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            stat = path.stat()
            relative = path.relative_to(root).as_posix()
            files.append(
                FileInfo(
                    relative_path=relative,
                    absolute_path=path,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                )
            )
        return files


class RemoteScanner:
    """Scan remote directories through an SftpClient-like object."""

    def __init__(self, client) -> None:
        self.client = client

    def scan(self, remote_root: str) -> list[RemoteFileInfo]:
        """Recursively scan regular remote files under remote_root."""

        files: list[RemoteFileInfo] = []
        self._scan_dir(remote_root.rstrip("/") or "/", "", files)
        return files

    def _scan_dir(
        self,
        current_dir: str,
        relative_dir: str,
        files: list[RemoteFileInfo],
    ) -> None:
        for entry in self.client.listdir_attr(current_dir):
            remote_path = join_remote_path(current_dir, entry.filename)
            relative_path = (
                entry.filename
                if not relative_dir
                else f"{relative_dir}/{entry.filename}"
            )
            if S_ISDIR(entry.st_mode):
                self._scan_dir(remote_path, relative_path, files)
            elif S_ISREG(entry.st_mode):
                files.append(
                    RemoteFileInfo(
                        relative_path=relative_path,
                        remote_path=remote_path,
                        size=entry.st_size,
                        mtime=float(entry.st_mtime),
                    )
                )

