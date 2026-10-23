"""Always-on voice commands, recognised offline with Vosk.

Pipeline, in the VoiceListener thread:

    microphone → SpeechGate → Vosk (fixed grammar) → match_command → heard signal

- The gate splits the audio into utterances (sound bounded by silence). Vosk only runs
  while there is sound, so a quiet room costs next to nothing.
- Vosk is restricted to the command phrases plus "[unk]" (anything else), which makes the
  four phrases very reliable.
- An utterance runs only if it is *exactly* one command: "lâmpada, apaga" said on its own
  works, "a lâmpada apaga sozinha" in the middle of a conversation does not.
"""

from __future__ import annotations

import array
import json
import logging
import math
import queue
import shutil
import threading
import time
import urllib.request
import zipfile
from collections import deque
from pathlib import Path

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from .config import app_dir
from .settings import Settings, save_settings

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BLOCK = 1600  # 100 ms of 16-bit mono audio

MODEL_NAME = "vosk-model-small-pt-0.3"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"

COMMANDS = {
    "lâmpada acende": "on",
    "lâmpada apaga": "off",
    "lâmpada foco": "foco",
    "lâmpada relaxa": "relaxar",
}
GRAMMAR = json.dumps([*COMMANDS, "[unk]"], ensure_ascii=False)

ACTIONS = {
    "on": lambda bulb: bulb.setOn(True),
    "off": lambda bulb: bulb.setOn(False),
    "foco": lambda bulb: bulb.applyPreset("foco"),
    "relaxar": lambda bulb: bulb.applyPreset("relaxar"),
}

MIN_CONF = 0.8      # every command word must be at least this certain
NOISE_S = 0.15      # an "[unk]" shorter than this is a click or a breath, not a word
COOLDOWN_S = 3.0    # ignore repeats right after a command (echo, saying it twice)
MIC_RETRY_S = 5     # microphone missing or unplugged: try again after this long
MIC_STALL_S = 3.0   # no audio for this long means the stream died
DOWNLOAD_RETRY_S = 60  # model server unreachable: try again after this long


def model_dir() -> Path:
    return app_dir() / "voice"


def match_command(words: list[dict]) -> str | None:
    """Command id if the utterance is exactly one command phrase, else None.

    `words` is Vosk's per-word result: [{"word", "conf", "start", "end"}, ...].
    """
    kept = [w for w in words if not (w["word"] == "[unk]" and w["end"] - w["start"] < NOISE_S)]
    if any(w["conf"] < MIN_CONF for w in kept):
        return None
    return COMMANDS.get(" ".join(w["word"] for w in kept))


def describe(words: list[dict]) -> str:
    return " ".join(f"{w['word']}({w['conf']:.2f})" for w in words)


def rms(block: bytes) -> float:
    samples = array.array("h", block)
    return math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0.0


class SpeechGate:
    """Splits a stream of fixed-size audio blocks into utterances.

    An utterance starts at the first block clearly louder than the background noise (with
    `preroll` blocks before it, so the first syllable isn't cut) and ends after `hangover`
    quiet blocks. The noise floor adapts while idle; a sound that never stops (a fan was
    switched on) ends the utterance after `max_blocks` and becomes the new floor.
    """

    def __init__(self, min_rms: float = 150.0, ratio: float = 3.0, preroll: int = 3,
                 hangover: int = 7, max_blocks: int = 100):
        self._min_rms = min_rms
        self._ratio = ratio
        self._hangover = hangover
        self._max_blocks = max_blocks
        self._preroll: deque[bytes] = deque(maxlen=preroll)
        self._floor = min_rms / ratio
        self._active = False
        self._quiet = 0
        self._length = 0
        self._quietest = 0.0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def threshold(self) -> float:
        return max(self._min_rms, self._floor * self._ratio)

    def push(self, block: bytes) -> tuple[bytes, bool]:
        """Returns (audio to feed the recognizer, whether an utterance just ended)."""
        level = rms(block)
        loud = level >= self.threshold
        if not self._active:
            if not loud:
                self._floor += 0.05 * (level - self._floor)
                self._preroll.append(block)
                return b"", False
            self._active, self._quiet, self._length, self._quietest = True, 0, 0, level
            audio = b"".join(self._preroll) + block
            self._preroll.clear()
            return audio, False

        self._length += 1
        self._quietest = min(self._quietest, level)
        self._quiet = 0 if loud else self._quiet + 1
        if self._quiet >= self._hangover:
            self._active = False
            return block, True
        if self._length >= self._max_blocks:
            self._active = False
            self._floor = max(self._floor, self._quietest)
            return block, True
        return block, False


