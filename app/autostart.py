"""'Start with Windows' via the per-user Run registry key (no admin rights needed)."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LampRemote"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Development: run the .pyw launcher with pythonw so no console window appears.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parent.parent / "LampRemote.pyw"
    return f'"{pythonw}" "{launcher}"'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            value = winreg.QueryValueEx(k, VALUE_NAME)[0]
    except OSError:
        return False
    # If the app was moved, the old entry points elsewhere: report it as off.
    return value == launch_command()


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, VALUE_NAME)
            except FileNotFoundError:
                pass
