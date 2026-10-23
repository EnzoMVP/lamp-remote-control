"""Entry point: wires config, worker thread, controller, flyout and tray icon together."""

from __future__ import annotations

import argparse
import getpass
import logging
import logging.handlers
import os
import sys

from PySide6.QtCore import QMetaObject, Qt, QThread, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import lathe  # noqa: F401 - registers the BulbPart QML type
from .backends import FakeBackend, TuyaBackend
from .bulb_controller import BulbController
from .bulb_worker import BulbWorker
from .config import ConfigError, app_dir, load_config, save_config
from .flyout import FlyoutController
from .settings import load_settings
from .tray import TrayIcon
from .tray_promote import schedule_promote_once
from .voice import VoiceController

log = logging.getLogger("lampremote")
INSTANCE_KEY = f"LampRemote-{getpass.getuser()}"


def setup_logging(verbose: bool):
    app_dir().mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.handlers.RotatingFileHandler(
        app_dir() / "lampremote.log", maxBytes=512_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:  # None in the windowed (no console) executable
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not verbose:
        logging.getLogger("tinytuya").setLevel(logging.WARNING)

    # Without a console, uncaught errors would vanish (or block on PyInstaller's dialog).
    def log_uncaught(exc_type, exc, tb):
        logging.getLogger("lampremote").critical("Uncaught exception", exc_info=(exc_type, exc, tb))
    sys.excepthook = log_uncaught


def parse_args(argv):
    p = argparse.ArgumentParser(prog="LampRemote")
    p.add_argument("--demo", action="store_true", help="usa uma lâmpada simulada")
    p.add_argument("--theme", choices=["dark", "light"], default="", help="força o tema")
    p.add_argument("--open", action="store_true", help="abre o painel ao iniciar")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--screenshot", help=argparse.SUPPRESS)  # dev: open, grab PNG, quit
    p.add_argument("--demo-dps", help=argparse.SUPPRESS)    # dev: initial JSON DPS for --demo
    return p.parse_args(argv)


def notify_running_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"open")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    setup_logging(args.verbose)

    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LampRemote.Tray")

    app = QApplication(sys.argv[:1])
    app.setApplicationName("LampRemote")
    app.setQuitOnLastWindowClosed(False)

    if not args.screenshot and notify_running_instance():
        log.info("Already running; asked the other instance to open its panel")
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "LampRemote", "A bandeja do sistema não está disponível.")
        return 1

    # --- bulb ----------------------------------------------------------------------
    worker = thread = None
    config_error = None
    cfg = None
    if args.demo:
        backend, name, ip = FakeBackend(), "Lâmpada demo", "simulada"
        if args.demo_dps:
            import json
            backend._dps.update(json.loads(args.demo_dps))
    else:
        try:
            cfg = load_config()
            backend, name, ip = TuyaBackend(cfg), cfg.name, cfg.ip
        except ConfigError as e:
            log.warning("Config: %s", e)
            backend, name, ip, config_error = None, "Lâmpada", "", str(e)

    if backend is not None:
        worker = BulbWorker(backend)
        thread = QThread()
        thread.setObjectName("bulb-worker")
        worker.moveToThread(thread)
        thread.started.connect(worker.start)

    bulb = BulbController(worker, name, ip, config_error)

    if worker is not None and cfg is not None:
        def remember_ip(new_ip: str):
            cfg.ip = new_ip
            try:
                save_config(cfg)
            except OSError:
                log.exception("Could not save the new IP")
        worker.ipChanged.connect(remember_ip)

    # --- UI ------------------------------------------------------------------------
    try:
        flyout = FlyoutController(bulb, theme_override=args.theme)
    except RuntimeError as e:
        QMessageBox.critical(None, "LampRemote", str(e))
        return 1
    voice = VoiceController(bulb, load_settings())
    tray = TrayIcon(bulb, flyout, voice)
    tray.show()
    if not args.screenshot:
        schedule_promote_once(tray)

    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_KEY)
    server.listen(INSTANCE_KEY)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), flyout.open(tray.geometry())))

    def shutdown():
        log.info("LampRemote quitting")
        tray.hide()
        voice.shutdown()
        flyout.unload()  # tear QML down while `bulb`/`flyout` still exist
        if thread is not None:
            QMetaObject.invokeMethod(worker, "stop", Qt.ConnectionType.BlockingQueuedConnection)
            thread.quit()
            thread.wait(3000)
    app.aboutToQuit.connect(shutdown)

    if thread is not None:
        thread.start()
    if not args.screenshot:
        voice.start()

    if args.open or args.screenshot:
        QTimer.singleShot(400, lambda: flyout.open(tray.geometry()))
    if args.screenshot:
        def grab():
            flyout.view.grabWindow().save(args.screenshot)
            app.quit()
        QTimer.singleShot(int(os.environ.get("LAMPREMOTE_SHOT_DELAY_MS", "2200")), grab)

    log.info("LampRemote started (%s)", "demo" if args.demo else ip or "unconfigured")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
