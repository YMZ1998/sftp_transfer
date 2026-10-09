# SFTP Transfer

LAN file transfer and incremental synchronization tool based on Python and Paramiko.

It is designed for moving many OCT image files between a Windows workstation and a Linux/Windows SSH server.

## Requirements

- Python >= 3.10
- Paramiko
- An SSH server on the remote machine

## Install

```bash
cd sftp_transfer
pip install -e .
```

## Direct Launch Scripts

You can run the tool without remembering the module name:

```bash
python run.py --help
```

On Windows:

```bat
run_sftp_transfer.bat --help
```

Editable examples are included:

```text
sync_example.bat
upload_example.bat
download_example.bat
run_sftp_transfer_gui.bat
```

Open these files, edit `HOST`, `USERNAME`, `LOCAL`, and `REMOTE`, then double-click or run them from `cmd`.

## GUI

Start the PyQt desktop interface:

```bat
python run_gui.py
```

Or double-click:

```text
run_sftp_transfer_gui.bat
```

The GUI supports upload, download, sync, dry-run preview, remote-only delete for upload/sync, stop, and live logs.

If PyQt5 is not installed:

```bash
pip install -e .[gui]
```

For tests:

```bash
pip install -e .[test]
pytest
```

## SSH Server Notes

Linux usually provides OpenSSH server through the system package manager.

Windows can enable OpenSSH Server from Optional Features, then start the `sshd` service.

Make sure the target account can read/write the remote directory.

## Password Login

```bash
python -m sftp_transfer upload \
  --host 192.168.1.200 \
  --username oct \
  --password 123456 \
  --local D:\Data\OCT \
  --remote /data/OCT
```

If no password or key is given, the tool prompts interactively without echo.

## SSH Key Login

```bash
python -m sftp_transfer upload \
  --host 192.168.1.200 \
  --username oct \
  --key C:\Users\user\.ssh\id_rsa \
  --local D:\Data\OCT \
  --remote /data/OCT
```

## Commands

Upload local changes:

```bash
python -m sftp_transfer upload --host 192.168.1.200 --username oct --local D:\Data\OCT --remote /data/OCT
```

Download remote changes:

```bash
python -m sftp_transfer download --host 192.168.1.200 --username oct --remote /data/OCT --local D:\Data\OCT
```

Sync is incremental upload by default. It never deletes remote files:

```bash
python -m sftp_transfer sync --host 192.168.1.200 --username oct --local D:\Data\OCT --remote /data/OCT
```

Mirror local files to the remote directory and delete remote files that no longer exist locally:

```bash
python -m sftp_transfer sync --host 192.168.1.200 --username oct --local D:\Data\OCT --remote /data/OCT --delete
```

Run with `--dry-run --delete` first to review the delete list before changing remote files.

## Dry Run

```bash
python -m sftp_transfer sync \
  --host 192.168.1.200 \
  --username oct \
  --local D:\Data\OCT \
  --remote /data/OCT \
  --dry-run
```

Example output:

```text
NEW      01/image001.png
UPDATE   01/image002.png
SKIP     01/image003.png
DELETE   01/removed.png
```

## Config File

Copy `config.example.json` to `config.json`.

```json
{
  "host": "192.168.1.200",
  "port": 22,
  "username": "oct",
  "password": "",
  "private_key": "C:/Users/user/.ssh/id_rsa",
  "remote_root": "/data/OCT"
}
```

CLI arguments override config values:

```bash
python -m sftp_transfer --config config.json sync --local D:\Data\OCT
```

Avoid saving passwords in config files. Prefer interactive input, `--password-stdin`, or SSH keys.

## Security

The default behavior loads system known hosts and prompts before accepting an unknown host key.

`--no-host-key-check` is available for local testing but is unsafe and should not be used for untrusted networks.

## Logging

Use `--verbose` for DEBUG logging:

```bash
python -m sftp_transfer --verbose sync ...
```

## Common Errors

- `Host key rejected`: add the server to `known_hosts` or accept the prompt.
- `Permission denied`: check username, password/key, and server directory permissions.
- `No such file`: verify the local and remote paths.
- Slow transfer: many small files have overhead. First version is single-threaded by design.

## Performance

The first version uses one SFTP connection and throttled terminal progress output.

It is suitable for many small files and tens of GB on a LAN. The code is structured so future versions can add `--workers 4` without rewriting sync planning.
