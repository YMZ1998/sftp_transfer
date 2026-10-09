from pathlib import Path

import pytest

from sftp_transfer.utils import join_remote_path, normalize_relative_path


def test_normalize_windows_relative_path():
    assert normalize_relative_path(r"01\image001.png") == "01/image001.png"


def test_reject_unsafe_relative_path():
    with pytest.raises(ValueError):
        normalize_relative_path("../secret.txt")


def test_join_remote_path_uses_posix_separator():
    assert join_remote_path("/data/OCT", r"01\image001.png") == "/data/OCT/01/image001.png"


def test_pathlib_windows_style_does_not_affect_remote_join():
    path = Path("01") / "image001.png"
    assert join_remote_path("/data/OCT", str(path)) == "/data/OCT/01/image001.png"

