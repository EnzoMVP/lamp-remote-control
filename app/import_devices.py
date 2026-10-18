"""Create the app config from tinytuya's wizard output.

Usage (in the folder where you ran `python -m tinytuya wizard`):
    python -m app.import_devices [devices.json] [snapshot.json]

devices.json has the id/local key (from the cloud); snapshot.json, written by
`tinytuya scan`/`wizard`, has the local IP and protocol version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import ConfigError, DeviceConfig, config_path, save_config


def _load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _snapshot_index(snapshot) -> dict:
    if not snapshot:
        return {}
    items = snapshot.get("devices", []) if isinstance(snapshot, dict) else snapshot
    return {d.get("id"): d for d in items if isinstance(d, dict)}


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    devices_path = Path(argv[0] if argv else "devices.json")
    snapshot_path = Path(argv[1] if len(argv) > 1 else "snapshot.json")

    devices = _load(devices_path)
    if not devices:
        print(f"Não encontrei {devices_path}. Rode 'python -m tinytuya wizard' antes, nesta pasta.")
        return 1
    if isinstance(devices, dict):
        devices = devices.get("devices", [])
    snap = _snapshot_index(_load(snapshot_path))

    # Lights first ("dj" is Tuya's category for bulbs).
    devices = sorted(devices, key=lambda d: d.get("category") != "dj")
    print("Dispositivos encontrados:")
    for i, d in enumerate(devices, 1):
        found = snap.get(d.get("id"), {})
        ip = found.get("ip") or d.get("ip") or "IP desconhecido"
        print(f"  {i}. {d.get('name', '?')}  [{d.get('category', '?')}]  id={d.get('id')}  {ip}")

    choice = 1
    if len(devices) > 1:
        raw = _ask(f"Qual é a lâmpada? [1-{len(devices)}, Enter = 1]: ")
        if raw:
            if not raw.isdigit() or not 1 <= int(raw) <= len(devices):
                print("Opção inválida.")
                return 1
            choice = int(raw)
    dev = devices[choice - 1]
    found = snap.get(dev.get("id"), {})

    ip = found.get("ip") or dev.get("ip") or ""
    if not ip:
        ip = _ask("IP da lâmpada não encontrado (rode 'python -m tinytuya scan'). Digite o IP: ")
    version = found.get("ver") or found.get("version") or dev.get("version") or ""
    if not version:
        version = _ask("Versão do protocolo (ex.: 3.3, 3.4 ou 3.5): ")

    try:
        cfg = DeviceConfig.from_dict({
            "id": dev.get("id"), "ip": ip, "local_key": dev.get("key"),
            "version": version, "name": dev.get("name") or "Lâmpada",
        })
    except ConfigError as e:
        print(f"Erro: {e}")
        return 1

    save_config(cfg)
    print(f"\nConfiguração salva em {config_path()}")
    print(f"  {cfg.name} · {cfg.ip} · versão {cfg.version}")
    print("Reinicie o LampRemote (clique direito no ícone > Sair, e abra de novo).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
