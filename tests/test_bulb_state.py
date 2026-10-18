import pytest

from app.bulb_state import (
    MODE_COLOUR, MODE_WHITE, BulbState, DpsCodec, kelvin_to_rgb, temperature_to_kelvin,
)

TYPE_A = {"switch": 1, "mode": 2, "brightness": 3, "colourtemp": 4, "colour": 5,
          "value_min": 25, "value_max": 255, "value_hexformat": "rgb8"}


def test_decode_type_b_full_status():
    codec = DpsCodec()
    s = codec.decode({"20": True, "21": "white", "22": 1000, "23": 0, "24": "00f003e801f4"}, BulbState())
    assert s.on is True
    assert s.mode == MODE_WHITE
    assert s.white_brightness == 100
    assert s.temperature == 0
    assert (s.hue, s.saturation, s.colour_brightness) == (240, 100, 50)


def test_decode_partial_keeps_base_fields():
    base = BulbState(on=True, white_brightness=42, temperature=77)
    s = DpsCodec().decode({"20": False}, base)
    assert s.on is False
    assert (s.white_brightness, s.temperature) == (42, 77)


def test_scene_mode_shown_as_colour():
    s = DpsCodec().decode({"21": "scene"}, BulbState())
    assert s.mode == MODE_COLOUR


@pytest.mark.parametrize("pct", [1, 2, 50, 99, 100])
def test_brightness_round_trip(pct):
    codec = DpsCodec()
    target = BulbState(on=True, white_brightness=pct)
    dps = codec.encode(target, {"white_brightness"})
    assert 10 <= dps["22"] <= 1000
    assert codec.decode(dps, BulbState()).white_brightness == pct


def test_encode_white_mode_switch_sends_mode_brightness_and_temp():
    dps = DpsCodec().encode(BulbState(on=True, mode=MODE_WHITE, white_brightness=100, temperature=50), {"mode"})
    assert dps == {"21": "white", "22": 1000, "23": 500}


def test_encode_colour_hsv16():
    target = BulbState(on=True, mode=MODE_COLOUR, hue=300, saturation=50, colour_brightness=100)
    dps = DpsCodec().encode(target, {"hue"})
    assert dps == {"24": "012c01f403e8"}


def test_colour_change_in_white_mode_is_not_sent_as_colour():
    dps = DpsCodec().encode(BulbState(on=True, mode=MODE_WHITE), {"hue"})
    assert dps == {}


def test_type_a_colour_round_trip():
    codec = DpsCodec(TYPE_A)
    target = BulbState(on=True, mode=MODE_COLOUR, hue=120, saturation=100, colour_brightness=100)
    dps = codec.encode(target, {"mode", "hue"})
    assert dps["2"] == "colour"
    assert dps["5"].startswith("00ff00")
    back = codec.decode(dps, BulbState())
    assert (back.hue, back.saturation, back.colour_brightness) == (120, 100, 100)


def test_type_a_brightness_scale():
    codec = DpsCodec(TYPE_A)
    assert codec.encode(BulbState(white_brightness=1), {"white_brightness"})["3"] == 25
    assert codec.encode(BulbState(white_brightness=100), {"white_brightness"})["3"] == 255


def test_on_off_only():
    assert DpsCodec().encode(BulbState(on=False), {"on"}) == {"20": False}


def test_invalid_colour_hex_is_ignored():
    base = BulbState(hue=10)
    assert DpsCodec().decode({"24": "zz"}, base).hue == 10


def test_kelvin_colours_are_warm_to_cold():
    warm = kelvin_to_rgb(temperature_to_kelvin(0))
    cold = kelvin_to_rgb(temperature_to_kelvin(100))
    assert warm[0] == 255 and warm[2] < 200
    assert cold[2] > warm[2]


def test_display_rgb_colour_mode():
    assert BulbState(mode=MODE_COLOUR, hue=0, saturation=100).display_rgb() == (255, 0, 0)