def download_model(dest: Path, stop: threading.Event) -> bool:
    """Download and unpack the model into dest/MODEL_NAME. False if stopped midway."""
    dest.mkdir(parents=True, exist_ok=True)
    part = dest / f"{MODEL_NAME}.zip.part"
    tmp = dest / f"{MODEL_NAME}.tmp"
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=10) as resp, open(part, "wb") as f:
            while chunk := resp.read(1 << 16):
                if stop.is_set():
                    return False
                f.write(chunk)
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(part) as z:
            z.extractall(tmp)
        (tmp / MODEL_NAME).replace(dest / MODEL_NAME)
        return True
    finally:
        part.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


class VoiceListener(QThread):
    # words heard with their confidence, command id ("" if the utterance isn't a command)
    heard = Signal(str, str)
    # "downloading" | "loading" | "listening" | "error", user-facing message (pt-BR)
    statusChanged = Signal(str, str)

    def __init__(self, model_path: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("voice")
        self._model_path = model_path
        self._stop = threading.Event()
        self._last_command = -math.inf

    def stop(self) -> None:
        """Ask the thread to finish; returns at once (see QThread.wait)."""
        self._stop.set()

    def run(self) -> None:
        model = self._load_model()
        while model is not None and not self._stop.is_set():
            try:
                self._listen(model)
            except Exception as e:  # noqa: BLE001 - PortAudio raises plain exceptions
                log.warning("Microphone unavailable: %s", e)
                self.statusChanged.emit("error", "Microfone indisponível")
                self._stop.wait(MIC_RETRY_S)

    def _load_model(self):
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)
        path = self._model_path / MODEL_NAME
        while not path.is_dir():
            self.statusChanged.emit("downloading", "Baixando o modelo de voz (~32 MB)…")
            log.info("Downloading %s", MODEL_URL)
            try:
                if not download_model(self._model_path, self._stop):
                    return None
            except (OSError, zipfile.BadZipFile) as e:  # URLError and timeouts are OSErrors
                log.warning("Model download failed: %s", e)
                self.statusChanged.emit(
                    "error", "Não foi possível baixar o modelo de voz. Nova tentativa em 1 min")
                if self._stop.wait(DOWNLOAD_RETRY_S):
                    return None
        self.statusChanged.emit("loading", "Carregando o modelo de voz…")
        try:
            return Model(str(path))
        except Exception:  # noqa: BLE001 - vosk raises a bare Exception for a broken model
            log.exception("Could not load the voice model")
            self.statusChanged.emit("error", "Não foi possível carregar o modelo de voz")
            return None

    def _listen(self, model) -> None:
        import sounddevice as sd
        from vosk import KaldiRecognizer

        blocks: queue.Queue[bytes] = queue.Queue(maxsize=50)

        def on_audio(data, frames, time_info, status):
            try:
                blocks.put_nowait(bytes(data))
            except queue.Full:
                pass

        rec = KaldiRecognizer(model, SAMPLE_RATE, GRAMMAR)
        rec.SetWords(True)
        gate = SpeechGate()
        words: list[dict] = []
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1,
                               dtype="int16", callback=on_audio):
            self.statusChanged.emit("listening", "")
            log.info("Listening on %s", sd.query_devices(kind="input")["name"])
            last_block = time.monotonic()
            while not self._stop.is_set():
                try:
                    block = blocks.get(timeout=0.2)
                except queue.Empty:
                    if time.monotonic() - last_block > MIC_STALL_S:
                        raise RuntimeError("no audio from the microphone") from None
                    continue
                last_block = time.monotonic()
                audio, ended = gate.push(block)
                if audio and rec.AcceptWaveform(audio):
                    words += json.loads(rec.Result()).get("result", [])
                if ended:
                    words += json.loads(rec.FinalResult()).get("result", [])
                    rec.Reset()
                    self._finish(words)
                    words = []

    def _finish(self, words: list[dict]) -> None:
        if not words:
            return
        command = match_command(words) or ""
        now = time.monotonic()
        if command:
            if now - self._last_command < COOLDOWN_S:
                command = ""
            else:
                self._last_command = now
        self.heard.emit(describe(words), command)


