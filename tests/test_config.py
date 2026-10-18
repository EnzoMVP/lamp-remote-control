import json

import pytest

from app.config import ConfigError, DeviceConfig, load_config, save_config

VALID = {"id": "ebabc123", "ip": "192.168.0.50", "local_key": "0123456789abcdef", "version": "3.3"}


def write(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return p


def test_load_valid(tmp_path):
    cfg = load_config(write(tmp_path, VALID))
    assert cfg.version == 3.3
    assert cfg.name == "Lâmpada"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="não encontrado"):
        load_config(tmp_path / "nope.json")


def test_missing_fields(tmp_path):
    with pytest.raises(ConfigError, match="local_key"):
        load_config(write(tmp_path, {**VALID, "local_key": ""}))


def test_bad_json(tmp_path):
    with pytest.raises(ConfigError, match="inválido"):
        load_config(write(tmp_path, "{oops"))


def test_bad_version(tmp_path):
    with pytest.raises(ConfigError, match="não suportada"):
        load_config(write(tmp_path, {**VALID, "version": "2.0"}))


def test_bad_key_length(tmp_path):
    with pytest.raises(ConfigError, match="16"):
        load_config(write(tmp_path, {**VALID, "local_key": "short"}))


def test_save_round_trip(tmp_path):
    p = tmp_path / "sub" / "config.json"
    cfg = DeviceConfig.from_dict(VALID)
    save_config(cfg, p)
    assert load_config(p) == cfg


def test_load_with_bom(tmp_path):
    p = tmp_path / "config.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(VALID).encode())
    assert load_config(p).id == VALID["id"]
