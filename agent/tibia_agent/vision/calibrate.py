"""Calibration tool: tells the agent where each part of the interface is on screen.

    tibia-calibrate                  # capture the screen and select each region
    tibia-calibrate --image shot.png # select regions on a saved screenshot
    tibia-calibrate --check          # read the screen once with the saved calibration
                                     # and save an annotated image to verify it

Selecting a region opens a window: drag a rectangle, then press Enter (or
Space). If the OpenCV window can't open, it asks for the coordinates in the
terminal instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from ..config import Settings
from .calibration import REGION_HELP, REGION_NAMES, Calibration, Region
from .readers import read_bar_pct, read_battle_list

COLORS = {
    "hp_bar": (0, 0, 255), "mana_bar": (255, 0, 0), "battle_list": (0, 255, 255),
    "game_window": (0, 255, 0), "minimap": (255, 0, 255),
}


def load_screen(image: str | None) -> np.ndarray:
    if image:
        img = cv2.imread(image)
        if img is None:
            raise SystemExit(f"Could not read {image}")
        return img
    from .capture import ScreenCapture

    return ScreenCapture().grab_full()


def ask_region_terminal(name: str) -> Region:
    print(f"\nRegion '{name}': {REGION_HELP[name]}")
    while True:
        raw = input("  left top width height (pixels, separated by spaces): ").split()
        try:
            left, top, width, height = (int(v) for v in raw)
            if width > 0 and height > 0:
                return Region(left, top, width, height)
        except ValueError:
            pass
        print("  Please enter four positive integers.")


def select_regions(screen: np.ndarray) -> dict[str, Region]:
    regions: dict[str, Region] = {}
    use_gui = True
    for name in REGION_NAMES:
        if use_gui:
            print(f"Select {REGION_HELP[name]} and press Enter.")
            try:
                x, y, w, h = cv2.selectROI(f"Select: {name}", screen, showCrosshair=False)
                cv2.destroyAllWindows()
                if w > 0 and h > 0:
                    regions[name] = Region(int(x), int(y), int(w), int(h))
                    continue
                print("  Empty selection, asking in the terminal instead.")
            except cv2.error:
                print("OpenCV can't open a window here (install opencv-python, not the "
                      "headless build). Asking in the terminal instead.")
                use_gui = False
        regions[name] = ask_region_terminal(name)
    return regions


def check(cal: Calibration, screen: np.ndarray, out: Path) -> None:
    def crop(r: Region) -> np.ndarray:
        return screen[r.top:r.top + r.height, r.left:r.left + r.width]

    hp = read_bar_pct(crop(cal.region("hp_bar")))
    mana = read_bar_pct(crop(cal.region("mana_bar")))
    battle = read_battle_list(crop(cal.region("battle_list")))
    print(f"Health: {hp}%  Mana: {mana}%  Battle list: {battle.monsters} creatures, "
          f"target: {'yes' if battle.has_target else 'no'}")

    annotated = screen.copy()
    for name, r in cal.regions.items():
        color = COLORS.get(name, (255, 255, 255))
        cv2.rectangle(annotated, (r.left, r.top), (r.left + r.width, r.top + r.height), color, 2)
        cv2.putText(annotated, name, (r.left, max(12, r.top - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    gw = cal.region("game_window")
    for dx, dy in ((0, 0), (-(cal.tiles_x // 2), -(cal.tiles_y // 2)), (cal.tiles_x // 2, cal.tiles_y // 2)):
        cv2.drawMarker(annotated, cal.tile_center(dx, dy), (0, 255, 255), cv2.MARKER_CROSS, 12, 2)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), annotated)
    print(f"Annotated image saved to {out}. The yellow crosses must sit on the center of "
          f"your character's tile and on the two corner tiles of the game window ({gw.width}x{gw.height} px).")


def main() -> None:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Calibrate the screen regions for vision mode.")
    parser.add_argument("--image", help="use a saved screenshot instead of capturing the screen")
    parser.add_argument("--output", default=settings.calibration_file, help="calibration file")
    parser.add_argument("--check", action="store_true", help="verify an existing calibration")
    parser.add_argument("--tiles", default="15x11", help="visible tiles in the game window (default 15x11)")
    args = parser.parse_args()

    screen = load_screen(args.image)
    path = Path(args.output)
    if args.check:
        check(Calibration.load(path), screen, Path(settings.runs_dir) / "calibration_check.png")
        return

    tiles_x, tiles_y = (int(v) for v in args.tiles.lower().split("x"))
    cal = Calibration(select_regions(screen), tiles_x, tiles_y,
                      meta={"screen_size": [int(screen.shape[1]), int(screen.shape[0])]})
    cal.save(path)
    print(f"\nCalibration saved to {path}. Verify it with: tibia-calibrate --check")


if __name__ == "__main__":
    main()
