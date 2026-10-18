"""Worker + controller running for real (worker in its own QThread) against FakeBackend."""

import time

import pytest
from PySide6.QtCore import QThread

from app.backends import FakeBackend
from app.bulb_controller import BulbController
from app.bulb_worker import BulbWorker


def wait_until(app, cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def rig(qapp):
    backend = FakeBackend(latency=0.05)
    worker = BulbWorker(backend)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.start)
    ctrl = BulbController(worker, "Teste", "1.2.3.4")
    thread.start()
    yield qapp, backend, worker, ctrl
    thread.quit()
    thread.wait(2000)


def test_initial_state_is_read(rig):
    app, backend, _, ctrl = rig
    assert wait_until(app, lambda: ctrl.ready)
    assert ctrl.on is True
    assert ctrl.mode == "white"
    assert ctrl.brightness == 80  # 800/1000 -> 80%


def test_slider_drag_is_coalesced_and_final_value_wins(rig):
    app, backend, _, ctrl = rig
    assert wait_until(app, lambda: ctrl.ready)
    for v in range(1, 101):  # 100 drag events in a burst
        ctrl.setBrightness(v)
    ctrl.commit()
    assert wait_until(app, lambda: backend.calls and backend.calls[-1].get("22") == 1000)
    assert len(backend.calls) <= 3, backend.calls


def test_optimistic_value_survives_stale_poll(rig):
    app, backend, _, ctrl = rig
    assert wait_until(app, lambda: ctrl.ready)
    backend.latency = 0.3
    ctrl.setBrightness(10)
    ctrl.refresh()  # a poll that may return the old value first
    for _ in range(40):
        app.processEvents()
        assert ctrl.brightness == 10
        time.sleep(0.02)


def test_offline_then_reconnect(rig):
    app, backend, _, ctrl = rig
    assert wait_until(app, lambda: ctrl.ready)
    backend.offline = True
    ctrl.refresh()
    assert wait_until(app, lambda: ctrl.status == "offline")
    assert not ctrl.ready
    ctrl.toggle()  # ignored while offline, must not raise
    backend.offline = False
    assert wait_until(app, lambda: ctrl.status == "online", timeout=4)


def test_colour_scene_while_off_turns_on(rig):
    app, backend, _, ctrl = rig
    assert wait_until(app, lambda: ctrl.ready)
    ctrl.setOn(False)
    assert wait_until(app, lambda: backend.calls and backend.calls[-1] == {"20": False})
    ctrl.applyPreset("noite")
    assert ctrl.on and ctrl.mode == "colour" and ctrl.hue == 22
    assert wait_until(app, lambda: backend.calls[-1].get("20") is True and "24" in backend.calls[-1])
