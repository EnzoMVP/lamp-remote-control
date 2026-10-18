from app.bulb_controller import PRESETS, _close
from app.bulb_state import BulbState


def test_each_preset_highlights_only_its_own_tile():
    for preset in PRESETS:
        state = BulbState(on=True).with_changes(preset["state"])
        matches = [p["id"] for p in PRESETS
                   if all(_close(getattr(state, k), v) for k, v in p["state"].items())]
        assert matches == [preset["id"]]


def test_presets_fill_whole_rows_of_four():
    assert len(PRESETS) % 4 == 0
    assert len({p["id"] for p in PRESETS}) == len(PRESETS)
