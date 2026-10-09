"""PyQt GUI for the SFTP transfer tool."""

from __future__ import annotations

import sys
import os
from configparser import ConfigParser
from pathlib import Path

try:
    from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt
    from PyQt5.QtGui import QTextCursor
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError as error:  # pragma: no cover - exercised manually.
    raise SystemExit("PyQt5 is required. Install with: pip install PyQt5") from error


class MainWindow(QMainWindow):
    """Small desktop wrapper around the command-line transfer engine."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SFTP Transfer")
        self.resize(980, 680)
        self.process: QProcess | None = None
        self.config_path = Path(__file__).resolve().parents[2] / "config.ini"

        self.command_combo = QComboBox()
        self.command_combo.addItems(["sync", "upload", "download"])

        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.key_edit = QLineEdit()

        self.local_edit = QLineEdit()
        self.remote_edit = QLineEdit()
        self.dry_run_check = QCheckBox("Dry run")
        self.delete_check = QCheckBox("Delete remote-only files")
        self.delete_check.setToolTip("Only applies to upload/sync. Run dry-run first before deleting.")
        self.no_host_key_check = QCheckBox("Skip host key check")
        self.verbose_check = QCheckBox("Verbose log")

        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.clear_button = QPushButton("Clear Log")

        self._build_layout()
        self._connect_signals()
        self._load_config()
        self._update_preview()

    def _build_layout(self) -> None:
        root = QWidget()
        main_layout = QVBoxLayout(root)

        connection = QGroupBox("Connection")
        connection_form = QFormLayout(connection)
        connection_form.addRow("Command", self.command_combo)
        connection_form.addRow("Host", self.host_edit)
        connection_form.addRow("Port", self.port_spin)
        connection_form.addRow("Username", self.username_edit)
        connection_form.addRow("Password", self.password_edit)

        key_row = QHBoxLayout()
        key_row.addWidget(self.key_edit)
        key_button = QPushButton("Browse")
        key_button.clicked.connect(self._browse_key)
        key_row.addWidget(key_button)
        connection_form.addRow("Private key", key_row)

        paths = QGroupBox("Paths")
        path_grid = QGridLayout(paths)
        path_grid.addWidget(QLabel("Local"), 0, 0)
        path_grid.addWidget(self.local_edit, 0, 1)
        local_file_button = QPushButton("File")
        local_dir_button = QPushButton("Folder")
        local_file_button.clicked.connect(self._browse_local_file)
        local_dir_button.clicked.connect(self._browse_local_dir)
        path_grid.addWidget(local_file_button, 0, 2)
        path_grid.addWidget(local_dir_button, 0, 3)
        path_grid.addWidget(QLabel("Remote"), 1, 0)
        path_grid.addWidget(self.remote_edit, 1, 1, 1, 3)

        options = QGroupBox("Options")
        option_layout = QHBoxLayout(options)
        option_layout.addWidget(self.dry_run_check)
        option_layout.addWidget(self.delete_check)
        option_layout.addWidget(self.no_host_key_check)
        option_layout.addWidget(self.verbose_check)
        option_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.clear_button)
        actions.addStretch(1)

        main_layout.addWidget(connection)
        main_layout.addWidget(paths)
        main_layout.addWidget(options)
        main_layout.addWidget(QLabel("Command preview"))
        main_layout.addWidget(self.command_preview)
        main_layout.addLayout(actions)
        main_layout.addWidget(self.output, 1)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        widgets = [
            self.command_combo,
            self.host_edit,
            self.username_edit,
            self.password_edit,
            self.key_edit,
            self.local_edit,
            self.remote_edit,
        ]
        for widget in widgets:
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._update_preview)
            else:
                widget.textChanged.connect(self._update_preview)

        self.port_spin.valueChanged.connect(self._update_preview)
        for checkbox in (self.dry_run_check, self.delete_check, self.no_host_key_check, self.verbose_check):
            checkbox.stateChanged.connect(self._update_preview)

        self.command_combo.currentTextChanged.connect(self._update_delete_enabled)
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        self.clear_button.clicked.connect(self.output.clear)

    def _build_args(self) -> list[str]:
        args = [
            self.command_combo.currentText(),
            "--host",
            self.host_edit.text().strip(),
            "--port",
            str(self.port_spin.value()),
            "--username",
            self.username_edit.text().strip(),
        ]
        password = self.password_edit.text()
        key = self.key_edit.text().strip()
        if key:
            args.extend(["--key", key])
        elif password:
            args.append("--password-stdin")
        if self.dry_run_check.isChecked():
            args.append("--dry-run")
        if self.delete_check.isChecked() and self.command_combo.currentText() in {"sync", "upload"}:
            args.append("--delete")
        if self.no_host_key_check.isChecked():
            args.append("--no-host-key-check")
        if self.verbose_check.isChecked():
            args.append("--verbose")
        args.extend(["--local", self.local_edit.text().strip()])
        args.extend(["--remote", self.remote_edit.text().strip()])
        return args

    def _validate(self) -> bool:
        missing = []
        if not self.host_edit.text().strip():
            missing.append("Host")
        if not self.username_edit.text().strip():
            missing.append("Username")
        if not self.password_edit.text() and not self.key_edit.text().strip():
            missing.append("Password or private key")
        if not self.local_edit.text().strip():
            missing.append("Local")
        if not self.remote_edit.text().strip():
            missing.append("Remote")
        if missing:
            QMessageBox.warning(self, "Missing fields", "Please fill: " + ", ".join(missing))
            return False
        if self.delete_check.isChecked() and not self.dry_run_check.isChecked():
            answer = QMessageBox.question(
                self,
                "Confirm delete",
                "This will delete remote files that do not exist locally. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return answer == QMessageBox.Yes
        return True

    def _start(self) -> None:
        if self.process is not None:
            return
        if not self._validate():
            return
        self._save_config()

        self.process = QProcess(self)
        self.process.setProgram(sys.executable)
        self.process.setArguments(["-m", "sftp_transfer", *self._build_args()])
        env = QProcessEnvironment.systemEnvironment()
        src_path = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = env.value("PYTHONPATH")
        env.insert("PYTHONPATH", src_path if not existing_pythonpath else src_path + os.pathsep + existing_pythonpath)
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

        self.output.appendPlainText("$ " + self.command_preview.text())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.process.start()
        if self.process.waitForStarted(3000):
            password = self.password_edit.text()
            if password and not self.key_edit.text().strip():
                self.process.write((password + "\n").encode())
            self.process.closeWriteChannel()

    def _stop(self) -> None:
        if self.process is None:
            return
        self.output.appendPlainText("\nStopping...")
        self.process.terminate()
        if not self.process.waitForFinished(3000):
            self.process.kill()

    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        self.output.appendPlainText(f"\nFinished with exit code {exit_code}")
        self.process = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _process_error(self, error: QProcess.ProcessError) -> None:
        self.output.appendPlainText(f"\nProcess error: {error}")

    def _read_output(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if data:
            cursor = self.output.textCursor()
            cursor.movePosition(QTextCursor.End)
            for char in data:
                if char == "\r":
                    cursor.movePosition(QTextCursor.End)
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.select(QTextCursor.LineUnderCursor)
                    cursor.removeSelectedText()
                else:
                    cursor.insertText(char)
            self.output.setTextCursor(cursor)
            self.output.ensureCursorVisible()

    def _update_preview(self) -> None:
        command = [sys.executable, "-m", "sftp_transfer", *self._build_args()]
        self.command_preview.setText(" ".join(f'"{item}"' if " " in item else item for item in command))

    def _update_delete_enabled(self) -> None:
        self.delete_check.setEnabled(self.command_combo.currentText() in {"sync", "upload"})
        self._update_preview()

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select private key")
        if path:
            self.key_edit.setText(path)

    def _browse_local_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select local file")
        if path:
            self.local_edit.setText(path)

    def _browse_local_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select local folder")
        if path:
            self.local_edit.setText(path)

    def _load_config(self) -> None:
        if not self.config_path.exists():
            return
        parser = ConfigParser()
        parser.read(self.config_path, encoding="utf-8")
        self.command_combo.setCurrentText(parser.get("options", "command", fallback="sync"))
        self.host_edit.setText(parser.get("connection", "host", fallback=""))
        self.port_spin.setValue(parser.getint("connection", "port", fallback=22))
        self.username_edit.setText(parser.get("connection", "username", fallback=""))
        self.password_edit.setText(parser.get("connection", "password", fallback=""))
        self.key_edit.setText(parser.get("connection", "private_key", fallback=""))
        self.local_edit.setText(parser.get("paths", "local", fallback=""))
        self.remote_edit.setText(parser.get("paths", "remote", fallback=""))
        self.dry_run_check.setChecked(parser.getboolean("options", "dry_run", fallback=False))
        self.delete_check.setChecked(parser.getboolean("options", "delete", fallback=False))
        self.no_host_key_check.setChecked(parser.getboolean("options", "no_host_key_check", fallback=False))
        self.verbose_check.setChecked(parser.getboolean("options", "verbose", fallback=False))
        self._update_delete_enabled()

    def _save_config(self) -> None:
        parser = ConfigParser()
        parser["connection"] = {
            "host": self.host_edit.text().strip(),
            "port": str(self.port_spin.value()),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "private_key": self.key_edit.text().strip(),
        }
        parser["paths"] = {
            "local": self.local_edit.text().strip(),
            "remote": self.remote_edit.text().strip(),
        }
        parser["options"] = {
            "command": self.command_combo.currentText(),
            "dry_run": str(self.dry_run_check.isChecked()).lower(),
            "delete": str(self.delete_check.isChecked()).lower(),
            "no_host_key_check": str(self.no_host_key_check.isChecked()).lower(),
            "verbose": str(self.verbose_check.isChecked()).lower(),
        }
        with self.config_path.open("w", encoding="utf-8") as file:
            parser.write(file)


def main() -> int:
    """Run the GUI application."""

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
