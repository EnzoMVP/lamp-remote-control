"""Procedural 3D geometry for the bulb: each part is a profile revolved around the Y axis.

Exposed to QML as `LampRemote.BulbPart { part: "glass" }`. Units are millimetres
of a ~110 mm tall A60 bulb, origin at the bottom contact.
"""

from __future__ import annotations

import math
from array import array

from PySide6.QtCore import Property, QByteArray, Signal
from PySide6.QtGui import QVector3D
from PySide6.QtQml import QmlElement
from PySide6.QtQuick3D import QQuick3DGeometry

QML_IMPORT_NAME = "LampRemote"
QML_IMPORT_MAJOR_VERSION = 1

SEGMENTS = 72
BULB_HEIGHT = 110.0


def _arc(cx, cy, radius, deg_from, deg_to, steps):
    out = []
    for i in range(steps + 1):
        a = math.radians(deg_from + (deg_to - deg_from) * i / steps)
        out.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return out


def _glass():
    # Frosted dome: sphere R=30 centred at y=80, closing just under the body rim.
    pts = [(max(0.0, r), y) for r, y in _arc(0, 80, 30, 90, -42, 48)]
    pts[0] = (0.0, 110.0)
    return pts + [(21.6, 59.4)]


def _body():
    # White plastic housing: concave taper from the dome down to the E27 collar.
    pts = [(21.0, 62.2), (23.3, 61.4), (23.6, 60.6)]
    steps = 28
    for i in range(1, steps + 1):
        t = i / steps
        ease = (1 - math.cos(math.pi * t)) / 2
        y = 60.6 - (60.6 - 31.0) * t
        r = 23.6 - (23.6 - 14.8) * (0.55 * t + 0.45 * ease)
        pts.append((r, y))
    return pts + [(14.8, 29.8), (13.9, 29.2), (13.6, 28.6)]


def _screw():
    # E27 thread approximated by sinusoidal rings (pitch 3.6 mm).
    pts = []
    y = 28.6
    while y > 8.0:
        pts.append((13.15 + 0.85 * math.sin(2 * math.pi * (y - 8.0) / 3.6), y))
        y -= 0.3
    return pts + [(12.6, 7.6), (11.2, 6.6)]


def _insulator():
    return [(11.4, 6.8), (10.4, 5.4), (8.4, 4.4), (5.6, 4.0)]


def _tip():
    return [(5.8, 4.1), (5.0, 3.4), (4.0, 2.4), (2.0, 1.9), (0.0, 1.8)]


PROFILES = {"glass": _glass, "body": _body, "screw": _screw, "insulator": _insulator, "tip": _tip}


def build_lathe(profile, segments=SEGMENTS):
    """Returns (vertex floats [x,y,z,nx,ny,nz]*, uint32 indices, min, max)."""
    n = len(profile)
    normals2d = []
    for i in range(n):
        r0, y0 = profile[max(i - 1, 0)]
        r1, y1 = profile[min(i + 1, n - 1)]
        tr, ty = r1 - r0, y1 - y0
        nr, ny = -ty, tr
        length = math.hypot(nr, ny) or 1.0
        normals2d.append((nr / length, ny / length))

    verts = array("f")
    for i, (r, y) in enumerate(profile):
        nr, ny = normals2d[i]
        for j in range(segments + 1):
            phi = 2 * math.pi * j / segments
            c, s = math.cos(phi), math.sin(phi)
            verts.extend((r * c, y, r * s, nr * c, ny, nr * s))

    idx = array("I")
    row = segments + 1
    for i in range(n - 1):
        for j in range(segments):
            a, b = i * row + j, (i + 1) * row + j
            c, d = a + 1, b + 1
            idx.extend((a, c, b, b, c, d))

    rmax = max(r for r, _ in profile)
    ys = [y for _, y in profile]
    return verts, idx, (-rmax, min(ys), -rmax), (rmax, max(ys), rmax)


@QmlElement
class BulbPart(QQuick3DGeometry):
    partChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._part = ""

    def _get_part(self):
        return self._part

    def _set_part(self, part):
        if part == self._part or part not in PROFILES:
            return
        self._part = part
        self._rebuild()
        self.partChanged.emit()

    part = Property(str, _get_part, _set_part, notify=partChanged)

    def _rebuild(self):
        verts, idx, lo, hi = build_lathe(PROFILES[self._part]())
        self.clear()
        self.setVertexData(QByteArray(verts.tobytes()))
        self.setIndexData(QByteArray(idx.tobytes()))
        self.setStride(6 * 4)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        A = QQuick3DGeometry.Attribute
        self.addAttribute(A.Semantic.PositionSemantic, 0, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.NormalSemantic, 12, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.IndexSemantic, 0, A.ComponentType.U32Type)
        self.setBounds(QVector3D(*lo), QVector3D(*hi))
        self.update()
