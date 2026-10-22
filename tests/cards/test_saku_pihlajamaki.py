"""Saku Pihlajamäki (krcg id 201658, `src/vtesbot/cards/saku_pihlajamaki.py`).

Card text: "Anarch Baron of Helsinki: Saku gets 1 optional maneuver each
combat." No rulings on file.

Two components, one assertion group each: the "Anarch Baron of Helsinki"
title clause (already generically handled by `engine/politics.py::
TITLE_VOTES`, not this module -- proven end to end through the real
`political_action`, exactly like `tests/cards/test_valeriya_zinovieva.py`'s
own title-vote scenario, to confirm this specific printed card's
`title="Baron"` really does contribute 2 votes while ready), and "1 optional
maneuver each combat" (this module's own effect, via `MANEUVER_HOOK`):
offered once per combat, usable, not offered again later in the same combat
once used, persisting as "already used" across every round of one combat
while resetting cleanly for a fresh, separate combat.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.saku_pihlajamaki import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.combat import run_combat
from vtesbot.engine.politics import political_action

NAME = "Saku Pihlajamäki"


def _make_saku(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Saku Pihlajamäki's real
    printed identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_valeriya_zinovieva.py::_make_valeriya`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=8,
        group=6,
        clan="Brujah",
        title="Baron",
        disciplines=("for", "pro", "CEL", "POT", "PRE"),
    )


def test_registered_as_implemented_against_the_maneuver_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.MANEUVER in reg.hooks


# --- "Anarch Baron of Helsinki" -- the title itself, generically handled ---


def test_a_ready_saku_contributes_2_votes_as_a_baron_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Baron"] == 2`. Proven
    here, end to end through the real `political_action`, exactly like
    `test_valeriya_zinovieva.py`'s own equivalent scenario."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Saku1", capacity=8, blood=1)
    _make_saku(p1, "Saku1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Saku1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Saku1"))

    assert result is True  # 1 (political action card) + 2 (Baron title) for vs 0 against
    actor.assert_exhausted()


# --- "Saku gets 1 optional maneuver each combat" -- this module's own effect ---


def _combat_game(*, blocking_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Saku1", capacity=8, blood=5)
    _make_saku(p1, "Saku1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=blocking_blood)
    return builder.build()


def test_saku_is_offered_and_can_use_her_once_per_combat_maneuver():
    """The maneuver is offered to Saku's controller on her first Determine
    Range turn (acting combatant goes first), and choosing it flips the
    round to long range -- observable via `GameState.combat_range` captured
    at the exact moment a hand strike resolves (same `combat_strength_
    modifier`-probe technique `tests/rules/test_combat_maneuver.py` uses)."""
    captured: list = []

    def capture(state, context):
        if context.get("player") == "P1":
            captured.append(state.combat_range)
        return 0

    hooks.register("combat_strength_modifier", capture)
    try:
        game = _combat_game()

        actor = ScriptedAgent("P1")
        actor.expect("maneuver_choice", "saku_pihlajamaki_maneuver")
        actor.expect("strike_choice", "hand_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        run_combat(game.state, "P1", game.vampire("Saku1"), "P2", game.vampire("B1"))

        assert captured == ["long"]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("combat_strength_modifier", capture)


def test_saku_is_not_offered_the_maneuver_again_later_in_the_same_combat_after_using_it():
    """Once Saku's single, once-per-combat grant is used in round 1, no
    `maneuver_choice` decision is ever raised for her again in round 2 of the
    *same* combat (the `ScriptedAgent` script below has no second
    `maneuver_choice` entry at all; an unexpected decision would raise)."""
    game = _combat_game()

    actor = ScriptedAgent("P1")
    # Round 1: use the once-per-combat grant.
    actor.expect("maneuver_choice", "saku_pihlajamaki_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline, closes the window
    # Round 2: no maneuver_choice decision at all -- the grant is already used.
    # B1 (0 blood) is wounded in round 1 and sent to torpor by round 2's
    # strike, ending combat at once -- no round-2 press decision for either
    # side (same shape as `tests/rules/test_combat_maneuver.py`'s own
    # "per-combat, not per-round" scenario).
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # round 1
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("Saku1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_saku_maneuver_grant_persists_across_rounds_but_resets_for_a_fresh_combat():
    """Per-combat, not per-round, scoping (`engine/combat.py` module
    docstring's "Per-combat, not per-round, scoping" paragraph): the grant
    stays used for every round of one combat (round 2 below has no
    `maneuver_choice` offered), but a brand new `run_combat` call -- a fresh,
    separate combat, with its own fresh `combat_state` dict -- offers it
    again from scratch. B1 is given enough blood (3) to mend fully between
    rounds, so the first combat runs two full rounds with normal press
    decisions rather than ending early in torpor."""
    # First combat: use the grant in round 1; confirm round 2 has nothing.
    game = _combat_game(blocking_blood=3)
    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "saku_pihlajamaki_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline, closes the window
    actor.expect("strike_choice", "hand_strike")  # round 2: no maneuver offered
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "1")
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender
    run_combat(game.state, "P1", game.vampire("Saku1"), "P2", game.vampire("B1"))
    actor.assert_exhausted()
    defender.assert_exhausted()

    # Second, separate combat (fresh `run_combat` call => fresh combat_state,
    # fresh game/vampires): the grant is offered again from scratch.
    game2 = _combat_game()
    actor2 = ScriptedAgent("P1")
    actor2.expect("maneuver_choice", "saku_pihlajamaki_maneuver")
    actor2.expect("strike_choice", "hand_strike")
    actor2.expect("press", "end_combat")
    defender2 = ScriptedAgent("P2")
    defender2.expect("strike_choice", "no_strike")
    defender2.expect("press", "end_combat")
    game2.state.agents["P1"] = actor2
    game2.state.agents["P2"] = defender2
    run_combat(game2.state, "P1", game2.vampire("Saku1"), "P2", game2.vampire("B1"))
    actor2.assert_exhausted()
    defender2.assert_exhausted()


def test_saku_maneuver_is_not_offered_for_a_different_vampire():
    """Gated on this exact printed card (`krcg_id == KRCG_ID`), not on clan,
    title or any other generic attribute -- a different, non-Saku vampire
    controlled by the same player gets no maneuver option offered."""
    from vtesbot.engine.combat import MANEUVER_HOOK

    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Other", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player="P1",
        vampire="Other",
        opponent="B1",
        combat_state={},
        round_state={},
    )

    assert options == []
