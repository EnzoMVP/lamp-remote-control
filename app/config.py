"""Load and save the bulb credentials.

The config lives outside the code and the executable, in
%APPDATA%\\LampRemote\\config.json (override with the LAMPREMOTE_CONFIG env var).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SUPPORTED_VERSIONS = (3.1, 3.2, 3.3, 3.4, 3.5)


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "LampRemote"


def config_path() -> Path:
    override = os.environ.get("LAMPREMOTE_CONFIG")
    return Path(override) if override else app_dir() / "config.json"


class ConfigError(Exception):
    """The config file is missing or invalid. The message is user-facing (pt-BR)."""


@dataclass
class DeviceConfig:
    id: str
    ip: str
    local_key: str
    version: float
    name: str = "Lâmpada"

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceConfig":
        missing = [k for k in ("id", "ip", "local_key", "version") if not data.get(k)]
        if missing:
            raise ConfigError(f"Campos faltando no config.json: {', '.join(missing)}")
        try:
            version = float(data["version"])
        except (TypeError, ValueError):
            raise ConfigError(f"Versão inválida: {data['version']!r}") from None
        if version not in SUPPORTED_VERSIONS:
            raise ConfigError(f"Versão {version} não suportada (use 3.1 a 3.5)")
        local_key = str(data["local_key"])
        if len(local_key) != 16:
            raise ConfigError("A local_key deve ter exatamente 16 caracteres")
        return cls(
            id=str(data["id"]).strip(),
            ip=str(data["ip"]).strip(),
            local_key=local_key,
            version=version,
            name=str(data.get("name") or "Lâmpada"),
        )


def load_config(path: Path | None = None) -> DeviceConfig:
    path = path or config_path()
    if not path.exists():
        raise ConfigError("Arquivo de configuração não encontrado")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # tolerate Notepad's BOM
    except json.JSONDecodeError as e:
        raise ConfigError(f"config.json inválido (linha {e.lineno})") from None
    if not isinstance(data, dict):
        raise ConfigError("config.json deve conter um objeto JSON")
    return DeviceConfig.from_dict(data)


def save_config(cfg: DeviceConfig, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
