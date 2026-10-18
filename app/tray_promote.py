"""Show our tray icon on the taskbar instead of the hidden "^" overflow (Windows 11).

Explorer keeps one entry per tray app under HKCU\\Control Panel\\NotifyIconSettings;
`IsPromoted = 1` is the same switch as Settings > Personalization > Taskbar >
Other system tray icons. We flip it once per executable path, so if the user hides
the icon later, we respect that.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QTimer

from .config import app_dir

log = logging.getLogger(__name__)

KEY = r"Control Panel\NotifyIconSettings"
RETRIES = 10          # Explorer creates the entry a moment after the icon first appears
RETRY_MS = 1500


def _owner_executable() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    # A venv's python.exe is a launcher; the icon belongs to the base interpreter.
    return getattr(sys, "_base_executable", sys.executable)


def _same_exe(registry_path: str, target: str) -> bool:
    reg, target = os.path.normcase(registry_path), os.path.normcase(target)
    if reg == target:
        return True
    # Paths under known folders may be stored as "{FOLDERID-GUID}\rest\of\path".
    if reg.startswith("{") and "}" in reg:
        return target.endswith(reg.split("}", 1)[1])
    return False


def promote_once(exe: str | None = None) -> bool | None:
    """True = promoted now, False = entry not there yet, None = nothing to do."""
    if sys.platform != "win32":
        return None
    import winreg

    exe = exe or _owner_executable()
    flag = app_dir() / "tray_promoted.txt"
    try:
        if flag.read_text(encoding="utf-8").strip() == os.path.normcase(exe):
            return None
    except OSError:
        pass

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY)
    except OSError:
        return None  # older Windows: no per-icon settings key
    found = False
    with root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                    path = winreg.QueryValueEx(k, "ExecutablePath")[0]
                    if _same_exe(path, exe):
                        winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        found = True
            except OSError:
                continue
    if found:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(os.path.normcase(exe), encoding="utf-8")
        log.info("Tray icon promoted to the taskbar")
    return found


def schedule_promote_once(parent) -> None:
    """Retry for a few seconds until Explorer has registered our icon."""
    attempts = {"n": 0}

    def attempt():
        attempts["n"] += 1
        try:
            result = promote_once()
        except Exception:  # noqa: BLE001 - cosmetic feature, never fatal
            log.exception("Could not promote the tray icon")
            return
        if result is False and attempts["n"] < RETRIES:
            QTimer.singleShot(RETRY_MS, parent, attempt)

    QTimer.singleShot(RETRY_MS, parent, attempt)
