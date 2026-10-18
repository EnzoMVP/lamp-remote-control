"""System tray icon: shows on/off (in the bulb's colour), left click toggles the flyout."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Slot
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import autostart


def taskbar_is_light() -> bool:
    """The taskbar follows the *system* theme, which can differ from the apps theme."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def _bulb_path(s: float) -> tuple[QPainterPath, QPainterPath]:
    """Bulb glyph on an s×s canvas: (glass outline, base lines)."""
    u = s / 24.0
    glass = QPainterPath()
    glass.moveTo(9.4 * u, 16.2 * u)
    glass.cubicTo(9.4 * u, 14.6 * u, 8.6 * u, 13.9 * u, 7.7 * u, 13.0 * u)
    glass.cubicTo(6.6 * u, 11.9 * u, 5.8 * u, 10.4 * u, 5.8 * u, 8.8 * u)
    glass.cubicTo(5.8 * u, 5.4 * u, 8.6 * u, 2.6 * u, 12 * u, 2.6 * u)
    glass.cubicTo(15.4 * u, 2.6 * u, 18.2 * u, 5.4 * u, 18.2 * u, 8.8 * u)
    glass.cubicTo(18.2 * u, 10.4 * u, 17.4 * u, 11.9 * u, 16.3 * u, 13.0 * u)
    glass.cubicTo(15.4 * u, 13.9 * u, 14.6 * u, 14.6 * u, 14.6 * u, 16.2 * u)
    glass.closeSubpath()
    base = QPainterPath()
    base.moveTo(9.2 * u, 18.6 * u); base.lineTo(14.8 * u, 18.6 * u)
    base.moveTo(10.2 * u, 21.2 * u); base.lineTo(13.8 * u, 21.2 * u)
    return glass, base


def render_icon(on: bool, color: QColor, status: str, light_taskbar: bool, size: int = 64) -> QIcon:
    fg = QColor(0, 0, 0) if light_taskbar else QColor(255, 255, 255)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    glass, base = _bulb_path(size)
    pen = QPen(fg, size * 0.085, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    reachable = status == "online"
    if on and reachable:
        p.fillPath(glass, color)
        p.setPen(pen)
        p.drawPath(glass)
        p.drawPath(base)
    else:
        if not reachable:
            fg.setAlphaF(0.55)
            pen.setColor(fg)
        p.setPen(pen)
        p.drawPath(glass)
        p.drawPath(base)
        if status == "offline":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#F0A57E"))
            r = size * 0.15
            p.drawEllipse(QPointF(size - r - 1, size - r - 1), r, r)
    p.end()
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, bulb, flyout, parent=None):
        super().__init__(parent)
        self._bulb = bulb
        self._flyout = flyout

        menu = QMenu()
        self._autostart = QAction("Iniciar com o Windows", menu, checkable=True)
        self._autostart.setChecked(autostart.is_enabled())
        self._autostart.toggled.connect(self._on_autostart_toggled)
        menu.addAction(self._autostart)
        menu.addSeparator()
        menu.addAction("Sair", QGuiApplication.quit)
        menu.aboutToShow.connect(lambda: self._autostart.setChecked(autostart.is_enabled()))
        self._menu = menu
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)
        bulb.stateChanged.connect(self.refresh)
        bulb.connectionChanged.connect(self.refresh)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self.refresh)
        self.refresh()

    @Slot()
    def refresh(self):
        b = self._bulb
        self.setIcon(render_icon(b.on, b.color, b.status, taskbar_is_light()))
        if b.status == "unconfigured":
            tip = f"{b.deviceName}: não configurada"
        elif b.status == "offline":
            tip = f"{b.deviceName}: offline"
        elif b.status == "connecting" and not b.ready:
            tip = f"{b.deviceName}: conectando…"
        elif b.on:
            tip = f"{b.deviceName}: ligada · {b.brightness}%"
        else:
            tip = f"{b.deviceName}: desligada"
        self.setToolTip(tip)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._flyout.toggle(self.geometry())

    def _on_autostart_toggled(self, enabled: bool):
        try:
            autostart.set_enabled(enabled)
        except OSError as e:
            self.showMessage("LampRemote", f"Não foi possível alterar a inicialização: {e}",
                             QSystemTrayIcon.MessageIcon.Warning)
            self._autostart.blockSignals(True)
            self._autostart.setChecked(autostart.is_enabled())
            self._autostart.blockSignals(False)
