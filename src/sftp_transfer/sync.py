"""Incremental transfer planning and execution."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from stat import S_ISREG
from typing import Iterable

from .models import FileInfo, RemoteFileInfo, TransferPlan, TransferStats
from .progress import ProgressPrinter
from .scanner import FileScanner, RemoteScanner
from .utils import join_remote_path, mtimes_close


class SyncManager:
    """Create transfer plans and execute them through an SFTP client."""

    def __init__(
        self,
        client,
        mtime_tolerance: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self.client = client
        self.mtime_tolerance = mtime_tolerance
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def plan_upload(
        self,
        local_files: Iterable[FileInfo],
        remote_files: Iterable[RemoteFileInfo],
    ) -> list[TransferPlan]:
        """Plan local-to-remote incremental upload."""

        remote_map = {item.relative_path: item for item in remote_files}
        plans: list[TransferPlan] = []
        for local in sorted(local_files, key=lambda item: item.relative_path):
            remote = remote_map.get(local.relative_path)
            if remote is None:
                plans.append(TransferPlan("new", local.relative_path, local, None, "missing remote"))
            elif local.size != remote.size:
                plans.append(TransferPlan("update", local.relative_path, local, remote, "size differs"))
            elif mtimes_close(local.mtime, remote.mtime, self.mtime_tolerance):
                plans.append(TransferPlan("skip", local.relative_path, local, remote, "same size and mtime"))
            else:
                plans.append(TransferPlan("update", local.relative_path, local, remote, "mtime differs"))
        return plans

    def plan_download(
        self,
        remote_files: Iterable[RemoteFileInfo],
        local_files: Iterable[FileInfo],
    ) -> list[TransferPlan]:
        """Plan remote-to-local incremental download."""

        local_map = {item.relative_path: item for item in local_files}
        plans: list[TransferPlan] = []
        for remote in sorted(remote_files, key=lambda item: item.relative_path):
            local = local_map.get(remote.relative_path)
            if local is None:
                plans.append(TransferPlan("download", remote.relative_path, None, remote, "missing local"))
            elif local.size != remote.size:
                plans.append(TransferPlan("download", remote.relative_path, local, remote, "size differs"))
            elif mtimes_close(local.mtime, remote.mtime, self.mtime_tolerance):
                plans.append(TransferPlan("skip", remote.relative_path, local, remote, "same size and mtime"))
            else:
                plans.append(TransferPlan("download", remote.relative_path, local, remote, "mtime differs"))
        return plans

    def upload(
        self,
        local_root: Path,
        remote_root: str,
        dry_run: bool = False,
    ) -> TransferStats:
        """Upload changed files from local_root to remote_root."""

        if local_root.is_file():
            return self._upload_single_file(local_root, remote_root, dry_run)
        local_files = FileScanner().scan(local_root)
        remote_files = self._scan_remote(remote_root)
        plans = self.plan_upload(local_files, remote_files)
        return self._execute_upload_plans(plans, remote_root, dry_run)

    def download(
        self,
        remote_root: str,
        local_root: Path,
        dry_run: bool = False,
    ) -> TransferStats:
        """Download changed files from remote_root to local_root."""

        if self._remote_is_file(remote_root):
            return self._download_single_file(remote_root, local_root, dry_run)
        local_files = FileScanner().scan(local_root) if local_root.exists() else []
        remote_files = self._scan_remote(remote_root)
        plans = self.plan_download(remote_files, local_files)
        return self._execute_download_plans(plans, local_root, dry_run)

    def sync(self, local_root: Path, remote_root: str, dry_run: bool = False) -> TransferStats:
        """Default sync: incremental upload without deleting remote files."""

        return self.upload(local_root, remote_root, dry_run=dry_run)

    def _scan_remote(self, remote_root: str) -> list[RemoteFileInfo]:
        if not self.client.exists(remote_root):
            return []
        return RemoteScanner(self.client).scan(remote_root)

    def _remote_is_file(self, remote_path: str) -> bool:
        try:
            return S_ISREG(self.client.stat(remote_path).st_mode)
        except OSError:
            return False

    def _upload_single_file(
        self,
        local_path: Path,
        remote_path: str,
        dry_run: bool,
    ) -> TransferStats:
        stat = local_path.stat()
        target = remote_path
        if remote_path.endswith("/"):
            target = join_remote_path(remote_path, local_path.name)
        plan = TransferPlan(
            "new",
            local_path.name,
            FileInfo(local_path.name, local_path, stat.st_size, stat.st_mtime),
            None,
            "single file",
        )
        return self._execute_upload_plans([plan], target.rsplit("/", 1)[0] or "/", dry_run)

    def _download_single_file(
        self,
        remote_path: str,
        local_path: Path,
        dry_run: bool,
    ) -> TransferStats:
        stat = self.client.stat(remote_path)
        relative = remote_path.rstrip("/").rsplit("/", 1)[-1]
        target = local_path / relative if local_path.exists() and local_path.is_dir() else local_path
        plan = TransferPlan(
            "download",
            target.name,
            None,
            RemoteFileInfo(target.name, remote_path, stat.st_size, float(stat.st_mtime)),
            "single file",
        )
        return self._execute_download_plans([plan], target.parent, dry_run)

    def _print_dry_run(self, plans: list[TransferPlan]) -> TransferStats:
        stats = TransferStats()
        for plan in plans:
            label = "SKIP" if plan.action == "skip" else plan.action.upper()
            print(f"{label:<8} {plan.relative_path}")
            if plan.action == "skip":
                stats.skipped += 1
        return stats

    def _execute_upload_plans(
        self,
        plans: list[TransferPlan],
        remote_root: str,
        dry_run: bool,
    ) -> TransferStats:
        if dry_run:
            return self._print_dry_run(plans)
        todo = [plan for plan in plans if plan.action in {"new", "update"}]
        stats = TransferStats(skipped=sum(1 for plan in plans if plan.action == "skip"))
        progress = ProgressPrinter(
            total_files=len(todo),
            total_bytes=sum(plan.local.size for plan in todo if plan.local),
            verb="Uploading",
        )
        failed: list[str] = []
        for plan in todo:
            assert plan.local is not None
            remote_path = join_remote_path(remote_root, plan.relative_path)
            progress.start_file(plan.relative_path, plan.local.size)
            try:
                self._retry(
                    lambda: self.client.upload_file(
                        plan.local.absolute_path,
                        remote_path,
                        callback=progress.callback,
                    ),
                    plan.relative_path,
                )
                progress.finish_file()
                stats.transferred += 1
                stats.bytes_transferred += plan.local.size
            except Exception as error:
                stats.failed += 1
                failed.append(plan.relative_path)
                self.logger.error("FAILED %s: %s", plan.relative_path, error)
        self._print_summary(stats, failed)
        return stats

    def _execute_download_plans(
        self,
        plans: list[TransferPlan],
        local_root: Path,
        dry_run: bool,
    ) -> TransferStats:
        if dry_run:
            return self._print_dry_run(plans)
        todo = [plan for plan in plans if plan.action == "download"]
        stats = TransferStats(skipped=sum(1 for plan in plans if plan.action == "skip"))
        progress = ProgressPrinter(
            total_files=len(todo),
            total_bytes=sum(plan.remote.size for plan in todo if plan.remote),
            verb="Downloading",
        )
        failed: list[str] = []
        for plan in todo:
            assert plan.remote is not None
            local_path = local_root / Path(plan.relative_path)
            progress.start_file(plan.relative_path, plan.remote.size)
            try:
                self._retry(
                    lambda: self.client.download_file(
                        plan.remote.remote_path,
                        local_path,
                        callback=progress.callback,
                    ),
                    plan.relative_path,
                )
                progress.finish_file()
                stats.transferred += 1
                stats.bytes_transferred += plan.remote.size
            except Exception as error:
                stats.failed += 1
                failed.append(plan.relative_path)
                self.logger.error("FAILED %s: %s", plan.relative_path, error)
        self._print_summary(stats, failed)
        return stats

    def _retry(self, func, relative_path: str) -> None:  # noqa: ANN001
        for attempt in range(1, self.max_retries + 1):
            try:
                func()
                return
            except Exception:
                if attempt >= self.max_retries:
                    raise
                self.logger.warning("Transfer failed: %s. Retry %s/%s...", relative_path, attempt, self.max_retries)
                time.sleep(min(2 ** (attempt - 1), 5))

    def _print_summary(self, stats: TransferStats, failed: list[str]) -> None:
        print(f"Transferred: {stats.transferred}")
        print(f"Skipped:     {stats.skipped}")
        print(f"Failed:      {stats.failed}")
        if failed:
            print("Failed files:")
            for item in failed:
                print(f"  {item}")
