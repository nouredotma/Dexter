from __future__ import annotations

import platform
import sys
from pathlib import Path

if platform.system() == "Windows":
    import winreg


class AutostartManager:
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    KEY_NAME = "Dexter"

    def __init__(self) -> None:
        self._is_windows = platform.system() == "Windows"

    def enable_autostart(self) -> bool:
        if not self._is_windows:
            return False
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        main_path = (Path(__file__).resolve().parent / "main.py").resolve()
        value = f'"{pythonw}" "{main_path}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self.KEY_NAME, 0, winreg.REG_SZ, value)
        return True

    def disable_autostart(self) -> bool:
        if not self._is_windows:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self.KEY_NAME)
            return True
        except FileNotFoundError:
            return False

    def is_autostart_enabled(self) -> bool:
        if not self._is_windows:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, self.KEY_NAME)
            return True
        except FileNotFoundError:
            return False

    def docker_autostart_info(self) -> str:
        return (
            "Enable Docker Desktop -> Settings -> General -> 'Start Docker Desktop when you log in'. "
            "Dexter requires backend containers running before desktop voice tasks."
        )
