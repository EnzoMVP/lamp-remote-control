"""End-to-end: real flyout window + real worker thread + simulated bulb, driven by mouse/keyboard."""

import time

import pytest
from PySide6.QtCore import QMetaObject, QPointF, Qt, QThread
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

import app.lathe  # noqa: F401 - registers BulbPart for QML
from app.backends import FakeBackend
from app.bulb_controller import BulbController
from app.bulb_worker import BulbWorker
from app.flyout import FlyoutController


def wait_until(app, cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def pump(app, seconds):
    wait_until(app, lambda: False, seconds)


@pytest.fixture
def ui(qapp, monkeypatch):
    monkeypatch.setenv("LAMPREMOTE_NO_FOREGROUND", "1")
    backend = FakeBackend(latency=0.02)
    worker = BulbWorker(backend)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.start)
    bulb = BulbController(worker, "Teste", "teste")
    fly = FlyoutController(bulb)
    thread.start()
    assert wait_until(qapp, lambda: bulb.ready)
    fly.open(None)
    assert wait_until(qapp, lambda: fly.view.isExposed())
    pump(qapp, 0.4)  # open animation
    yield qapp, backend, bulb, fly
    fly.unload()
    QMetaObject.invokeMethod(worker, "stop", Qt.ConnectionType.BlockingQueuedConnection)
    thread.quit()
    thread.wait(3000)


def find(fly, name) -> QQuickItem:
    # Walk the visual tree: Repeater delegates aren't QObject children of their row.
    stack = [fly.view.rootObject()]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            return item
        stack.extend(item.childItems())
    raise AssertionError(f"item {name!r} not found")


def scene_point(item, fx=0.5, fy=0.5):
    return item.mapToScene(QPointF(item.width() * fx, item.height() * fy)).toPoint()


def test_power_button_turns_bulb_off(ui):
    app, backend, bulb, fly = ui
    QTest.mouseClick(fly.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     scene_point(find(fly, "powerButton")))
    assert wait_until(app, lambda: backend.calls and backend.calls[-1] == {"20": False})
    assert bulb.on is False


def test_dragging_brightness_sends_few_commands_and_final_value(ui):
    app, backend, bulb, fly = ui
    slider = find(fly, "brightnessSlider")
    view = fly.view
    left, btn, mods = Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    QTest.mousePress(view, btn, mods, scene_point(slider, 0.9))
    for i in range(40):  # fast drag from 90% to 30% of the track
        QTest.mouseMove(view, scene_point(slider, 0.9 - 0.6 * (i + 1) / 40), 2)
        app.processEvents()
    QTest.mouseRelease(view, left, mods, scene_point(slider, 0.3))
    assert wait_until(app, lambda: abs(bulb.brightness - 30) <= 6)
    final = bulb.brightness
    expected_raw = round(10 + 990 * (final - 1) / 99)
    assert wait_until(app, lambda: backend.calls and backend.calls[-1].get("22") == expected_raw)
    assert len(backend.calls) < 20, f"{len(backend.calls)} commands for one drag"


def test_mode_switch_goes_to_colour(ui):
    app, backend, bulb, fly = ui
    QTest.mouseClick(fly.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     scene_point(find(fly, "modeSwitch")))
    assert wait_until(app, lambda: backend.calls and backend.calls[-1].get("21") == "colour")
    assert "24" in backend.calls[-1]
    assert bulb.mode == "colour"


def test_preset_tile_applies_scene(ui):
    app, backend, bulb, fly = ui
    QTest.mouseClick(fly.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     scene_point(find(fly, "preset_relaxar")))
    assert wait_until(app, lambda: backend.calls and backend.calls[-1].get("23") == 0)
    assert bulb.activePreset == "relaxar"


def test_escape_closes_panel(ui):
    app, _, _, fly = ui
    QTest.keyClick(fly.view, Qt.Key.Key_Escape)
    assert wait_until(app, lambda: not fly.view.isVisible())
