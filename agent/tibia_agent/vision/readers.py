"""Classic computer vision readers (no AI). They run every ~150 ms.

All functions take BGR images (numpy arrays) cropped to one calibrated region.
They rely on color saturation: in Tibia, bars and creature health bars are
strongly colored, while backgrounds, borders and text are dark or gray.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# HSV thresholds for "colored" pixels (OpenCV range: S and V go from 0 to 255).
MIN_SATURATION = 90
MIN_VALUE = 90


def colored_mask(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hsv[..., 1] >= MIN_SATURATION) & (hsv[..., 2] >= MIN_VALUE)


def red_mask(img: np.ndarray) -> np.ndarray:
    b, g, r = (img[..., i].astype(int) for i in range(3))
    return (r >= 170) & (g <= 70) & (b <= 70)


def read_bar_pct(img: np.ndarray, min_column_fill: float = 0.3) -> int:
    """Fill percentage of a horizontal bar (health or mana).

    A column counts as filled when at least `min_column_fill` of its pixels are
    colored. The percentage is the position of the last filled column, which
    tolerates the white "150 / 150" text drawn over the bar.
    """
    if img.size == 0:
        return 0
    filled_cols = np.flatnonzero(colored_mask(img).mean(axis=0) >= min_column_fill)
    if filled_cols.size == 0:
        return 0
    return round(100 * (filled_cols[-1] + 1) / img.shape[1])


@dataclass
class BattleList:
    monsters: int
    has_target: bool


def _bands(rows: np.ndarray, min_gap: int) -> int:
    """Counts groups of consecutive row indices separated by at least min_gap."""
    if rows.size == 0:
        return 0
    return 1 + int(np.count_nonzero(np.diff(rows) > min_gap))


def read_battle_list(img: np.ndarray, icon_fraction: float = 0.25) -> BattleList:
    """Counts creatures in the battle list and detects whether one is targeted.

    Each entry has a creature icon on the left, and its name (white/gray text)
    with a colored health bar on the right. The health bar is the only colored
    thing on the right, so each separate band of rows with colored pixels is
    one creature; even an almost empty bar keeps a few colored pixels. The
    attack target has a red frame around its icon, so red pixels in the left
    strip mean "has target".
    """
    if img.size == 0:
        return BattleList(0, False)
    split = max(1, int(img.shape[1] * icon_fraction))
    right = img[:, split:]
    bar_rows = np.flatnonzero(colored_mask(right).sum(axis=1) >= 2)
    monsters = _bands(bar_rows, min_gap=3)
    red_left = red_mask(img[:, :split])
    has_target = monsters > 0 and int(red_left.sum()) >= 10
    return BattleList(monsters, has_target)
