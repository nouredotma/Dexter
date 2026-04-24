from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from desktop.config import DexterConfig


class OverlayState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class GlowBorder(QWidget):
    def __init__(self, config: DexterConfig, parent: QWidget) -> None:
        super().__init__(parent)
        self._config = config
        self._opacity = 0
        self._anim = QPropertyAnimation(self, b"glowOpacity")
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def get_opacity(self) -> int:
        return self._opacity

    def set_opacity(self, value: int) -> None:
        self._opacity = max(0, min(255, value))
        self.update()

    glowOpacity = pyqtProperty(int, get_opacity, set_opacity)

    def set_state(self, state: OverlayState) -> None:
        self._anim.stop()
        if state == OverlayState.IDLE:
            self._opacity = 0
            self.update()
            return
        if state == OverlayState.SPEAKING:
            self._opacity = self._config.GLOW_OPACITY
            self.update()
            return
        self._anim.setStartValue(40 if state == OverlayState.LISTENING else 70)
        self._anim.setEndValue(self._config.GLOW_OPACITY)
        self._anim.setDuration(1200 if state == OverlayState.LISTENING else 500)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._opacity <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self._config.GLOW_COLOR)
        color.setAlpha(self._opacity)
        pen = QPen(color, self._config.GLOW_WIDTH)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(4, 4, -4, -4))


class DexterOverlay(QWidget):
    def __init__(self, config: DexterConfig) -> None:
        super().__init__()
        self._config = config
        self._state = OverlayState.IDLE

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

        self._glow = GlowBorder(config, self)
        self._glow.setGeometry(self.rect())

        self._transcript = QLabel("", self)
        self._transcript.setWordWrap(True)
        self._transcript.setStyleSheet("background-color: rgba(0, 0, 0, 190); color: white; border-radius: 10px; padding: 12px;")
        self._transcript.setFont(QFont("Segoe UI", config.TRANSCRIPT_FONT_SIZE))
        self._transcript.hide()

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self.clear_transcript)

    def resizeEvent(self, _event) -> None:  # noqa: N802
        self._glow.setGeometry(self.rect())
        w, h = 460, 120
        self._transcript.setGeometry(QRect(self.width() - w - 32, self.height() - h - 48, w, h))

    def set_state(self, state: OverlayState) -> None:
        self._state = state
        self._glow.set_state(state)

    def show_transcript(self, text: str) -> None:
        self._transcript.setText(text)
        self._transcript.show()
        self._fade_timer.start(max(1000, self._config.TRANSCRIPT_DURATION * 1000))

    def clear_transcript(self) -> None:
        self._transcript.clear()
        self._transcript.hide()
