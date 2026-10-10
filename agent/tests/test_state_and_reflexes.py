from tibia_agent.config import Settings
from tibia_agent.reflexes import Reflexes
from tibia_agent.state import GameState


def make_state(hp=100, mana=50, target=None, creatures=()):
    return GameState.from_dict({
        "online": True, "pos": {"x": 100, "y": 100, "z": 7},
        "hp": hp, "max_hp": 100, "mana": mana, "max_mana": 50, "level": 2,
        "target_id": target,
        "creatures": [
            {"id": i, "name": "Rat", "x": x, "y": y, "z": 7, "hp_pct": 100, "kind": k}
            for i, (x, y, k) in enumerate(creatures, start=1)
        ],
    })


def test_offline_state():
    s = GameState.from_dict({"online": False})
    assert not s.online
    assert "no está conectado" in s.summary()


def test_empty_lua_table_is_accepted_as_creature_list():
    s = GameState.from_dict({"online": True, "pos": {"x": 1, "y": 2, "z": 7}, "creatures": {}})
    assert s.creatures == []


def test_summary_lists_relative_positions():
    s = make_state(creatures=[(102, 99, "monster")])
    assert "rel=(+2,-1) dist=2" in s.summary()


def test_heals_when_low_and_respects_cooldown():
    r = Reflexes(Settings(heal_hp_pct=50, heal_mana_cost=20, heal_cooldown=1.0))
    low = make_state(hp=30)
    assert [a.name for a in r.decide(low, now=10.0)] == ["say"]
    assert r.decide(low, now=10.5) == []
    assert [a.name for a in r.decide(low, now=11.1)] == ["say"]


def test_no_heal_without_mana():
    r = Reflexes(Settings())
    assert r.decide(make_state(hp=10, mana=5), now=0) == []


def test_attacks_adjacent_monster_only_when_idle():
    r = Reflexes(Settings())
    near = [(101, 101, "monster"), (105, 100, "monster"), (100, 99, "npc")]
    actions = r.decide(make_state(creatures=near), now=0)
    assert [(a.name, a.args) for a in actions] == [("attack", {"creature_id": 1})]
    assert r.decide(make_state(creatures=near, target=1), now=5) == []
