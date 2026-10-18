"""Bulb state model and Tuya DPS encoding/decoding.

Pure logic with no Qt or network dependency, so it can be unit-tested.

The UI works in friendly units:
    brightness   1..100 (%)
    temperature  0..100 (0 = warm, 100 = cold)
    hue          0..359 (degrees)
    saturation   0..100 (%)

Tuya bulbs come in "types" (see tinytuya.BulbDevice.DEFAULT_DPSET):
    B (most common, DPs 20-24): brightness/temp 10..1000 / 0..1000, colour "hhhhssssvvvv"
    A (older, DPs 1-5):         brightness/temp 25..255 / 0..255,  colour "rrggbb0hhhssvv"
"""

from __future__ import annotations

import colorsys
from dataclasses import asdict, dataclass, replace

MODE_WHITE = "white"
MODE_COLOUR = "colour"

WARM_KELVIN = 2700
COLD_KELVIN = 6500

FIELDS = ("on", "mode", "white_brightness", "colour_brightness", "temperature", "hue", "saturation")


@dataclass(frozen=True)
class BulbState:
    on: bool = False
    mode: str = MODE_WHITE
    white_brightness: int = 100
    colour_brightness: int = 100
    temperature: int = 50
    hue: int = 30
    saturation: int = 100

    @property
    def brightness(self) -> int:
        return self.colour_brightness if self.mode == MODE_COLOUR else self.white_brightness

    def with_changes(self, changes: dict) -> "BulbState":
        changes = {k: v for k, v in changes.items() if k in FIELDS}
        return replace(self, **changes)

    def as_dict(self) -> dict:
        return asdict(self)

    def display_rgb(self) -> tuple[int, int, int]:
        """The colour the bulb is emitting, at full intensity (ignores brightness/on)."""
        if self.mode == MODE_COLOUR:
            r, g, b = colorsys.hsv_to_rgb((self.hue % 360) / 360.0, self.saturation / 100.0, 1.0)
            return round(r * 255), round(g * 255), round(b * 255)
        return kelvin_to_rgb(temperature_to_kelvin(self.temperature))


def temperature_to_kelvin(temperature: int) -> int:
    return round(WARM_KELVIN + (COLD_KELVIN - WARM_KELVIN) * clamp(temperature, 0, 100) / 100)


