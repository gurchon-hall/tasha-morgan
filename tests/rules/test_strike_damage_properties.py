"""Strike damage properties (ENG-048): an aggravated `StrikeDamage` reaches
`apply_damage` as aggravated, and "hand strike at +N" cards (Dust Up, Slam)
inherit every property of the base hand strike [TOM 19960225]."""

from dataclasses import replace

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import dust_up, opikun, rolling_with_the_punches, slam, soak
from vtesbot.engine import combat, hooks
from vtesbot.engine.cards import LibraryCard, Sect
from vtesbot.engine.combat import (
    COMBAT_DODGE_OPTION_HOOK,
    COMBAT_STRIKE_OPTION_HOOK,
    COMMITTED_STRIKE_KEY,
    LONG_RANGE,
    StrikeDamage,
    run_combat,
)
from vtesbot.engine.decision import Choice


def _combat_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=5)
    return builder.build()


def _agents(game, actor_strike: str):
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", actor_strike)
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender
    return actor, defender


def test_aggravated_strike_is_applied_as_aggravated_damage(monkeypatch):
    def fake_strike(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("fake_aggravated", "Fake aggravated strike"),
                apply=lambda s: StrikeDamage(2, aggravated=True),
            )
        ]

    hooks.register(COMBAT_STRIKE_OPTION_HOOK, fake_strike)
    applied = []
    real_apply = combat.apply_damage

    def spy(state, player, vampire, normal=0, aggravated=0, **kwargs):
        applied.append((vampire.instance_id, normal, aggravated))
        return real_apply(state, player, vampire, normal=normal, aggravated=aggravated, **kwargs)

    monkeypatch.setattr(combat, "apply_damage", spy)
    game = _combat_game()
    actor, defender = _agents(game, "fake_aggravated")

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert applied == [("B1", 0, 2)]
    # Rulebook §4 Aggravated damage: the first point wounds a healthy vampire
    # (torpor); each further point burns 1 blood.
    assert game.zone_of("B1") == "torpor"
    assert game.vampire("B1").blood == 4
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_plain_hand_strike_is_normal_dodgeable_damage():
    game = _combat_game()
    base = combat.hand_strike_damage(game.state, "P1", "V1", "B1")
    assert base == StrikeDamage(1)


def _anarch_game(disciplines: tuple[str, ...], card: LibraryCard, blood: int = 2):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=blood, disciplines=disciplines
    )
    p1.hand.append(card)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=2)
    game = builder.build()
    game.vampire("V1").card = replace(game.vampire("V1").card, sect=Sect.ANARCH)
    return game


def _aggravated_base(*args, **kwargs):
    return StrikeDamage(1, aggravated=True)


def test_dust_up_strikes_inherit_base_damage_properties(monkeypatch):
    monkeypatch.setattr(dust_up, "hand_strike_damage", _aggravated_base)
    game = _anarch_game(
        ("ani", "pot"), LibraryCard(krcg_id=dust_up.KRCG_ID, name="Dust Up", card_type="combat")
    )
    ctx = {"player": "P1", "vampire": "V1", "opponent": "B1"}

    [ani] = dust_up._ani_strike(game.state, ctx)
    assert ani.apply(game.state) == StrikeDamage(2, ignore_dodge=True, aggravated=True)

    game.state.players["P1"].hand.append(
        LibraryCard(krcg_id=dust_up.KRCG_ID, name="Dust Up", card_type="combat")
    )
    [pot] = dust_up._pot_strike(game.state, ctx)
    assert pot.apply(game.state) == StrikeDamage(3, aggravated=True)


def test_slam_strike_inherits_base_damage_properties(monkeypatch):
    monkeypatch.setattr(slam, "hand_strike_damage", _aggravated_base)
    game = _anarch_game(
        ("pot",), LibraryCard(krcg_id=slam.KRCG_ID, name="Slam", card_type="combat")
    )
    ctx = {"player": "P1", "vampire": "V1", "opponent": "B1"}

    [basic] = slam._provide_basic(game.state, ctx)
    assert basic.apply(game.state) == StrikeDamage(3, aggravated=True)


