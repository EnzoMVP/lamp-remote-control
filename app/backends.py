"""Transports that talk to the bulb. All methods are blocking and must run off the UI thread."""

from __future__ import annotations

import logging
import random
import threading
import time

from .bulb_state import DpsCodec
from .config import DeviceConfig

log = logging.getLogger(__name__)


class BulbError(Exception):
    """Communication failure. The message is user-facing (pt-BR)."""


_TUYA_ERRORS = {
    "901": "Lâmpada não encontrada na rede",
    "902": "A lâmpada não respondeu a tempo",
    "904": "Resposta inválida da lâmpada",
    "905": "Lâmpada inacessível",
    "914": "Local key ou versão incorreta",
}


class TuyaBackend:
    def __init__(self, cfg: DeviceConfig):
        self.cfg = cfg
        self._dev = None

    def _device(self):
        if self._dev is None:
            import tinytuya

            self._dev = tinytuya.BulbDevice(
                self.cfg.id, self.cfg.ip, self.cfg.local_key, version=self.cfg.version,
                persist=True, connection_timeout=3, connection_retry_limit=1, connection_retry_delay=1,
            )
        return self._dev

    @property
    def dpset(self) -> dict | None:
        dev = self._dev
        return dict(dev.dpset) if dev is not None and dev.bulb_configured else None

    # Protocol 3.4/3.5 bulbs report a change as several messages (e.g. {'21': ...} then
    # {'24': ...}). tinytuya reads one message per call, so the rest stays queued on the
    # persistent socket and would be read later as if it were the *current* state -
    # the UI then "changes by itself". So: commands don't wait for echoes, stale
    # messages are drained before each query, and only a complete report counts.

    def status(self) -> dict:
        dev = self._device()
        self._drain()
        for _ in range(4):
            result = self._check(dev.status())
            dps = result.get("dps")
            if dps and self._is_full_report(dps):
                return dps
            log.debug("Skipping partial/late report: %s", dps)
        raise BulbError("Resposta incompleta da lâmpada")

    def set_dps(self, dps: dict) -> dict:
        # Fire and forget: the UI already shows the new value, and the echo arrives
        # out of order anyway. Failures still surface (send errors / next status()).
        result = self._device().set_multiple_values(dps, nowait=True)
        if isinstance(result, dict) and "Error" in result:
            self._check(result)
        return {}

    def _is_full_report(self, dps: dict) -> bool:
        dev = self._dev
        switch = dev.dpset.get("switch") if dev is not None and dev.bulb_configured else None
        if switch is not None:
            return str(switch) in dps and len(dps) >= 3
        return len(dps) >= 3

    def _drain(self, max_messages: int = 20) -> None:
        """Discard messages already waiting on the socket (late change reports)."""
        dev = self._dev
        if dev is None or getattr(dev, "socket", None) is None:
            return
        timeout = dev.connection_timeout
        dev.set_socketTimeout(0.08)
        try:
            for _ in range(max_messages):
                msg = dev.receive()
                if not msg:
                    break
                log.debug("Drained late message: %s", msg)
        finally:
            dev.set_socketTimeout(timeout)

    def close(self) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:  # noqa: BLE001 - closing a dead socket can fail in many ways
                pass
            self._dev = None

    def rediscover_ip(self) -> str | None:
        """Broadcast scan for the device id; returns the new IP if it moved."""
        import tinytuya

        found = tinytuya.find_device(dev_id=self.cfg.id)
        ip = found.get("ip") if found else None
        if ip and ip != self.cfg.ip:
            log.info("Bulb moved from %s to %s", self.cfg.ip, ip)
            self.cfg.ip = ip
            self.close()
            return ip
        return None

    @staticmethod
    def _check(result) -> dict:
        if not result:
            raise BulbError("Sem resposta da lâmpada")
        if "Error" in result:
            code = str(result.get("Err", ""))
            log.warning("Tuya error %s: %s (%s)", code, result.get("Error"), result.get("Payload"))
            raise BulbError(_TUYA_ERRORS.get(code, str(result["Error"])))
        return result


class FakeBackend:
    """In-memory bulb for demo mode and tests. Simulates latency and optional flakiness."""

    def __init__(self, latency: float = 0.08, failure_rate: float = 0.0):
        self.latency = latency
        self.failure_rate = failure_rate
        self.offline = False
        self.calls: list[dict] = []
        self._lock = threading.Lock()
        self._dps = {"20": True, "21": "white", "22": 800, "23": 300, "24": "001e03e803e8"}

    dpset = DpsCodec.TYPE_B

    def _io(self) -> None:
        time.sleep(self.latency)
        if self.offline or random.random() < self.failure_rate:
            raise BulbError("Lâmpada inacessível")

    def status(self) -> dict:
        self._io()
        with self._lock:
            return dict(self._dps)

    def set_dps(self, dps: dict) -> dict:
        self._io()
        with self._lock:
            self.calls.append(dict(dps))
            self._dps.update({str(k): v for k, v in dps.items()})
            return dict(dps)

    def close(self) -> None:
        pass

    def rediscover_ip(self) -> str | None:
        return None
