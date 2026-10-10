"""Fast screen capture of calibrated regions (mss)."""

from __future__ import annotations

import numpy as np

from .calibration import Region


class ScreenCapture:
    def __init__(self):
        import mss  # imported here so the rest of the package works without a display

        self._sct = mss.mss()

    def grab(self, region: Region) -> np.ndarray:
        """Returns the region as a BGR image."""
        shot = np.asarray(self._sct.grab(region.as_mss()))
        return np.ascontiguousarray(shot[..., :3])

    def grab_full(self) -> np.ndarray:
        monitor = self._sct.monitors[0]  # all monitors together
        shot = np.asarray(self._sct.grab(monitor))
        return np.ascontiguousarray(shot[..., :3])
