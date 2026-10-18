"""TuyaBackend against a fake device that behaves like the real Elgin bulb (protocol 3.5).

Observed on the real bulb: a change is reported as one message per DP, and each
tinytuya call reads only ONE message, so replies come back one step late, e.g.
    set {'21': 'colour', '24': red}  -> {'21': 'colour'}
    set {'24': green}                -> {'24': red}      (previous command's leftover)
    status()                         -> {'21': 'white'}  (a late partial, not the state)
"""

from app.backends import TuyaBackend
from app.bulb_state import DpsCodec
from app.config import DeviceConfig

FULL = {"20": True, "21": "white", "22": 1000, "23": 600, "24": "001603b60050",
        "25": "000e0d0000000000000000c80000", "26": 0, "34": True, "41": True}


class LaggyBulb:
    """Mimics the socket queue of a persistent tinytuya connection."""

    def __init__(self):
        self.state = dict(FULL)
        self.queue: list[dict] = []
        self.socket = object()  # "connected"
        self.connection_timeout = 3
        self.bulb_configured = True
        self.dpset = DpsCodec.TYPE_B

    def _read_one(self):
        return {"dps": self.queue.pop(0)} if self.queue else None

    def set_multiple_values(self, data, nowait=False):
        self.state.update(data)
        self.queue.extend({k: v} for k, v in data.items())  # one report per DP
        return None if nowait else self._read_one()

    def status(self, nowait=False):
        self.queue.append(dict(self.state))  # the real answer goes to the back of the queue
        return self._read_one()

    def receive(self):
        return self._read_one()

    def set_socketTimeout(self, s):
        self.connection_timeout = s

    def close(self):
        pass


def make_backend():
    backend = TuyaBackend(DeviceConfig("id", "1.2.3.4", "0123456789abcdef", 3.5))
    backend._dev = LaggyBulb()
    return backend


def test_status_after_commands_is_the_real_current_state():
    b = make_backend()
    b.set_dps({"21": "colour", "24": "000003e803e8"})
    b.set_dps({"24": "007803e803e8"})
    b.set_dps({"21": "white", "22": 1000, "23": 600})
    dps = b.status()
    assert dps["21"] == "white"
    assert len(dps) == len(FULL)
    assert b._dev.queue == []  # nothing stale left behind


def test_status_never_returns_a_partial_report():
    b = make_backend()
    b._dev.queue.append({"21": "colour"})  # a late leftover already waiting
    assert b.status() == b._dev.state


def test_set_does_not_return_stale_echo():
    b = make_backend()
    b.set_dps({"21": "colour", "24": "000003e803e8"})
    assert b.set_dps({"24": "007803e803e8"}) == {}
