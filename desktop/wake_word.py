from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd
from openwakeword.model import Model


class WakeWordDetector:
    def __init__(self, wake_word: str, on_detected: Callable[[], None]) -> None:
        self._wake_word = wake_word
        self._on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        # openwakeword may not provide an exact "hey dexter" model; default package model is used.
        self._model = Model()

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _listen_loop(self) -> None:
        samplerate = 16000
        blocksize = 1280
        threshold = 0.5
        try:
            with sd.InputStream(samplerate=samplerate, channels=1, blocksize=blocksize, dtype="int16") as stream:
                while self._running:
                    frames, _overflow = stream.read(blocksize)
                    chunk = np.squeeze(frames).astype(np.int16)
                    scores = self._model.predict(chunk)
                    best = max((float(v) for v in scores.values()), default=0.0)
                    if best >= threshold:
                        self._on_detected()
        except Exception:
            self._running = False