def _spy_apply_damage(monkeypatch) -> list[tuple[str, int, int]]:
    applied: list[tuple[str, int, int]] = []
    real_apply = combat.apply_damage

    def spy(state, player, vampire, normal=0, aggravated=0, **kwargs):
        applied.append((vampire.instance_id, normal, aggravated))
        return real_apply(state, player, vampire, normal=normal, aggravated=aggravated, **kwargs)

    monkeypatch.setattr(combat, "apply_damage", spy)
    return applied


def _p2_dodges(state, context):
    if context.get("player") != "P2":
        return []
    return [hooks.HookOption(choice=Choice("fake_dodge", "Fake dodge"), apply=lambda s: None)]


def _dust_up_vs_dodge(monkeypatch, strike: str):
    monkeypatch.setattr(dust_up, "hand_strike_damage", _aggravated_base)
    hooks.register(COMBAT_DODGE_OPTION_HOOK, _p2_dodges)
    applied = _spy_apply_damage(monkeypatch)
    game = _anarch_game(
        ("ani", "pot"), LibraryCard(krcg_id=dust_up.KRCG_ID, name="Dust Up", card_type="combat")
    )
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", strike)
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "fake_dodge")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender
    return game, actor, defender, applied


def test_dodge_proof_inherited_aggravated_strike_lands_through_run_combat(monkeypatch):
    game, actor, defender, applied = _dust_up_vs_dodge(monkeypatch, "dust_up:ani")

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert applied == [("B1", 0, 2)]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_dodgeable_inherited_aggravated_strike_is_dodged(monkeypatch):
    game, actor, defender, applied = _dust_up_vs_dodge(monkeypatch, "dust_up:pot")
    actor.expect("press", "end_combat")
    defender.expect("press", "end_combat")

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert applied == []
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_blocking_side_aggravated_strike_is_applied_as_aggravated(monkeypatch):
    def fake_strike(state, context):
        if context.get("player") != "P2":
            return []
        return [
            hooks.HookOption(
                choice=Choice("fake_aggravated", "Fake aggravated strike"),
                apply=lambda s: StrikeDamage(1, aggravated=True),
            )
        ]

    hooks.register(COMBAT_STRIKE_OPTION_HOOK, fake_strike)
    applied = _spy_apply_damage(monkeypatch)
    game = _combat_game()
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "fake_aggravated")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert applied == [("V1", 0, 1)]


def test_slam_committed_strike_inherits_base_damage_properties(monkeypatch):
    monkeypatch.setattr(slam, "hand_strike_damage", _aggravated_base)
    game = _anarch_game(
        ("POT",), LibraryCard(krcg_id=slam.KRCG_ID, name="Slam", card_type="combat")
    )
    game.state.combat_range = LONG_RANGE
    round_state: dict = {}
    ctx = {"player": "P1", "vampire": "V1", "opponent": "B1", "round_state": round_state}

    [maneuver] = slam._provide_superior_maneuver(game.state, ctx)
    maneuver.apply(game.state)
    committed = round_state[COMMITTED_STRIKE_KEY]["V1"]

    assert committed.apply(game.state) == StrikeDamage(3, aggravated=True)


def test_only_any_damage_prevention_applies_to_an_aggravated_strike():
    """Soak and Opikun prevent non-aggravated damage only; Rolling with the
    Punches [for] prevents any damage."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=5, blood=3, disciplines=("for",))
    p2.ready_vampire("OP", capacity=5, blood=3)
    p2.hand.append(LibraryCard(krcg_id=soak.KRCG_ID, name="Soak", card_type="combat"))
    p2.hand.append(
        LibraryCard(
            krcg_id=rolling_with_the_punches.KRCG_ID,
            name="Rolling with the Punches",
            card_type="combat",
        )
    )
    game = builder.build()
    game.vampire("OP").card = replace(game.vampire("OP").card, krcg_id=opikun.KRCG_ID)
    ctx = {
        "player": "P2",
        "vampire": "B1",
        "damage": {"normal": 0, "aggravated": 2},
        "round_state": {},
        "combat_state": {},
    }

    assert soak._provide_soak(game.state, ctx) == []
    assert opikun._provide_opikun(game.state, ctx) == []
    assert rolling_with_the_punches._provide_prevent(game.state, ctx) != []

    normal_ctx = {**ctx, "damage": {"normal": 2, "aggravated": 0}}  # control: same setup
    assert soak._provide_soak(game.state, normal_ctx) != []
    assert opikun._provide_opikun(game.state, normal_ctx) != []
