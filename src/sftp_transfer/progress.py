"""Terminal progress display helpers with throttled output."""

from __future__ import annotations

import sys
import time

from .utils import format_bytes, format_eta


class ProgressPrinter:
    """Render file and overall progress without flooding the terminal."""

    def __init__(
        self,
        total_files: int,
        total_bytes: int,
        interval: float = 0.5,
        verb: str = "Uploading",
    ) -> None:
        self.total_files = max(1, total_files)
        self.total_bytes = max(0, total_bytes)
        self.interval = interval
        self.verb = verb
        self.files_done = 0
        self.bytes_done = 0
        self._last_print = 0.0
        self._start = time.time()
        self._file_start = self._start
        self._file_name = ""
        self._file_done = 0
        self._file_total = 0

    def start_file(self, relative_path: str, size: int) -> None:
        """Start tracking a file transfer."""

        self._file_name = relative_path
        self._file_total = max(1, size)
        self._file_done = 0
        self._file_start = time.time()
        self._print(force=True)

    def callback(self, done: int, total: int) -> None:
        """Paramiko callback for a single file."""

        previous = self._file_done
        self._file_done = done
        self._file_total = max(1, total)
        self.bytes_done += max(0, done - previous)
        self._print()

    def finish_file(self) -> None:
        """Mark current file as complete."""

        if self._file_done < self._file_total:
            self.bytes_done += self._file_total - self._file_done
        self.files_done += 1
        self._file_done = self._file_total
        self._print(force=True)

    def _bar(self, ratio: float, width: int = 20) -> str:
        ratio = min(1.0, max(0.0, ratio))
        filled = int(ratio * width)
        return "[" + "█" * filled + "░" * (width - filled) + "]"

    def _print(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_print < self.interval:
            return
        self._last_print = now
        elapsed = max(0.001, now - self._start)
        speed = self.bytes_done / elapsed
        remaining = None
        if speed > 0 and self.total_bytes:
            remaining = max(0.0, (self.total_bytes - self.bytes_done) / speed)

        file_ratio = self._file_done / max(1, self._file_total)
        overall_ratio = self.bytes_done / self.total_bytes if self.total_bytes else 0.0
        text = (
            f"\r{self.verb}: {self._file_name}\n"
            f"{self._bar(file_ratio)} {file_ratio * 100:5.1f}% "
            f"{format_bytes(self._file_done)} / {format_bytes(self._file_total)}\n"
            f"Overall {self._bar(overall_ratio)} {overall_ratio * 100:5.1f}% "
            f"Files {self.files_done}/{self.total_files} "
            f"Transferred {format_bytes(self.bytes_done)} / {format_bytes(self.total_bytes)} "
            f"Speed {format_bytes(speed)}/s ETA {format_eta(remaining)}\n"
        )
        sys.stderr.write("\033[2K" + text)
        sys.stderr.flush()
