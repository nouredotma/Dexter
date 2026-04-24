from __future__ import annotations

import asyncio

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from desktop.api_client import DexterAPIClient


class DexterTrayIcon(QSystemTrayIcon):
    def __init__(self, api: DexterAPIClient, parent=None) -> None:
        super().__init__(parent)
        self.api = api
        self.dashboard = None
        self.voice_controller = None
        self._wake_enabled = False
        self.setIcon(self._build_icon())
        self.setToolTip("Dexter")
        self._backend_label = None
        self.setContextMenu(self._build_menu())
        self.activated.connect(self._on_activated)

    def _build_icon(self) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor("#FF4500"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(8, 8, 48, 48)
        p.end()
        return QIcon(pix)

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        open_action = menu.addAction("Open Dashboard")
        open_action.triggered.connect(self._open_dashboard)
        menu.addSeparator()

        self.wake_action = menu.addAction("Wake Word OFF")
        self.wake_action.triggered.connect(self._toggle_wake)
        listen_action = menu.addAction("Listen Now")
        listen_action.triggered.connect(lambda: asyncio.create_task(self._listen_now()))

        menu.addSeparator()
        self._backend_label = menu.addAction("Backend Status: Unknown")
        self._backend_label.setEnabled(False)
        restart_action = menu.addAction("Restart Backend (docker-compose up -d)")
        restart_action.triggered.connect(self._restart_backend)

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        return menu

    async def update_backend_status(self) -> None:
        ok = await self.api.health_check()
        if self._backend_label:
            self._backend_label.setText(f"Backend Status: {'Online' if ok else 'Offline'}")
        if not ok:
            self.showMessage("Dexter", "Backend appears offline.", QSystemTrayIcon.MessageIcon.Warning)

    def bind(self, dashboard, voice_controller) -> None:
        self.dashboard = dashboard
        self.voice_controller = voice_controller
        self.voice_controller.response_ready.connect(self._notify_task_done)

    def notify_wake_word_detected(self) -> None:
        self.showMessage("Dexter", "Wake word detected.", QSystemTrayIcon.MessageIcon.Information)

    def _notify_task_done(self, text: str) -> None:
        preview = (text or "Task complete")[:120]
        self.showMessage("Dexter", preview, QSystemTrayIcon.MessageIcon.Information)

    async def _listen_now(self) -> None:
        if not self.voice_controller:
            return
        text = await self.voice_controller.start_listening()
        await self.voice_controller.process_and_respond(text)

    def _open_dashboard(self) -> None:
        if self.dashboard:
            self.dashboard.show()
            self.dashboard.raise_()
            self.dashboard.activateWindow()

    def _toggle_wake(self) -> None:
        if not self.voice_controller:
            return
        self._wake_enabled = not self._wake_enabled
        if self._wake_enabled:
            self.voice_controller.enable_wake_word()
            self.wake_action.setText("Wake Word ON")
        else:
            self.voice_controller.disable_wake_word()
            self.wake_action.setText("Wake Word OFF")

    def _restart_backend(self) -> None:
        import subprocess

        subprocess.Popen("docker-compose up -d", shell=True)
        self.showMessage("Dexter", "Backend restart triggered.", QSystemTrayIcon.MessageIcon.Information)

    def _quit_app(self) -> None:
        from PyQt6.QtWidgets import QApplication

        if self.voice_controller:
            self.voice_controller.disable_wake_word()
        QApplication.quit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_dashboard()
