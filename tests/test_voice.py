import array
import json

import pytest
from PySide6.QtCore import QObject, Signal

from app.settings import Settings, load_settings, save_settings
from app.voice import BLOCK, SpeechGate, VoiceController, is_complete, match_command


def w(word, conf=1.0, dur=0.6):
    return {"word": word, "conf": conf, "start": 0.0, "end": dur}


# --- match_command -------------------------------------------------------------------

@pytest.mark.parametrize("phrase, command", [
    ("lâmpada acende", "on"),
    ("lâmpada apaga", "off"),
    ("lâmpada foco", "foco"),
    ("lâmpada relaxa", "relaxar"),
])
def test_each_phrase_said_alone_is_a_command(phrase, command):
    assert match_command([w(x) for x in phrase.split()]) == command


def test_a_click_before_the_command_is_ignored():
    assert match_command([w("[unk]", 0.56, 0.06), w("lâmpada"), w("acende")]) == "on"


def test_command_inside_a_sentence_is_ignored():
    # "a lâmpada apaga sozinha às vezes"
    assert match_command([w("lâmpada"), w("apaga"), w("[unk]", 0.92, 0.6)]) is None
    assert match_command([w("[unk]", 1.0, 0.4), w("lâmpada"), w("apaga")]) is None


def test_word_without_the_prefix_is_ignored():
    assert match_command([w("foco")]) is None
    assert match_command([w("[unk]", 1.0, 1.3), w("foco", 0.97)]) is None


def test_unsure_word_is_ignored():
    assert match_command([w("lâmpada"), w("apaga", 0.6)]) is None


def test_two_commands_in_one_breath_are_ignored():
    assert match_command([w("lâmpada"), w("acende"), w("lâmpada"), w("apaga")]) is None


def test_is_complete_only_for_a_whole_command():
    assert is_complete("lâmpada apaga")
    assert is_complete("[unk] lâmpada foco")
    assert not is_complete("lâmpada")
    assert not is_complete("lâmpada apaga [unk]")
    assert not is_complete("")


# --- SpeechGate ----------------------------------------------------------------------

def block(level: int) -> bytes:
    """100 ms square wave whose RMS is `level`."""
    return array.array("h", [level, -level] * (BLOCK // 2)).tobytes()


QUIET, LOUD = block(30), block(2000)


def test_silence_never_reaches_the_recognizer():
    gate = SpeechGate()
    for _ in range(50):
        assert gate.push(QUIET) == (b"", False)


def test_utterance_includes_preroll_and_ends_after_hangover():
    gate = SpeechGate(preroll=3, hangover=4)
    for _ in range(10):
        gate.push(QUIET)
    audio, ended = gate.push(LOUD)
    assert audio == QUIET * 3 + LOUD and not ended
    assert gate.push(LOUD) == (LOUD, False)
    assert [gate.push(QUIET)[1] for _ in range(4)] == [False, False, False, True]
    assert not gate.active
    assert gate.push(QUIET) == (b"", False)


def test_short_pause_inside_a_command_does_not_split_it():
    gate = SpeechGate(hangover=7)
    gate.push(LOUD)  # "lâmpada"
    assert not any(gate.push(QUIET)[1] for _ in range(3))  # the comma
    assert gate.push(LOUD) == (LOUD, False)  # "apaga"


def test_complete_command_ends_after_a_short_pause():
    gate = SpeechGate(hangover=7, quick_hangover=3)
    gate.push(LOUD)
    assert gate.speaking
    ends = [gate.push(QUIET, complete=True)[1] for _ in range(3)]
    assert ends == [False, False, True]
    assert not gate.speaking


def test_noise_floor_rises_with_background_noise():
    gate = SpeechGate(min_rms=150, ratio=3)
    hum = block(120)
    for _ in range(200):
        gate.push(hum)
    assert gate.threshold > 300
    assert not gate.active


def test_endless_sound_becomes_the_new_floor():
    gate = SpeechGate(max_blocks=20)
    fan = block(400)
    ends = [gate.push(fan)[1] for _ in range(25)]
    assert ends.count(True) == 1
    assert gate.threshold >= 400 * 3
    assert gate.push(fan) == (b"", False)


# --- settings ------------------------------------------------------------------------

def test_settings_default_when_missing_or_broken(tmp_path):
    assert load_settings(tmp_path / "nope.json") == Settings()
    bad = tmp_path / "settings.json"
    bad.write_text("{oops", encoding="utf-8")
    assert load_settings(bad) == Settings()


def test_settings_round_trip_ignores_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(Settings(voice=True, voice_test=True), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "future": 1}), encoding="utf-8")
    assert load_settings(path) == Settings(voice=True, voice_test=True)


# --- VoiceController -----------------------------------------------------------------

