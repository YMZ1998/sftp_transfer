from sftp_transfer.scanner import FileScanner


def test_file_scanner_returns_relative_posix_paths(tmp_path):
    root = tmp_path / "data"
    nested = root / "01"
    nested.mkdir(parents=True)
    file_path = nested / "image001.png"
    file_path.write_bytes(b"abc")

    files = FileScanner().scan(root)

    assert len(files) == 1
    assert files[0].relative_path == "01/image001.png"
    assert files[0].absolute_path == file_path
    assert files[0].size == 3

