import json

from app import import_devices
from app.config import load_config


def test_import_from_wizard_output(tmp_path, monkeypatch):
    monkeypatch.setenv("LAMPREMOTE_CONFIG", str(tmp_path / "out" / "config.json"))
    (tmp_path / "devices.json").write_text(json.dumps([
        {"name": "Tomada", "id": "plug1", "key": "aaaaaaaaaaaaaaaa", "category": "cz"},
        {"name": "Lâmpada Sala", "id": "bulb1", "key": "0123456789abcdef", "category": "dj"},
    ]), encoding="utf-8")
    (tmp_path / "snapshot.json").write_text(json.dumps(
        {"devices": [{"id": "bulb1", "ip": "192.168.0.77", "ver": "3.5"}]}), encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "")  # Enter = first (the bulb is sorted first)

    rc = import_devices.main([str(tmp_path / "devices.json"), str(tmp_path / "snapshot.json")])

    assert rc == 0
    cfg = load_config()
    assert (cfg.id, cfg.ip, cfg.version, cfg.name) == ("bulb1", "192.168.0.77", 3.5, "Lâmpada Sala")


def test_missing_devices_file(tmp_path, capsys):
    assert import_devices.main([str(tmp_path / "nope.json")]) == 1
    assert "wizard" in capsys.readouterr().out
