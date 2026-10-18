"""Render the executable's icon (assets/LampRemote.png); PyInstaller converts it to .ico."""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen, QRadialGradient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.tray import _bulb_path  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "LampRemote.png"


def main():
    QGuiApplication(sys.argv)
    s = 256
    img = QImage(s, s, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1A1916"))
    p.drawRoundedRect(QRectF(8, 8, s - 16, s - 16), 56, 56)

    glow = QRadialGradient(QPointF(s / 2, s * 0.42), s * 0.42)
    glow.setColorAt(0, QColor(255, 200, 130, 150))
    glow.setColorAt(1, QColor(255, 200, 130, 0))
    p.setBrush(glow)
    p.drawRoundedRect(QRectF(8, 8, s - 16, s - 16), 56, 56)

    inner = 176
    p.translate((s - inner) / 2, (s - inner) / 2 + 4)
    glass, base = _bulb_path(inner)
    p.fillPath(glass, QColor("#FFD9A8"))
    pen = QPen(QColor("#F3EFE8"), inner * 0.06, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPath(glass)
    p.drawPath(base)
    p.end()

    OUT.parent.mkdir(exist_ok=True)
    img.save(str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
