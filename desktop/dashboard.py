from __future__ import annotations

import asyncio
import os
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.api_client import DexterAPIClient
from desktop.config import DexterConfig


class DexterDashboard(QMainWindow):
    def __init__(self, api: DexterAPIClient, config: DexterConfig) -> None:
        super().__init__()
        self.api = api
        self.config = config
        self._current_task_id: str | None = None
        self.setWindowTitle("Dexter Dashboard")
        self.resize(1100, 700)
        self.setStyleSheet(
            "QMainWindow{background:#1a1a1a;color:white;} "
            "QWidget{color:white;} "
            "QPushButton{background:#2a2a2a; border:1px solid #444; padding:6px 14px; border-radius:4px;} "
            "QPushButton:hover{border:1px solid #FF4500; background:#333;} "
            "QLineEdit,QTextEdit,QListWidget,QTableWidget{background:#232323;color:white;border:1px solid #333;border-radius:4px;padding:4px;}"
        )

        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)

        self.nav = QListWidget()
        self.nav.addItems(["Tasks", "Memory", "Tools", "Settings"])
        self.nav.setMaximumWidth(180)
        outer.addWidget(self.nav)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        self.tasks_page = self._build_tasks_page()
        self.memory_page = self._build_memory_page()
        self.tools_page = self._build_tools_page()
        self.settings_page = self._build_settings_page()
        self.stack.addWidget(self.tasks_page)
        self.stack.addWidget(self.memory_page)
        self.stack.addWidget(self.tools_page)
        self.stack.addWidget(self.settings_page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self._health_dot = QLabel("●")
        self._health_dot.setStyleSheet("color:#888;")
        self._task_count = QLabel("Tasks: 0")
        self.statusBar().addPermanentWidget(self._health_dot)
        self.statusBar().addPermanentWidget(self._task_count)

        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: asyncio.create_task(self.refresh_all()))
        self._timer.start(5000)

    # ----- Tasks Page (with prompt input) -----

    def _build_tasks_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # Prompt input row
        input_row = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type a task for Dexter... (press Enter or click Send)")
        self.prompt_input.setMinimumHeight(36)
        self.prompt_input.setStyleSheet(
            "QLineEdit{font-size:14px; padding:8px; border:1px solid #555; border-radius:6px;}"
            "QLineEdit:focus{border:1px solid #FF4500;}"
        )
        self.prompt_input.returnPressed.connect(lambda: asyncio.create_task(self._submit_prompt()))
        input_row.addWidget(self.prompt_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumHeight(36)
        self.send_btn.setStyleSheet(
            "QPushButton{background:#FF4500; color:white; font-weight:bold; padding:8px 20px; border-radius:6px; border:none;}"
            "QPushButton:hover{background:#FF5722;}"
            "QPushButton:disabled{background:#666;}"
        )
        self.send_btn.clicked.connect(lambda: asyncio.create_task(self._submit_prompt()))
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

        # Task list + details splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        self.task_table = QTableWidget(0, 4)
        self.task_table.setHorizontalHeaderLabels(["Prompt", "Status", "Time", "Result"])
        self.task_table.cellClicked.connect(lambda r, c: asyncio.create_task(self._on_task_clicked(r, c)))
        splitter.addWidget(self.task_table)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.task_details = QTextEdit()
        self.task_details.setReadOnly(True)
        self.task_logs = QTextEdit()
        self.task_logs.setReadOnly(True)
        details_layout.addWidget(QLabel("Task details"))
        details_layout.addWidget(self.task_details)
        details_layout.addWidget(QLabel("Step logs"))
        details_layout.addWidget(self.task_logs)
        splitter.addWidget(details)
        return page

    async def _submit_prompt(self) -> None:
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        self.send_btn.setEnabled(False)
        self.prompt_input.setEnabled(False)
        try:
            result = await self.api.submit_task(prompt)
            if result and result.get("id"):
                self.prompt_input.clear()
                self.statusBar().showMessage(f"Task submitted: {str(result['id'])[:8]}...", 3000)
                await self.refresh_tasks()
            else:
                self.statusBar().showMessage("Failed to submit task. Is the backend online?", 5000)
        finally:
            self.send_btn.setEnabled(True)
            self.prompt_input.setEnabled(True)
            self.prompt_input.setFocus()

    # ----- Memory Page -----

    def _build_memory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.memory_list = QListWidget()
        layout.addWidget(self.memory_list)
        btn_row = QHBoxLayout()
        self.memory_clear_btn = QPushButton("Clear All Memory")
        self.memory_clear_btn.clicked.connect(lambda: asyncio.create_task(self._clear_memory()))
        btn_row.addWidget(self.memory_clear_btn)
        layout.addLayout(btn_row)
        return page

    # ----- Tools Page (connected toggles) -----

    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Dangerous Tools"))
        layout.addWidget(QLabel("Toggle these tools on/off. Changes are saved to .env and take effect on next backend restart."))

        self.shell_toggle = QCheckBox("Enable shell tool")
        self.shell_toggle.setChecked(os.getenv("ENABLE_SHELL_TOOL", "false").lower() == "true")
        self.shell_toggle.toggled.connect(lambda checked: self._update_env_var("ENABLE_SHELL_TOOL", checked))
        layout.addWidget(self.shell_toggle)

        self.desktop_toggle = QCheckBox("Enable desktop control tool")
        self.desktop_toggle.setChecked(os.getenv("ENABLE_DESKTOP_CONTROL", "false").lower() == "true")
        self.desktop_toggle.toggled.connect(lambda checked: self._update_env_var("ENABLE_DESKTOP_CONTROL", checked))
        layout.addWidget(self.desktop_toggle)

        layout.addWidget(QLabel(""))
        self.restart_note = QLabel("ℹ️ Changes require a backend restart to take effect.")
        self.restart_note.setStyleSheet("color: #FF4500;")
        self.restart_note.hide()
        layout.addWidget(self.restart_note)

        layout.addStretch(1)
        return page

    def _update_env_var(self, key: str, enabled: bool) -> None:
        """Update a key in the .env file."""
        value = "true" if enabled else "false"
        env_path = self._find_env_file()
        if not env_path:
            return

        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ[key] = value
        self.restart_note.show()

    # ----- Settings Page (saves to .env) -----

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)

        self.api_url_edit = QLineEdit(self.config.DEXTER_API_URL)
        self.tts_voice_edit = QLineEdit(self.config.TTS_VOICE)
        self.whisper_model_edit = QLineEdit(self.config.WHISPER_MODEL)
        self.glow_color_edit = QLineEdit(self.config.GLOW_COLOR)
        self.auto_speak_toggle = QCheckBox("Auto-speak responses")
        self.auto_speak_toggle.setChecked(self.config.AUTO_SPEAK_RESPONSES)

        layout.addRow("API URL", self.api_url_edit)
        layout.addRow("TTS voice", self.tts_voice_edit)
        layout.addRow("Whisper model", self.whisper_model_edit)
        layout.addRow("Glow color", self.glow_color_edit)
        layout.addRow("Auto speak", self.auto_speak_toggle)

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet(
            "QPushButton{background:#FF4500; color:white; font-weight:bold; padding:8px 20px; border-radius:6px; border:none;}"
            "QPushButton:hover{background:#FF5722;}"
        )
        save_btn.clicked.connect(self._save_settings)
        layout.addRow("", save_btn)

        self.settings_status = QLabel("")
        self.settings_status.setStyleSheet("color: #00cc66;")
        layout.addRow("", self.settings_status)
        return page

    def _save_settings(self) -> None:
        """Persist settings to .env file."""
        env_path = self._find_env_file()
        if not env_path:
            self.settings_status.setText("⚠️ Could not find .env file")
            self.settings_status.setStyleSheet("color: #cc3333;")
            return

        settings_map = {
            "DEXTER_API_URL": self.api_url_edit.text().strip(),
            "TTS_VOICE": self.tts_voice_edit.text().strip(),
            "WHISPER_MODEL": self.whisper_model_edit.text().strip(),
            "GLOW_COLOR": self.glow_color_edit.text().strip(),
            "AUTO_SPEAK_RESPONSES": "true" if self.auto_speak_toggle.isChecked() else "false",
        }

        lines = env_path.read_text(encoding="utf-8").splitlines()
        for key, value in settings_map.items():
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Update runtime config
        self.config.TTS_VOICE = settings_map["TTS_VOICE"]
        self.config.WHISPER_MODEL = settings_map["WHISPER_MODEL"]
        self.config.GLOW_COLOR = settings_map["GLOW_COLOR"]
        self.config.AUTO_SPEAK_RESPONSES = self.auto_speak_toggle.isChecked()

        self.settings_status.setText("✅ Settings saved! Some changes need a restart.")
        self.settings_status.setStyleSheet("color: #00cc66;")

    def _find_env_file(self) -> Path | None:
        """Find the .env file relative to the project root."""
        candidates = [
            Path(__file__).resolve().parent.parent / ".env",
            Path.cwd() / ".env",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    # ----- Data refresh -----

    async def _clear_memory(self) -> None:
        await self.api.clear_memory()
        await self.refresh_memory()

    async def refresh_all(self) -> None:
        await asyncio.gather(self.refresh_tasks(), self.refresh_memory(), self.refresh_health())

    async def refresh_health(self) -> None:
        ok = await self.api.health_check()
        self._health_dot.setStyleSheet(f"color:{'#00cc66' if ok else '#cc3333'};")

    async def refresh_tasks(self) -> None:
        tasks = await self.api.get_tasks(limit=20)
        self.task_table.setRowCount(len(tasks))
        self._task_count.setText(f"Tasks: {len(tasks)}")
        for i, row in enumerate(tasks):
            prompt = str(row.get("prompt", ""))[:50]
            status = str(row.get("status", "unknown"))
            created = str(row.get("created_at", ""))
            result = str(row.get("result", ""))[:70]
            self.task_table.setItem(i, 0, QTableWidgetItem(prompt))
            item = QTableWidgetItem(status)
            item.setForeground(Qt.GlobalColor.white)
            self.task_table.setItem(i, 1, item)
            self.task_table.setItem(i, 2, QTableWidgetItem(created))
            self.task_table.setItem(i, 3, QTableWidgetItem(result))
            self.task_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row.get("id"))

    async def _on_task_clicked(self, row: int, _column: int) -> None:
        item = self.task_table.item(row, 0)
        if not item:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if not task_id:
            return
        self._current_task_id = str(task_id)
        task = await self.api.get_task(self._current_task_id)
        logs = await self.api.get_task_logs(self._current_task_id)
        self.task_details.setPlainText(str(task) if task else "No details")
        self.task_logs.setPlainText("\n".join(str(x) for x in logs))

    async def refresh_memory(self) -> None:
        rows = await self.api.get_memory(limit=50)
        self.memory_list.clear()
        for item in rows:
            self.memory_list.addItem(f"[{item.get('timestamp')}] {item.get('prompt')} -> {item.get('result')}")
