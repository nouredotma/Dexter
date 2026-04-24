from __future__ import annotations

import asyncio

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
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
        self.setStyleSheet("QMainWindow{background:#1a1a1a;color:white;} QWidget{color:white;} QPushButton{background:#2a2a2a;} QLineEdit,QTextEdit,QListWidget,QTableWidget{background:#232323;color:white;}")

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

    def _build_tasks_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
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

    def _build_memory_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.memory_list = QListWidget()
        layout.addWidget(self.memory_list)
        btn_row = QHBoxLayout()
        self.memory_delete_btn = QPushButton("Delete Selected")
        self.memory_delete_btn.setEnabled(False)
        self.memory_clear_btn = QPushButton("Clear All")
        self.memory_clear_btn.clicked.connect(lambda: asyncio.create_task(self._clear_memory()))
        btn_row.addWidget(self.memory_delete_btn)
        btn_row.addWidget(self.memory_clear_btn)
        layout.addLayout(btn_row)
        return page

    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.shell_toggle = QCheckBox("Enable shell tool")
        self.desktop_toggle = QCheckBox("Enable desktop control tool")
        layout.addWidget(QLabel("Dangerous tools"))
        layout.addWidget(self.shell_toggle)
        layout.addWidget(self.desktop_toggle)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        self.api_url_edit = QLineEdit(self.config.DEXTER_API_URL)
        self.tts_voice_edit = QLineEdit(self.config.TTS_VOICE)
        self.whisper_model_edit = QLineEdit(self.config.WHISPER_MODEL)
        self.wake_word_toggle = QCheckBox("Enable wake word")
        self.glow_color_edit = QLineEdit(self.config.GLOW_COLOR)
        self.auto_speak_toggle = QCheckBox("Auto-speak responses")
        self.auto_speak_toggle.setChecked(self.config.AUTO_SPEAK_RESPONSES)
        layout.addRow("API URL", self.api_url_edit)
        layout.addRow("TTS voice", self.tts_voice_edit)
        layout.addRow("Whisper model", self.whisper_model_edit)
        layout.addRow("Wake word", self.wake_word_toggle)
        layout.addRow("Glow color", self.glow_color_edit)
        layout.addRow("Auto speak", self.auto_speak_toggle)
        return page

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
