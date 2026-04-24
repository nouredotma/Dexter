from __future__ import annotations

import asyncio
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from desktop.config import DexterConfig


class STTEngine:
    def __init__(self, config: DexterConfig) -> None:
        self._config = config
        self._is_listening = False
        self._model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    async def listen_and_transcribe(
        self,
        duration_seconds: int = 10,
        on_audio_level: Callable[[float], None] | None = None,
    ) -> str:
        self._is_listening = True
        try:
            text = await asyncio.to_thread(
                self._record_and_transcribe,
                duration_seconds,
                on_audio_level,
            )
            return text
        except Exception as exc:  # noqa: BLE001
            return f"error: microphone/transcription failed: {exc}"
        finally:
            self._is_listening = False

    def _record_and_transcribe(
        self,
        duration_seconds: int,
        on_audio_level: Callable[[float], None] | None,
    ) -> str:
        samplerate = 16000
        frames = int(duration_seconds * samplerate)
        if not sd.query_devices():
            return "error: no microphone detected"

        audio = sd.rec(frames, samplerate=samplerate, channels=1, dtype="float32")
        chunk = samplerate // 8
        cursor = 0
        while cursor < frames:
            end = min(cursor + chunk, frames)
            snippet = audio[cursor:end]
            level = float(np.sqrt(np.mean(np.square(snippet)))) if len(snippet) else 0.0
            if on_audio_level:
                on_audio_level(level)
            sd.sleep(125)
            cursor = end
        sd.wait()

        mono = np.squeeze(audio)
        segments, _info = self._model.transcribe(mono, language="en")
        text = " ".join(s.text.strip() for s in segments if s.text.strip()).strip()
        return text
