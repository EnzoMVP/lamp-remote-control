"""QObject exposed to QML as `bulb`: properties for the UI, slots for user actions.

UI changes are applied optimistically (the panel updates instantly) and sent
through a throttle: while a slider is dragged, at most one command goes out every
THROTTLE_MS, and the final value is always sent (trailing edge, or immediately on
release via commit()). Incoming bulb state never overwrites a field the user
touched in the last GUARD_S seconds, so polls can't make sliders jump back.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QColor

from .bulb_state import (
    MODE_COLOUR, MODE_WHITE, BulbState, DpsCodec, clamp, temperature_to_kelvin,
)

THROTTLE_MS = 150
GUARD_S = 2.0

# Scene tiles, shown in rows of 4. Each state must be distinct so only one tile lights up.
PRESETS = [
    {"id": "leitura", "name": "Leitura", "icon": "book", "caption": "Neutra",
     "state": {"mode": MODE_WHITE, "white_brightness": 100, "temperature": 60}},
    {"id": "relaxar", "name": "Relaxar", "icon": "sofa", "caption": "Quente",
     "state": {"mode": MODE_WHITE, "white_brightness": 40, "temperature": 0}},
    {"id": "foco", "name": "Foco", "icon": "target", "caption": "Fria",
     "state": {"mode": MODE_WHITE, "white_brightness": 100, "temperature": 100}},
    {"id": "noite", "name": "Noite", "icon": "moon", "caption": "Âmbar",
     "state": {"mode": MODE_COLOUR, "hue": 22, "saturation": 95, "colour_brightness": 8}},
]


class BulbController(QObject):
    stateChanged = Signal()
    connectionChanged = Signal()
    capabilitiesChanged = Signal()

    requestRefresh = Signal()
    requestRetry = Signal()
    requestFastPoll = Signal(bool)

    def __init__(self, worker=None, device_name: str = "Lâmpada", ip: str = "",
                 config_error: str | None = None, parent=None):
        super().__init__(parent)
        self._worker = worker
        self._state = BulbState()
        self._codec = DpsCodec()
        self._device_name = device_name
        self._ip = ip
        self._status = "unconfigured" if config_error or worker is None else "connecting"
        self._message = config_error or ""
        self._retry_in = 0
        self._has_state = False
        self._pending: set[str] = set()
        self._guards: dict[str, float] = {}

        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)
        self._throttle.setInterval(THROTTLE_MS)
        self._throttle.timeout.connect(self._on_throttle)

        if worker is not None:
            worker.stateReceived.connect(self._on_state_received)
            worker.connectionChanged.connect(self._on_connection_changed)
            worker.dpsetDetected.connect(self._on_dpset)
            worker.ipChanged.connect(self._on_ip_changed)
            self.requestRefresh.connect(worker.refresh)
            self.requestRetry.connect(worker.retry_now)
            self.requestFastPoll.connect(worker.set_fast_poll)

    # --- read-only state for Python callers (tray) ---------------------------
    @property
    def state(self) -> BulbState:
        return self._state

    # --- QML properties --------------------------------------------------------
    def _get_on(self): return self._state.on
    def _get_mode(self): return self._state.mode
    def _get_brightness(self): return self._state.brightness
    def _get_temperature(self): return self._state.temperature
    def _get_kelvin(self): return temperature_to_kelvin(self._state.temperature)
    def _get_hue(self): return self._state.hue
    def _get_saturation(self): return self._state.saturation
    def _get_color(self): return QColor(*self._state.display_rgb())
    def _get_status(self): return self._status
    def _get_message(self): return self._message
    def _get_retry_in(self): return self._retry_in
    def _get_ready(self): return self._status == "online" and self._has_state
    def _get_device_name(self): return self._device_name
    def _get_ip(self): return self._ip
    def _get_has_colour(self): return self._codec.has_colour
    def _get_has_temperature(self): return self._codec.has_temperature
    def _get_presets(self): return PRESETS

    def _get_active_preset(self):
        s = self._state
        for p in PRESETS:
            if all(_close(getattr(s, k), v) for k, v in p["state"].items()):
                return p["id"]
        return ""

    on = Property(bool, _get_on, notify=stateChanged)
    mode = Property(str, _get_mode, notify=stateChanged)
    brightness = Property(int, _get_brightness, notify=stateChanged)
    temperature = Property(int, _get_temperature, notify=stateChanged)
    kelvin = Property(int, _get_kelvin, notify=stateChanged)
    hue = Property(int, _get_hue, notify=stateChanged)
    saturation = Property(int, _get_saturation, notify=stateChanged)
    color = Property(QColor, _get_color, notify=stateChanged)
    activePreset = Property(str, _get_active_preset, notify=stateChanged)
    status = Property(str, _get_status, notify=connectionChanged)
    message = Property(str, _get_message, notify=connectionChanged)
    retryIn = Property(int, _get_retry_in, notify=connectionChanged)
    ready = Property(bool, _get_ready, notify=connectionChanged)
    hasState = Property(bool, lambda self: self._has_state, notify=connectionChanged)
    deviceName = Property(str, _get_device_name, constant=True)
    ipAddress = Property(str, _get_ip, notify=connectionChanged)
    hasColour = Property(bool, _get_has_colour, notify=capabilitiesChanged)
    hasTemperature = Property(bool, _get_has_temperature, notify=capabilitiesChanged)
    presets = Property("QVariantList", _get_presets, constant=True)

    # --- QML actions -------------------------------------------------------------
    @Slot()
    def toggle(self):
        self._change({"on": not self._state.on}, throttled=False)

    @Slot(bool)
    def setOn(self, on: bool):
        self._change({"on": on}, throttled=False)

    @Slot(str)
    def setMode(self, mode: str):
        if mode in (MODE_WHITE, MODE_COLOUR) and mode != self._state.mode:
            self._change({"mode": mode}, throttled=False)

    @Slot(int)
    def setBrightness(self, value: int):
        key = "colour_brightness" if self._state.mode == MODE_COLOUR else "white_brightness"
        self._change({key: clamp(int(value), 1, 100)})

    @Slot(int)
    def setTemperature(self, value: int):
        self._change({"mode": MODE_WHITE, "temperature": clamp(int(value), 0, 100)})

    @Slot(int)
    def setHue(self, value: int):
        self._change({"mode": MODE_COLOUR, "hue": int(value) % 360})

    @Slot(int)
    def setSaturation(self, value: int):
        self._change({"mode": MODE_COLOUR, "saturation": clamp(int(value), 0, 100)})

    @Slot(str)
    def applyPreset(self, preset_id: str):
        for p in PRESETS:
            if p["id"] == preset_id:
                self._change(dict(p["state"]), throttled=False)
                return

    @Slot()
    def commit(self):
        """Slider released: send whatever is pending right now."""
        if self._pending:
            self._throttle.stop()
            self._send()

    @Slot()
    def retry(self):
        self.requestRetry.emit()

    @Slot()
    def refresh(self):
        self.requestRefresh.emit()

    @Slot(bool)
    def setPanelVisible(self, visible: bool):
        self.requestFastPoll.emit(visible)

    # --- internals -----------------------------------------------------------------
    def _change(self, changes: dict, throttled: bool = True):
        if not self._get_ready():
            return
        if not self._state.on and "on" not in changes:
            changes["on"] = True  # adjusting a lit property implies "turn it on"
        changed = {k for k, v in changes.items() if getattr(self._state, k) != v}
        if not changed:
            return
        self._state = self._state.with_changes(changes)
        now = time.monotonic()
        for k in changed:
            self._guards[k] = now + GUARD_S
        self._pending |= changed
        self.stateChanged.emit()

        if not throttled:
            self._throttle.stop()
            self._send()
        elif not self._throttle.isActive():
            self._send()  # leading edge: the bulb reacts as soon as dragging starts
            self._throttle.start()

    def _on_throttle(self):
        if self._pending:
            self._send()
            self._throttle.start()

    def _send(self):
        if not self._pending or self._worker is None:
            return
        dps = self._codec.encode(self._state, self._pending)
        self._pending.clear()
        if dps:
            self._worker.submit(dps)

    @Slot(dict, bool)
    def _on_state_received(self, dps: dict, full: bool):
        incoming = self._codec.decode(dps, self._state)
        now = time.monotonic()
        keep = {k: getattr(self._state, k) for k, until in self._guards.items() if until > now}
        self._guards = {k: until for k, until in self._guards.items() if until > now}
        new_state = incoming.with_changes(keep)
        first = full and not self._has_state
        if first:
            self._has_state = True
        if new_state != self._state:
            self._state = new_state
            self.stateChanged.emit()
        if first:
            self.connectionChanged.emit()  # `ready` depends on _has_state

    @Slot(str, str, int)
    def _on_connection_changed(self, status: str, message: str, retry_in: int):
        self._status, self._message, self._retry_in = status, message, retry_in
        self.connectionChanged.emit()

    @Slot(dict)
    def _on_dpset(self, dpset: dict):
        self._codec = DpsCodec(dpset)
        self.capabilitiesChanged.emit()

    @Slot(str)
    def _on_ip_changed(self, ip: str):
        self._ip = ip
        self.connectionChanged.emit()


def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= 2
    return a == b
