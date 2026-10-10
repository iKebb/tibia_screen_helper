"""Vision mode tests. The mock screen is drawn off-screen with pygame, so the
readers are checked against images whose true values are known."""

import asyncio
import os

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")
pygame = pytest.importorskip("pygame")

from tibia_agent.config import Settings
from tibia_agent.planners import ToolCall
from tibia_agent.planners.vision_rules import VisionRulePlanner
from tibia_agent.vision.agent import VisionAgent
from tibia_agent.vision.calibration import Calibration, Region
from tibia_agent.vision.grid import draw_grid, encode_png
from tibia_agent.vision.inputs import DryRunInput
from tibia_agent.vision.mock_screen import GAME, ScreenMock, mock_calibration
from tibia_agent.vision.perception import Perception, VisionState
from tibia_agent.vision.readers import read_bar_pct, read_battle_list
from tibia_agent.vision.reflexes import VisionReflexes
from tibia_agent.mock_game import Monster


@pytest.fixture(scope="module")
def pg():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    yield pygame
    pygame.quit()


def render(pg, mock: ScreenMock) -> np.ndarray:
    from tibia_agent.vision.mock_screen import WINDOW_SIZE

    surface = pg.Surface(WINDOW_SIZE)
    mock.draw(surface, pg, pg.font.Font(None, 16))
    rgb = pg.surfarray.array3d(surface).swapaxes(0, 1)
    return np.ascontiguousarray(rgb[..., ::-1])  # RGB -> BGR, like mss


class FrameCapture:
    """Fake ScreenCapture that crops regions from a fixed frame."""

    def __init__(self, frame):
        self.frame = frame

    def grab(self, r: Region):
        return self.frame[r.top:r.top + r.height, r.left:r.left + r.width]


def place_rats(mock: ScreenMock, *offsets):
    mock.sim.monsters.clear()
    ids = []
    for i, (dx, dy) in enumerate(offsets):
        m = Monster(100 + i, mock.sim.x + dx, mock.sim.y + dy)
        mock.sim.monsters[m.id] = m
        ids.append(m.id)
    return ids


@pytest.mark.parametrize("hp,mana", [(150, 50), (75, 10), (30, 0), (1, 49)])
def test_reads_bars_on_mock_screen(pg, hp, mana):
    mock = ScreenMock(seed=1)
    mock.sim.hp, mock.sim.mana = hp, mana
    state = Perception(mock_calibration(), FrameCapture(render(pg, mock))).read()
    assert abs(state.hp_pct - round(100 * hp / 150)) <= 2
    assert abs(state.mana_pct - round(100 * mana / 50)) <= 2


def test_reads_battle_list_on_mock_screen(pg):
    mock = ScreenMock(seed=1)
    cal = mock_calibration()
    place_rats(mock)
    assert Perception(cal, FrameCapture(render(pg, mock))).read().monsters == 0

    ids = place_rats(mock, (1, 0), (3, 2), (-5, -4))
    mock.sim.monsters[ids[1]].hp = 1  # almost dead: tiny health bar
    state = Perception(cal, FrameCapture(render(pg, mock))).read()
    assert (state.monsters, state.has_target) == (3, False)

    mock.sim.target = ids[2]
    state = Perception(cal, FrameCapture(render(pg, mock))).read()
    assert (state.monsters, state.has_target) == (3, True)


def test_bar_reader_ignores_empty_and_text():
    bar = np.full((12, 200, 3), 40, np.uint8)
    assert read_bar_pct(bar) == 0
    bar[:, :120] = (40, 40, 210)  # red fill (BGR)
    cv2.putText(bar, "90 / 150", (70, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    assert read_bar_pct(bar) == 60


def test_battle_list_reader_on_empty_image():
    assert read_battle_list(np.zeros((0, 0, 3), np.uint8)).monsters == 0


def test_tile_center_and_bounds():
    cal = mock_calibration()
    assert cal.tile_center(0, 0) == (GAME.left + 7 * 32 + 16, GAME.top + 5 * 32 + 16)
    assert cal.tile_center(-7, -5) == (GAME.left + 16, GAME.top + 16)
    assert cal.tile_in_view(7, 5) and not cal.tile_in_view(8, 0)


def test_calibration_roundtrip(tmp_path):
    cal = mock_calibration()
    cal.save(tmp_path / "c.json")
    assert Calibration.load(tmp_path / "c.json").regions == cal.regions


def test_grid_image_is_png():
    img = np.zeros((352, 480, 3), np.uint8)
    grid = draw_grid(img, 15, 11)
    assert grid.shape[0] > 352 * 2 and encode_png(grid)[:4] == b"\x89PNG"


def test_vision_reflexes():
    r = VisionReflexes(Settings(heal_hp_pct=50, heal_key="f1", attack_key="space"))
    assert r.decide(VisionState(30, 50, 2, False), now=0) == ["f1", "space"]
    assert r.decide(VisionState(30, 50, 2, False), now=0.5) == []
    assert r.decide(VisionState(90, 50, 2, True), now=5) == []


async def test_vision_rule_planner():
    p = VisionRulePlanner(seed=1)
    plan = await p.plan("", VisionState(100, 100, 2, False).summary(), "", [])
    assert [c.name for c in plan.calls] == ["attack_next"]


async def test_vision_agent_tools_drive_mock_through_input(pg, tmp_path):
    """Tools produce real key presses and clicks that move the mock character."""
    mock = ScreenMock(seed=1)
    place_rats(mock)
    controller = DryRunInput()
    agent = VisionAgent(Settings(runs_dir=str(tmp_path)), VisionRulePlanner(), mock_calibration(),
                        FrameCapture(render(pg, mock)), controller, tmp_path)
    start = (mock.sim.x, mock.sim.y)

    assert (await agent.execute(ToolCall("walk", {"direction": "east", "steps": 2})))["ok"]
    assert (await agent.execute(ToolCall("click_tile", {"dx": 3, "dy": -2})))["ok"]
    assert not (await agent.execute(ToolCall("click_tile", {"dx": 9, "dy": 0})))["ok"]

    for event in controller.events:  # replay the inputs into the mock
        if event[0] == "press":
            mock.on_key(event[1], "")
        elif event[0] == "click":
            mock.on_click(event[1], event[2])
    for _ in range(20):
        mock.sim.tick()
    assert (mock.sim.x, mock.sim.y) == (start[0] + 2 + 3, start[1] - 2)


def test_calibration_check_marks_corner_tiles(pg, tmp_path, capsys):
    from tibia_agent.vision.calibrate import check

    mock = ScreenMock(seed=1)
    mock.sim.hp = 60
    cal = mock_calibration()
    check(cal, render(pg, mock), tmp_path / "check.png")
    assert "Health: 40%" in capsys.readouterr().out
    annotated = cv2.imread(str(tmp_path / "check.png"))
    for dx, dy in ((0, 0), (-7, -5), (7, 5)):
        x, y = cal.tile_center(dx, dy)
        assert tuple(annotated[y, x]) == (0, 255, 255)  # yellow cross (BGR)
