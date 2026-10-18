"""The flyout window: frameless, translucent, anchored above the tray icon.

Behaves like Windows' own quick panels: opens next to the icon, closes when it
loses focus (click outside) or on Esc, and clicking the tray icon toggles it.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import Property, QObject, QRect, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtQuick import QQuickView

from .config import config_path

log = logging.getLogger(__name__)

PANEL_W = 372
PANEL_H = 632
NOTCH_H = 10
MARGIN_SIDE = 24   # room for the shadow left/right
MARGIN_FAR = 26    # shadow room on the side away from the taskbar
MARGIN_NEAR = 16   # shadow room on the taskbar side (below the notch)
SCREEN_GAP = 12    # minimum distance between panel and screen edges
TASKBAR_GAP = 4    # distance between notch tip and taskbar
REOPEN_GUARD_S = 0.35
# The notch must stay on the straight part of the edge (panel radius 26 + notch half-width 17).
NOTCH_MIN_X = 26 + 17

QML_DIR = Path(__file__).resolve().parent / "qml"


class FlyoutController(QObject):
    """Exposed to QML as `flyout`."""

    geometryChanged = Signal()
    shownChanged = Signal()

    def __init__(self, bulb, theme_override: str = "", parent=None):
        super().__init__(parent)
        self._bulb = bulb
        self._shown = False
        self._notch_side = "bottom"
        self._notch_x = PANEL_W / 2
        self._last_hide = 0.0

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(120)  # let the fade-out play
        self._hide_timer.timeout.connect(self._hide_now)

        self.view = QQuickView()
        self.view.setFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                           | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint)
        self.view.setColor(QColor(Qt.GlobalColor.transparent))
        fmt = self.view.format()
        fmt.setAlphaBufferSize(8)
        self.view.setFormat(fmt)
        self.view.setTitle("LampRemote")
        self.view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self.view.resize(self.windowWidth, self.windowHeight)
        self.view.activeChanged.connect(self._on_active_changed)

        ctx = self.view.engine().rootContext()
        ctx.setContextProperty("bulb", bulb)
        ctx.setContextProperty("flyout", self)
        ctx.setContextProperty("themeOverride", theme_override)
        self.view.engine().addImportPath(str(QML_DIR))
        # QML runtime warnings arrive on the GUI thread; a Python qInstallMessageHandler
        # can deadlock against the threaded render loop, so don't use one.
        self.view.engine().warnings.connect(
            lambda errors: [log.warning("QML: %s", e.toString()) for e in errors])
        self.view.setSource(QUrl.fromLocalFile(str(QML_DIR / "Flyout.qml")))
        for err in self.view.errors():
            log.error("QML: %s", err.toString())
        if self.view.status() == QQuickView.Status.Error:
            raise RuntimeError("Falha ao carregar a interface (veja o log)")

    # --- properties for QML ------------------------------------------------------------
    windowWidth = Property(int, lambda self: PANEL_W + 2 * MARGIN_SIDE, constant=True)
    windowHeight = Property(int, lambda self: PANEL_H + NOTCH_H + MARGIN_FAR + MARGIN_NEAR, constant=True)
    panelWidth = Property(int, lambda self: PANEL_W, constant=True)
    panelHeight = Property(int, lambda self: PANEL_H, constant=True)
    marginSide = Property(int, lambda self: MARGIN_SIDE, constant=True)

    def _panel_y(self):
        return MARGIN_NEAR + NOTCH_H if self._notch_side == "top" else MARGIN_FAR

    panelY = Property(int, _panel_y, notify=geometryChanged)
    notchSide = Property(str, lambda self: self._notch_side, notify=geometryChanged)
    notchX = Property(float, lambda self: self._notch_x, notify=geometryChanged)
    shown = Property(bool, lambda self: self._shown, notify=shownChanged)

    # --- open / close ----------------------------------------------------------------
    def is_open(self) -> bool:
        return self.view.isVisible() and self._shown

    def toggle(self, anchor: QRect | None):
        if self.is_open():
            self.close()
        elif time.monotonic() - self._last_hide < REOPEN_GUARD_S:
            # This click is the one that just closed us (focus moved to the taskbar).
            return
        else:
            self.open(anchor)

    def open(self, anchor: QRect | None = None):
        self._hide_timer.stop()
        self._place(anchor)
        if not self.view.isVisible():
            self._set_shown(False)
            self.view.show()
        _disable_dwm_rounding(int(self.view.winId()))
        self.view.raise_()
        self.view.requestActivate()
        _force_foreground(int(self.view.winId()))
        QTimer.singleShot(16, lambda: self._set_shown(True))
        self._bulb.setPanelVisible(True)

    @Slot()
    def close(self):
        if not self.view.isVisible():
            return
        self._last_hide = time.monotonic()
        self._set_shown(False)
        self._hide_timer.start()

    def _hide_now(self):
        if not self._shown:
            self.view.hide()
            self._bulb.setPanelVisible(False)

    def _set_shown(self, value: bool):
        if value != self._shown:
            self._shown = value
            self.shownChanged.emit()

    def _on_active_changed(self):
        log.debug("Flyout active=%s shown=%s", self.view.isActive(), self._shown)
        if not self.view.isActive() and self._shown:
            self.close()

    def unload(self):
        self.view.hide()
        self.view.setSource(QUrl())

    @Slot()
    def openConfigFolder(self):
        folder = config_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        self.close()

    # --- positioning ----------------------------------------------------------------
    def _place(self, anchor: QRect | None):
        x, y, side, notch_x = compute_placement(anchor)
        self._notch_side, self._notch_x = side, notch_x
        self.geometryChanged.emit()
        self.view.setPosition(x, y)


def compute_placement(anchor: QRect | None):
    """Returns (window_x, window_y, notch_side, notch_x_in_panel)."""
    screen = None
    if anchor is not None and anchor.isValid() and not anchor.isEmpty():
        screen = QGuiApplication.screenAt(anchor.center())
    screen = screen or QGuiApplication.primaryScreen()
    geo, avail = screen.geometry(), screen.availableGeometry()

    if avail.bottom() < geo.bottom():
        edge = "bottom"
    elif avail.top() > geo.top():
        edge = "top"
    elif avail.left() > geo.left():
        edge = "left"
    elif avail.right() < geo.right():
        edge = "right"
    else:
        edge = "bottom"  # auto-hidden taskbar: assume the default position

    # The icon must sit on the taskbar itself; icons in the overflow ("^") menu don't.
    on_taskbar = anchor is not None and anchor.isValid() and not anchor.isEmpty() and (
        (edge == "bottom" and anchor.top() >= avail.bottom() - 2)
        or (edge == "top" and anchor.bottom() <= avail.top() + 2)
    )
    if anchor is not None and anchor.isValid() and edge == "bottom" and avail == geo:
        on_taskbar = anchor.top() >= geo.bottom() - 80

    win_h = PANEL_H + NOTCH_H + MARGIN_FAR + MARGIN_NEAR
    if on_taskbar:
        ax = anchor.center().x()
        side = edge
    else:
        ax = avail.right() - 160  # roughly above the clock / quick settings
        side = "none"

    panel_left = max(avail.left() + SCREEN_GAP, min(avail.right() + 1 - SCREEN_GAP - PANEL_W, ax - PANEL_W // 2))
    if edge == "left":
        panel_left = avail.left() + SCREEN_GAP
    elif edge == "right":
        panel_left = avail.right() + 1 - SCREEN_GAP - PANEL_W
    notch_x = float(max(NOTCH_MIN_X, min(PANEL_W - NOTCH_MIN_X, ax - panel_left)))

    if side == "bottom":
        tip_y = avail.bottom() + 1 - TASKBAR_GAP
        y = tip_y - (MARGIN_FAR + PANEL_H + NOTCH_H)
    elif side == "top":
        y = avail.top() + TASKBAR_GAP - MARGIN_NEAR
    elif edge == "top":
        y = avail.top() + SCREEN_GAP - MARGIN_FAR
    else:
        y = avail.bottom() + 1 - SCREEN_GAP - PANEL_H - MARGIN_FAR

    # Never leave the screen if it is shorter than the panel.
    y = max(geo.top() - MARGIN_FAR, min(y, geo.bottom() + 1 - win_h + MARGIN_NEAR))
    return panel_left - MARGIN_SIDE, y, side, notch_x


# --- Win32 helpers --------------------------------------------------------------------

def _disable_dwm_rounding(hwnd: int):
    """Windows 11 may round/border frameless windows; we draw our own shape."""
    if sys.platform != "win32":
        return
    DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND = 33, 1
    DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE = 34, 0xFFFFFFFE
    try:
        dwm = ctypes.windll.dwmapi
        v = ctypes.c_int(DWMWCP_DONOTROUND)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(v), 4)
        c = ctypes.c_uint(DWMWA_COLOR_NONE)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_BORDER_COLOR, ctypes.byref(c), 4)
    except (OSError, AttributeError):
        pass


def _force_foreground(hwnd: int):
    """Make sure the flyout really gets focus, so clicking elsewhere deactivates it.

    Windows only lets the foreground process hand out focus. A tray click usually
    grants it, but when it doesn't we briefly attach to the foreground thread.
    """
    if sys.platform != "win32" or os.environ.get("LAMPREMOTE_NO_FOREGROUND"):
        return
    user32 = ctypes.windll.user32
    if user32.GetForegroundWindow() == hwnd:
        return
    if user32.SetForegroundWindow(hwnd):
        log.debug("SetForegroundWindow ok")
        return
    log.debug("SetForegroundWindow refused; attaching to the foreground thread")
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    our_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    if fg_thread and fg_thread != our_thread:
        user32.AttachThreadInput(our_thread, fg_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.AttachThreadInput(our_thread, fg_thread, False)
