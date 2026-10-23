"""Background worker that owns the bulb connection.

Lives in its own QThread. Every network call happens here, so the UI never blocks.
Commands are coalesced: while one is in flight, newer values overwrite older
pending ones and only the latest set is sent next ("latest wins").
"""

from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .backends import BulbError

log = logging.getLogger(__name__)

BACKOFF_SECONDS = (1, 2, 5, 10, 20, 30)
POLL_FAST_MS = 3000   # panel open
POLL_SLOW_MS = 15000  # panel closed: keeps the tray icon honest and the socket alive
REDISCOVER_AFTER = 3  # failures before trying a broadcast scan for a new IP
SLOW_COMMAND_MS = 250  # log commands slower than this, to see where the delay goes


class BulbWorker(QObject):
    # dps, is_full_status
    stateReceived = Signal(dict, bool)
    # status ("connecting" | "online" | "offline"), message, retry_in_seconds
    connectionChanged = Signal(str, str, int)
    dpsetDetected = Signal(dict)
    ipChanged = Signal(str)

    _kick = Signal()

    def __init__(self, backend):
        super().__init__()
        self._backend = backend
        self._lock = threading.Lock()
        self._pending: dict = {}
        self._pending_since = 0.0
        self._kicked = False
        self._online = False
        self._failures = 0
        self._poll_ms = POLL_SLOW_MS
        self._poll_timer: QTimer | None = None
        self._retry_timer: QTimer | None = None
        self._kick.connect(self._flush)

    # --- called from the UI thread -------------------------------------------
    def submit(self, dps: dict) -> None:
        """Thread-safe: queue DPS to send. At most one flush is ever queued."""
        with self._lock:
            if not self._pending:
                self._pending_since = time.monotonic()
            self._pending.update(dps)
            if self._kicked:
                return
            self._kicked = True
        self._kick.emit()

    # --- slots (run in the worker thread) ------------------------------------
    @Slot()
    def start(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._connect)
        self._connect()

    @Slot()
    def stop(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
        if self._retry_timer:
            self._retry_timer.stop()
        self._backend.close()

    @Slot()
    def refresh(self) -> None:
        if self._online:
            self._poll()

    @Slot()
    def retry_now(self) -> None:
        if not self._online and self._retry_timer is not None:
            self._retry_timer.stop()
            self._connect()

    @Slot(bool)
    def set_fast_poll(self, fast: bool) -> None:
        self._poll_ms = POLL_FAST_MS if fast else POLL_SLOW_MS
        if self._online and self._poll_timer is not None:
            self._poll_timer.start(self._poll_ms)
            if fast:
                self._poll()  # panel just opened: show the real state right away

    @Slot()
    def _flush(self) -> None:
        with self._lock:
            dps, self._pending, self._kicked = self._pending, {}, False
            since = self._pending_since
        if not dps or not self._online:
            return
        start = time.monotonic()
        try:
            echo = self._call(self._backend.set_dps, dps)
        except BulbError as e:
            self._fail(e)
            return
        done = time.monotonic()
        # Queued = waiting for a poll or an earlier command to finish; sent = the network call.
        queued_ms, sent_ms = (start - since) * 1000, (done - start) * 1000
        log.log(logging.INFO if queued_ms + sent_ms > SLOW_COMMAND_MS else logging.DEBUG,
                "Command %s: queued %.0f ms, sent in %.0f ms", dps, queued_ms, sent_ms)
        if echo:
            self.stateReceived.emit(echo, False)

    def _poll(self) -> None:
        try:
            dps = self._call(self._backend.status)
        except BulbError as e:
            self._fail(e)
            return
        self.stateReceived.emit(dps, True)

    def _connect(self) -> None:
        # After a failure, stay "offline" while retrying instead of flickering to "connecting".
        if self._failures == 0:
            self.connectionChanged.emit("connecting", "Conectando…", 0)
        else:
            self.connectionChanged.emit("offline", "Reconectando…", 0)
        try:
            dps = self._call(self._backend.status)
        except BulbError as e:
            self._fail(e)
            return
        self._online = True
        self._failures = 0
        dpset = self._backend.dpset
        if dpset:
            self.dpsetDetected.emit(dpset)
        self.stateReceived.emit(dps, True)
        self.connectionChanged.emit("online", "", 0)
        self._poll_timer.start(self._poll_ms)

    def _fail(self, err: BulbError) -> None:
        log.warning("Bulb communication failed: %s", err)
        self._online = False
        self._poll_timer.stop()
        self._backend.close()
        self._failures += 1

        if self._failures == REDISCOVER_AFTER or (
            self._failures > REDISCOVER_AFTER and self._failures % 6 == 0
        ):
            self.connectionChanged.emit("offline", "Procurando a lâmpada na rede…", 0)
            try:
                new_ip = self._backend.rediscover_ip()
            except Exception:  # noqa: BLE001 - discovery is best effort
                log.exception("Rediscovery failed")
                new_ip = None
            if new_ip:
                self.ipChanged.emit(new_ip)
                self._retry_timer.start(0)
                return

        delay = BACKOFF_SECONDS[min(self._failures - 1, len(BACKOFF_SECONDS) - 1)]
        self.connectionChanged.emit("offline", str(err), delay)
        self._retry_timer.start(delay * 1000)

    @staticmethod
    def _call(fn, *args):
        try:
            return fn(*args)
        except BulbError:
            raise
        except Exception as e:  # noqa: BLE001 - sockets/crypto can raise anything
            log.exception("Unexpected error talking to the bulb")
            raise BulbError("Erro de comunicação com a lâmpada") from e
