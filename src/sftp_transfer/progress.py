"""Terminal progress display helpers with throttled output."""

from __future__ import annotations

import sys
import time
from shutil import get_terminal_size

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

    def close(self) -> None:
        """Finish the progress line."""

        sys.stderr.write("\n")
        sys.stderr.flush()

    def _bar(self, ratio: float, width: int = 100) -> str:
        ratio = min(1.0, max(0.0, ratio))
        filled = int(ratio * width)
        # return "[" + "#" * filled + "-" * (width - filled) + "]"
        return "[" + "█" * filled + "░" * (width - filled) + "]"

    def _shorten(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        if max_length <= 3:
            return text[:max_length]
        return "..." + text[-(max_length - 3) :]

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

        overall_ratio = self.bytes_done / self.total_bytes if self.total_bytes else 0.0
        prefix = (
            f"\r{self.verb} {self._bar(overall_ratio)} {overall_ratio * 100:5.1f}% "
            f"{self.files_done}/{self.total_files} "
            f"{format_bytes(self.bytes_done)}/{format_bytes(self.total_bytes)} "
            f"{format_bytes(speed)}/s ETA {format_eta(remaining)} "
        )
        width = max(60, get_terminal_size((120, 20)).columns)
        file_width = max(12, width - len(prefix) - 1)
        text = prefix + self._shorten(self._file_name, file_width)
        sys.stderr.write("\r" + text.ljust(width - 1))
        sys.stderr.flush()
