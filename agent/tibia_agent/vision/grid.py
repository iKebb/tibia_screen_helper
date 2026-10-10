"""Draws a labeled tile grid over the game window so the model can say
"go to tile (+3, -2)" instead of guessing pixels."""

from __future__ import annotations

import cv2
import numpy as np

GRID_COLOR = (255, 255, 255)
PLAYER_COLOR = (0, 255, 255)
LABEL_COLOR = (255, 255, 0)


def draw_grid(img: np.ndarray, tiles_x: int, tiles_y: int, scale: int = 2) -> np.ndarray:
    """Returns an enlarged copy of the game window with the grid and labels.

    Columns are labeled dx (-7..+7) on top and rows dy (-5..+5) on the left;
    the player's tile (0, 0) is outlined in yellow.
    """
    h, w = img.shape[:2]
    big = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
    margin = 28
    out = cv2.copyMakeBorder(big, margin, 0, margin, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    tw, th = big.shape[1] / tiles_x, big.shape[0] / tiles_y
    cx, cy = tiles_x // 2, tiles_y // 2

    for i in range(tiles_x + 1):
        x = margin + round(i * tw)
        cv2.line(out, (x, margin), (x, out.shape[0]), GRID_COLOR, 1)
    for j in range(tiles_y + 1):
        y = margin + round(j * th)
        cv2.line(out, (margin, y), (out.shape[1], y), GRID_COLOR, 1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    for i in range(tiles_x):
        label = f"{i - cx:+d}" if i != cx else "0"
        x = margin + round((i + 0.5) * tw) - 10
        cv2.putText(out, label, (x, 20), font, 0.5, LABEL_COLOR, 1, cv2.LINE_AA)
    for j in range(tiles_y):
        label = f"{j - cy:+d}" if j != cy else "0"
        y = margin + round((j + 0.5) * th) + 5
        cv2.putText(out, label, (2, y), font, 0.45, LABEL_COLOR, 1, cv2.LINE_AA)

    x0, y0 = margin + round(cx * tw), margin + round(cy * th)
    cv2.rectangle(out, (x0, y0), (x0 + round(tw), y0 + round(th)), PLAYER_COLOR, 2)
    return out


def encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()
