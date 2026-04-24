# Dexter Desktop App

## Requirements
- Python 3.12+
- Docker Desktop
- ffmpeg (required by faster-whisper)

## Installation
```bash
pip install -r desktop/requirements.txt
```

## Running
```bash
python desktop/main.py
```

## First Time Setup
1. Configure backend `.env` and ensure backend starts correctly.
2. Enable optional tools in `.env`:
   - `ENABLE_SHELL_TOOL=true` (only if needed)
   - `ENABLE_DESKTOP_CONTROL=true` (only if needed)
3. Open dashboard settings and tune voice model/voice.

## Usage
- Wake word flow: enable Wake Word from tray menu, then say wake phrase.
- Manual flow: tray menu -> `Listen Now`.
- Dashboard: view tasks, inspect logs, clear memory, and update settings.

## Troubleshooting
- Backend offline:
  - Run `docker-compose up -d`
  - Check `http://localhost:8000/health`
- Microphone not detected:
  - Verify OS input device permissions and default recording device.
- TTS not working:
  - Check internet access for `edge-tts`.
  - Fallback uses Windows system speech.
- ffmpeg missing:
  - Install ffmpeg and ensure it is available on PATH.