class FakeListener(QObject):
    heard = Signal(str, str, int)
    statusChanged = Signal(str, str)
    finished = Signal()

    def __init__(self, model_path):
        super().__init__()
        self.started = self.stopped = False

    def start(self): self.started = True
    def stop(self): self.stopped = True
    def wait(self, ms=0): return True


class FakeBulb:
    def __init__(self):
        self.ready = True
        self.calls = []

    def setOn(self, on): self.calls.append(("setOn", on))
    def applyPreset(self, preset): self.calls.append(("applyPreset", preset))


@pytest.fixture
def voice(qapp, tmp_path):
    listeners = []

    def factory(path):
        listeners.append(FakeListener(path))
        return listeners[-1]

    saved = []
    bulb = FakeBulb()
    ctrl = VoiceController(bulb, Settings(), save=lambda s: saved.append(Settings(**vars(s))),
                           model_path=tmp_path, listener_factory=factory)
    return ctrl, bulb, listeners, saved


def test_enabling_starts_listening_and_is_remembered(voice):
    ctrl, _, listeners, saved = voice
    ctrl.setEnabled(True)
    assert listeners[0].started
    assert saved[-1].voice is True
    listeners[0].statusChanged.emit("listening", "")
    assert ctrl.status == "listening"


@pytest.mark.parametrize("command, call", [
    ("on", ("setOn", True)),
    ("off", ("setOn", False)),
    ("foco", ("applyPreset", "foco")),
    ("relaxar", ("applyPreset", "relaxar")),
])
def test_commands_drive_the_bulb(voice, command, call):
    ctrl, bulb, listeners, _ = voice
    ctrl.setEnabled(True)
    listeners[0].heard.emit("…", command, 300)
    assert bulb.calls == [call]


def test_non_commands_do_nothing(voice):
    ctrl, bulb, listeners, _ = voice
    ctrl.setEnabled(True)
    listeners[0].heard.emit("lâmpada(1.00) [unk](0.99)", "", 300)
    assert bulb.calls == []


def test_test_mode_only_logs(voice, caplog):
    ctrl, bulb, listeners, saved = voice
    ctrl.setEnabled(True)
    ctrl.setTestMode(True)
    assert saved[-1].voice_test is True
    with caplog.at_level("INFO", logger="app.voice"):
        listeners[0].heard.emit("lâmpada(1.00) apaga(1.00)", "off", 300)
        listeners[0].heard.emit("lâmpada(1.00) [unk](0.99)", "", 300)
    assert bulb.calls == []
    assert 'executaria "off"' in caplog.text
    assert "ignorado" in caplog.text


def test_offline_bulb_is_left_alone(voice):
    ctrl, bulb, listeners, _ = voice
    bulb.ready = False
    ctrl.setEnabled(True)
    listeners[0].heard.emit("…", "on", 300)
    assert bulb.calls == []


def test_disabling_stops_the_listener_and_ignores_late_signals(voice):
    ctrl, bulb, listeners, _ = voice
    ctrl.setEnabled(True)
    old = listeners[0]
    ctrl.setEnabled(False)
    assert old.stopped
    assert ctrl.status == "off"
    old.statusChanged.emit("listening", "")
    old.heard.emit("…", "on", 300)
    assert ctrl.status == "off"
    assert bulb.calls == []


def test_starts_on_launch_only_if_left_on(qapp, tmp_path):
    made = []
    factory = lambda path: made.append(FakeListener(path)) or made[-1]  # noqa: E731
    VoiceController(FakeBulb(), Settings(voice=False), save=lambda s: None,
                    model_path=tmp_path, listener_factory=factory).start()
    assert made == []
    VoiceController(FakeBulb(), Settings(voice=True), save=lambda s: None,
                    model_path=tmp_path, listener_factory=factory).start()
    assert made[0].started


# --- model download --------------------------------------------------------------------

def test_failed_download_is_retried(qapp, tmp_path, monkeypatch):
    import vosk

    import app.voice as voice_mod

    attempts = []

    def flaky_download(dest, stop):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("The read operation timed out")
        (dest / voice_mod.MODEL_NAME).mkdir(parents=True)
        return True

    monkeypatch.setattr(voice_mod, "download_model", flaky_download)
    monkeypatch.setattr(voice_mod, "DOWNLOAD_RETRY_S", 0)
    monkeypatch.setattr(vosk, "Model", lambda path: ("model", path))
    listener = voice_mod.VoiceListener(tmp_path)
    statuses = []
    listener.statusChanged.connect(lambda status, message: statuses.append(status))

    assert listener._load_model()[0] == "model"
    assert len(attempts) == 2
    assert statuses == ["downloading", "error", "downloading", "loading"]
