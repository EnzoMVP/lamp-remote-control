"""Flyout placement against the real primary screen (taskbar at the bottom)."""

import pytest
from PySide6.QtCore import QRect

from app.flyout import (
    MARGIN_FAR, MARGIN_SIDE, NOTCH_H, NOTCH_MIN_X, PANEL_H, PANEL_W, compute_placement,
)


@pytest.fixture(scope="module")
def screen(qapp):
    return qapp.primaryScreen()


def taskbar_icon(screen, x):
    avail = screen.availableGeometry()
    return QRect(x - 12, avail.bottom() + 8, 24, 24)


def test_notch_points_at_icon(screen):
    avail = screen.availableGeometry()
    if avail.bottom() == screen.geometry().bottom():
        pytest.skip("taskbar is not at the bottom on this machine")
    icon = taskbar_icon(screen, avail.center().x())
    x, y, side, notch_x = compute_placement(icon)
    assert side == "bottom"
    assert x + MARGIN_SIDE + notch_x == icon.center().x()
    tip_y = y + MARGIN_FAR + PANEL_H + NOTCH_H
    assert avail.bottom() - 10 <= tip_y <= avail.bottom() + 1


def test_panel_stays_on_screen_near_right_edge(screen):
    avail = screen.availableGeometry()
    if avail.bottom() == screen.geometry().bottom():
        pytest.skip("taskbar is not at the bottom on this machine")
    icon = taskbar_icon(screen, avail.right() - 5)
    x, _, _, notch_x = compute_placement(icon)
    assert x + MARGIN_SIDE + PANEL_W <= avail.right() + 1
    assert NOTCH_MIN_X <= notch_x <= PANEL_W - NOTCH_MIN_X


def test_no_anchor_falls_back_without_notch(screen):
    _, _, side, _ = compute_placement(None)
    assert side == "none"
