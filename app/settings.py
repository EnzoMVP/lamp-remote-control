"""User preferences changed from the tray menu, kept in %APPDATA%\\LampRemote\\settings.json.

Separate from config.json, which holds the bulb credentials. A missing or broken file
just means "defaults": preferences are never worth an error dialog.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .config import app_dir

log = logging.getLogger(__name__)


def settings_path() -> Path:
    return app_dir() / "settings.json"


@dataclass
class Settings:
    voice: bool = False       # always-on voice commands
    voice_test: bool = False  # recognise and log, but don't touch the bulb


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError):
        log.warning("Ignoring unreadable %s", path)
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: bool(v) for k, v in data.items() if k in known})


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    tmp.replace(path)