class VoiceController(QObject):
    """Owns the listener thread and turns what it hears into bulb actions."""

    statusChanged = Signal()

    def __init__(self, bulb, settings: Settings, save=save_settings, model_path: Path | None = None,
                 listener_factory=VoiceListener, parent=None):
        super().__init__(parent)
        self._bulb = bulb
        self._settings = settings
        self._save = save
        self._model_path = model_path or model_dir()
        self._factory = listener_factory
        self._listener = None
        self._stopping: set = set()
        self._status = "off"
        self._message = ""

    def _get_enabled(self): return self._settings.voice
    def _get_test_mode(self): return self._settings.voice_test
    def _get_status(self): return self._status
    def _get_message(self): return self._message

    enabled = Property(bool, _get_enabled, notify=statusChanged)
    testMode = Property(bool, _get_test_mode, notify=statusChanged)
    status = Property(str, _get_status, notify=statusChanged)
    message = Property(str, _get_message, notify=statusChanged)

    def start(self) -> None:
        """Start listening if the user left voice commands on."""
        if self._settings.voice:
            self._start_listener()

    @Slot(bool)
    def setEnabled(self, enabled: bool) -> None:
        if enabled == self._settings.voice:
            return
        self._settings.voice = enabled
        self._persist()
        if enabled:
            self._start_listener()
        else:
            self._stop_listener()
            self._set_status("off", "")

    @Slot(bool)
    def setTestMode(self, test: bool) -> None:
        if test != self._settings.voice_test:
            self._settings.voice_test = test
            self._persist()
            self.statusChanged.emit()

    def shutdown(self) -> None:
        self._stop_listener()
        for listener in list(self._stopping):
            listener.wait(5000)

    # --- internals -------------------------------------------------------------
    def _start_listener(self) -> None:
        if self._listener is not None:
            return
        listener = self._factory(self._model_path)
        listener.heard.connect(self._on_heard)
        listener.statusChanged.connect(self._on_listener_status)
        self._listener = listener
        self._set_status("loading", "Carregando o modelo de voz…")
        listener.start()

    def _stop_listener(self) -> None:
        listener, self._listener = self._listener, None
        if listener is None:
            return
        listener.heard.disconnect(self._on_heard)
        listener.statusChanged.disconnect(self._on_listener_status)
        listener.stop()
        # Don't block the UI while it winds down (a download can take a moment to notice).
        self._stopping.add(listener)
        listener.finished.connect(self._reap)

    @Slot()
    def _reap(self) -> None:
        self._stopping.discard(self.sender())

    @Slot(str, str)
    def _on_listener_status(self, status: str, message: str) -> None:
        if self.sender() == self._listener:  # else: queued before that listener was stopped
            self._set_status(status, message)

    def _set_status(self, status: str, message: str) -> None:
        if (status, message) != (self._status, self._message):
            self._status, self._message = status, message
            self.statusChanged.emit()

    @Slot(str, str)
    def _on_heard(self, text: str, command: str) -> None:
        if self.sender() != self._listener:
            return
        if self._settings.voice_test:
            # The test log is for the user to read, hence pt-BR.
            if command:
                log.info('Voz (teste): ouviu "%s" -> executaria "%s"', text, command)
            elif any(not w.startswith("[unk]") for w in text.split()):
                log.info('Voz (teste): ouviu "%s" -> ignorado', text)
            else:
                log.debug("Voice (test): noise %s", text)
            return
        if not command:
            log.debug("Voice: ignored %s", text)
            return
        if not self._bulb.ready:
            log.info("Voice: %s heard, but the bulb isn't reachable", command)
            return
        log.info("Voice: %s (%s)", command, text)
        ACTIONS[command](self._bulb)

    def _persist(self) -> None:
        try:
            self._save(self._settings)
        except OSError:
            log.exception("Could not save settings")
