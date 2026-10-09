from pathlib import Path

from sftp_transfer.models import FileInfo, RemoteFileInfo
from sftp_transfer.sync import SyncManager


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.downloads = []
        self.deleted = []
        self.failures_left = 0

    def exists(self, remote_path: str) -> bool:
        return True

    def upload_file(self, local_path: Path, remote_path: str, callback=None):
        if self.failures_left:
            self.failures_left -= 1
            raise OSError("temporary")
        self.uploads.append((local_path, remote_path))
        if callback:
            callback(10, 10)

    def download_file(self, remote_path: str, local_path: Path, callback=None):
        self.downloads.append((remote_path, local_path))
        if callback:
            callback(10, 10)

    def remove_file(self, remote_path: str):
        self.deleted.append(remote_path)


def local(relative: str, size: int = 10, mtime: float = 100.0) -> FileInfo:
    return FileInfo(relative, Path(relative), size, mtime)


def remote(relative: str, size: int = 10, mtime: float = 100.0) -> RemoteFileInfo:
    return RemoteFileInfo(relative, f"/data/OCT/{relative}", size, mtime)


def test_plan_upload_new_update_skip():
    manager = SyncManager(FakeClient())
    plans = manager.plan_upload(
        [
            local("new.png"),
            local("size.png", size=20),
            local("mtime.png", mtime=200),
            local("same.png"),
        ],
        [
            remote("size.png", size=10),
            remote("mtime.png", mtime=100),
            remote("same.png"),
        ],
    )
    actions = {plan.relative_path: plan.action for plan in plans}
    assert actions == {
        "new.png": "new",
        "size.png": "update",
        "mtime.png": "update",
        "same.png": "skip",
    }


def test_plan_upload_does_not_delete_remote_only_file():
    manager = SyncManager(FakeClient())
    plans = manager.plan_upload([local("same.png")], [remote("same.png"), remote("remote-only.png")])
    assert [plan.relative_path for plan in plans] == ["same.png"]


def test_plan_upload_delete_remote_only_file_when_enabled():
    manager = SyncManager(FakeClient())
    plans = manager.plan_upload(
        [local("same.png")],
        [remote("same.png"), remote("remote-only.png")],
        delete=True,
    )
    actions = {plan.relative_path: plan.action for plan in plans}
    assert actions == {"same.png": "skip", "remote-only.png": "delete"}


def test_dry_run_does_not_upload(capsys):
    client = FakeClient()
    manager = SyncManager(client)
    stats = manager._execute_upload_plans(
        [manager.plan_upload([local("new.png")], [])[0]],
        "/data/OCT",
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert "NEW" in captured.out
    assert client.uploads == []
    assert stats.failed == 0


def test_retry_eventually_uploads():
    client = FakeClient()
    client.failures_left = 1
    manager = SyncManager(client, max_retries=2)
    plan = manager.plan_upload([local("new.png")], [])[0]
    stats = manager._execute_upload_plans([plan], "/data/OCT", dry_run=False)
    assert stats.transferred == 1
    assert client.uploads[0][1] == "/data/OCT/new.png"


def test_execute_upload_plans_deletes_remote_only_file():
    client = FakeClient()
    manager = SyncManager(client)
    plan = manager.plan_upload([], [remote("old.png")], delete=True)[0]
    stats = manager._execute_upload_plans([plan], "/data/OCT", dry_run=False)
    assert stats.deleted == 1
    assert client.deleted == ["/data/OCT/old.png"]
