from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from pathlib import Path

import edge_tts
import sounddevice as sd
import soundfile as sf

from desktop.config import DexterConfig


class TTSEngine:
    def __init__(self, config: DexterConfig) -> None:
        self._config = config
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._play_thread: threading.Thread | None = None

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    async def speak(self, text: str) -> None:
        if not text.strip():
            return
        await self.stop()
        self._is_speaking = True
        self._stop_event.clear()
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                temp_path = Path(f.name)
            communicate = edge_tts.Communicate(
                text=text,
                voice=self._config.TTS_VOICE,
                rate=self._config.TTS_RATE,
            )
            await communicate.save(str(temp_path))
            await asyncio.to_thread(self._play_audio_file, temp_path)
        except Exception:
            await asyncio.to_thread(self._fallback_tts, text)
        finally:
            self._is_speaking = False

    async def stop(self) -> None:
        self._stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)
        self._is_speaking = False

    def _play_audio_file(self, path: Path) -> None:
        try:
            data, samplerate = sf.read(str(path), dtype="float32")
            sd.play(data, samplerate)
            sd.wait()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _fallback_tts(self, text: str) -> None:
        command = f'powershell -Command "Add-Type -AssemblyName System.Speech; ' \
            f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text.replace(chr(39), " ")}\')"'
        os.system(command)