def kelvin_to_rgb(kelvin: float) -> tuple[int, int, int]:
    """Approximate blackbody colour (Tanner Helland), slightly desaturated for a bulb look."""
    import math

    t = kelvin / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    return tuple(round(clamp(c, 0, 255)) for c in (r, g, b))  # type: ignore[return-value]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class DpsCodec:
    """Translates between BulbState and raw Tuya DPS for a given DP mapping.

    `dpset` uses tinytuya's BulbDevice.dpset format:
        {'switch': 20, 'mode': 21, 'brightness': 22, 'colourtemp': 23, 'colour': 24,
         'value_min': 10, 'value_max': 1000, 'value_hexformat': 'hsv16'}
    """

    TYPE_B = {
        "switch": 20, "mode": 21, "brightness": 22, "colourtemp": 23, "colour": 24,
        "value_min": 10, "value_max": 1000, "value_hexformat": "hsv16",
    }

    def __init__(self, dpset: dict | None = None):
        dpset = dict(dpset or self.TYPE_B)
        self.dp = {k: (str(dpset[k]) if dpset.get(k) is not None else None)
                   for k in ("switch", "mode", "brightness", "colourtemp", "colour")}
        self.vmin = int(dpset.get("value_min") or 10)
        self.vmax = int(dpset.get("value_max") or 1000)
        self.hexformat = dpset.get("value_hexformat") or "hsv16"

    @property
    def has_colour(self) -> bool:
        return self.dp["colour"] is not None

    @property
    def has_temperature(self) -> bool:
        return self.dp["colourtemp"] is not None

    # --- scaling -------------------------------------------------------
    def _pct_to_bright(self, pct: int) -> int:
        pct = clamp(int(pct), 1, 100)
        return round(self.vmin + (self.vmax - self.vmin) * (pct - 1) / 99)

    def _bright_to_pct(self, raw: int) -> int:
        return clamp(round(1 + 99 * (int(raw) - self.vmin) / (self.vmax - self.vmin)), 1, 100)

    def _pct_to_temp(self, pct: int) -> int:
        return round(self.vmax * clamp(int(pct), 0, 100) / 100)

    def _temp_to_pct(self, raw: int) -> int:
        return clamp(round(100 * int(raw) / self.vmax), 0, 100)

    def _encode_colour(self, hue: int, sat: int, bright_pct: int) -> str:
        h, s = (hue % 360), clamp(sat, 0, 100) / 100
        v = clamp(bright_pct, 1, 100) / 100
        if self.hexformat == "hsv16":
            return "%04x%04x%04x" % (h, round(s * 1000), round(v * 1000))
        r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(h / 360, s, v))
        return "%02x%02x%02x%04x%02x%02x" % (r, g, b, h, round(s * 255), round(v * 255))

    def _decode_colour(self, value: str) -> tuple[int, int, int] | None:
        """Returns (hue 0-359, saturation %, brightness %) or None if unparseable."""
        try:
            if len(value) == 12:
                h, s, v = int(value[0:4], 16), int(value[4:8], 16) / 1000, int(value[8:12], 16) / 1000
            elif len(value) == 14:
                h, s, v = int(value[6:10], 16), int(value[10:12], 16) / 255, int(value[12:14], 16) / 255
            elif len(value) == 6:
                r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
                hf, s, v = colorsys.rgb_to_hsv(r, g, b)
                h = round(hf * 360)
            else:
                return None
        except ValueError:
            return None
        return int(h) % 360, clamp(round(s * 100), 0, 100), clamp(round(v * 100), 1, 100)

    # --- public API ------------------------------------------------------
    def decode(self, dps: dict, base: BulbState) -> BulbState:
        """Merges raw DPS (full status or a partial update) into `base`."""
        dps = {str(k): v for k, v in dps.items()}
        ch: dict = {}
        if self.dp["switch"] in dps:
            ch["on"] = bool(dps[self.dp["switch"]])
        if self.dp["mode"] and self.dp["mode"] in dps:
            mode = dps[self.dp["mode"]]
            # scene/music modes are shown as colour mode; the UI never sends them
            ch["mode"] = MODE_WHITE if mode == MODE_WHITE else MODE_COLOUR
        if self.dp["brightness"] and self.dp["brightness"] in dps:
            ch["white_brightness"] = self._bright_to_pct(dps[self.dp["brightness"]])
        if self.dp["colourtemp"] and self.dp["colourtemp"] in dps:
            ch["temperature"] = self._temp_to_pct(dps[self.dp["colourtemp"]])
        if self.dp["colour"] and isinstance(dps.get(self.dp["colour"]), str):
            hsv = self._decode_colour(dps[self.dp["colour"]])
            if hsv:
                ch["hue"], ch["saturation"], ch["colour_brightness"] = hsv
        return base.with_changes(ch)

    def encode(self, target: BulbState, changed: set[str]) -> dict:
        """Builds the DPS needed to move the bulb to `target`, given which fields changed."""
        dps: dict = {}
        if "on" in changed:
            dps[self.dp["switch"]] = target.on
        if "mode" in changed and self.dp["mode"]:
            dps[self.dp["mode"]] = target.mode
        is_colour = target.mode == MODE_COLOUR
        if is_colour and self.has_colour and changed & {"mode", "hue", "saturation", "colour_brightness"}:
            dps[self.dp["colour"]] = self._encode_colour(target.hue, target.saturation, target.colour_brightness)
        if not is_colour:
            if self.dp["brightness"] and changed & {"mode", "white_brightness"}:
                dps[self.dp["brightness"]] = self._pct_to_bright(target.white_brightness)
            if self.has_temperature and changed & {"mode", "temperature"}:
                dps[self.dp["colourtemp"]] = self._pct_to_temp(target.temperature)
        return dps
