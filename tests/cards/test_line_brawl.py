"""Line Brawl (krcg id 102229, `src/vtesbot/cards/line_brawl.py`).

Card text: "Requires an Anarch.\n[cel] Ⓓ Steal 1 pool from another
Methuselah.\n[pot] Ⓓ Enter combat with a minion.\n[pre] Ⓓ Bleed with +1
bleed." Ruling: "When played, a multi-Disciplines card counts as requiring
the Discipline(s) being used. In the hand, library, or ash heap, the card is
considered to require any and/or all Disciplines listed on it." [LSJ
20011204-3] [PIB 20130704].

One assertion per clause/qualifier/ruling: the "Requires an Anarch"
card-level gate (independent of discipline clause); each clause's own
discipline gate (`[cel]`/`[pot]`/`[pre]`) and "card in hand" gate, including
the generic multi-discipline ruling (a vampire with only one of the three
disciplines never sees the other two, a vampire with more than one sees
more than one option); `[cel]`'s pool steal (normal case and the
"target has less pool than the steal amount" edge case); `[pot]`'s
enter-combat clause (no eligible target -> not offered at all; single
eligible target -> applied directly; multiple eligible targets -> a
`Decision`; a block still produces combat via the generic engine path,
`resolve()` never running, and the forced-into-combat target is never
locked by this clause itself); `[pre]`'s bleed (base amount 2, tagged
`action=ACTION_BLEED` so a bleed-gated provider sharing the same window
still fires, mirroring `enchant_kindred.py`'s own basic-clause test).
"""

import contextlib

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import bonding as bonding_module
from vtesbot.cards.line_brawl import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Line Brawl"


def _line_brawl_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Mirrors `test_dust_up.py::_set_sect`: neither `ready_vampire` nor
    `uncontrolled_vampire` has a `sect=` parameter, and `CryptCard` is
    frozen, so a fresh instance is swapped in, preserving every other
    field. Must be called *before* `builder.build()`."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=old.clan,
        title=old.title,
        disciplines=old.disciplines,
        sect=sect,
    )


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- "Requires an Anarch" -- card-level gate, independent of clause --------


def test_anarch_gate_blocks_all_three_clauses_for_a_non_anarch_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pot", "pre")
    )
    _set_sect(p1, "V1", Sect.CAMARILLA)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_anarch_gate_blocks_all_three_clauses_when_sect_is_unset():
    """`CryptCard.sect` defaults to `None`; a card gating on sect must treat
    that as "does not qualify," never guess a default sect."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pot", "pre")
    )
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    assert game.vampire("V1").card.sect is None
    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_anarch_gate_allows_all_three_clauses_for_an_anarch_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pot", "pre")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }

    assert values == {"line_brawl:cel", "line_brawl:pot", "line_brawl:pre"}


# --- Discipline-level gating / multi-discipline ruling ----------------------


def test_cel_not_offered_without_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot", "pre")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "line_brawl:cel" not in values


def test_pot_not_offered_without_pot():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pre")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "line_brawl:pot" not in values


def test_pre_not_offered_without_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "line_brawl:pre" not in values


def test_a_vampire_with_only_one_discipline_sees_only_that_one_clause():
    """Generic multi-discipline ruling [LSJ 20011204-3] [PIB 20130704]: in
    play, a vampire with only one of the three printed disciplines can only
    ever use that one clause, never the others."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert values == {"line_brawl:pre"}


def test_no_clause_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel", "pot", "pre")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


# --- "[cel] Ⓓ Steal 1 pool from another Methuselah." ------------------------


def test_cel_steals_1_pool_from_the_opponent_and_is_consumed_as_a_one_shot():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:cel")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 31
    assert game.pool_of("P2") == 29
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_cel_steals_only_what_the_target_actually_has():
    """ "Steal" moves only what is actually there (`engine.pool.lose_pool`'s
    own floor-at-0 behaviour): an opponent already at 0 pool (less than the
    printed steal amount of 1) loses nothing further and nothing is created
    out of nothing on the stealing side. `lose_pool` always runs
    `check_oust` regardless of the amount actually lost, so this scenario
    also (correctly, and not specially handled by this card) triggers the
    pre-existing oust/victory machinery for a Methuselah already at 0 pool."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:cel")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 0  # nothing further lost, never negative
    assert game.pool_of("P1") == 36  # 30 + the pre-existing oust bonus, not from the steal itself
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    actor.assert_exhausted()


def test_cel_blocked_does_not_resolve_but_the_card_is_still_consumed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:cel")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 30
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- "[pot] Ⓓ Enter combat with a minion." ----------------------------------


def test_pot_not_offered_without_an_eligible_opposing_ready_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30)  # no vampire at all for P1 to force into combat
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "line_brawl:pot" for o in options)


def test_pot_not_offered_when_the_only_opposing_vampire_is_in_torpor():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).torpid_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "line_brawl:pot" for o in options)


def test_pot_single_eligible_target_enters_combat_without_a_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pot")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is True  # V1's hand strike landed in the forced combat
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pot_with_multiple_eligible_targets_raises_a_choice_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0).ready_vampire(
        "B2", capacity=3, blood=0
    )
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "line_brawl_combat_target":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pot")
    actor.expect("line_brawl_combat_target", "line_brawl_combat_target:B1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert seen == [["line_brawl_combat_target:B1", "line_brawl_combat_target:B2"]]
    assert game.vampire("B1").wounded is True
    assert game.vampire("B2").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pot_blocked_enters_combat_with_the_blocker_instead_via_the_generic_path():
    """The target is chosen at `apply()` time (announce), before the
    block-attempt window even opens (rules-auditor finding, 2026-10-11 --
    Rulebook §4 "Announce the Action" + this engine's own `ActionCardSpec`
    contract both require it). If the opponent then blocks with a
    *different* minion than the one announced, the generic block-attempt
    path's own `run_combat` call supersedes it -- `resolve()` (and so the
    announced target) never runs at all; combat happens with the actual
    blocker instead."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0).ready_vampire(
        "B2", capacity=3, blood=0
    )
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pot")
    actor.expect("line_brawl_combat_target", "line_brawl_combat_target:B2")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("B1").locked is True  # blocker locked, per the generic block path
    assert game.vampire("B2").locked is False  # announced target, but blocked by B1 instead
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pot_unblocked_target_is_not_locked_by_entering_combat():
    """Unlike blocking (which locks the blocker, `engine/action.py::
    attempt_block`), forcing a target into combat via this clause does not
    lock it -- Line Brawl's own text never says "locking", unlike the one
    "enter combat" card-text precedent found that does (Brujah Frenzy:
    "... locking him or her.")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pot")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("B1").locked is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pot_never_targets_the_acting_players_own_vampire():
    """The Ⓓ marker (Rulebook §2 glossary "Directed Action") settles that
    the target is controlled by the opponent, never the acting player's own
    side, even though the printed clause names no explicit "controlled by
    your prey or predator" qualifier."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.ready_vampire("V2", capacity=3, blood=0)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30)  # no opposing vampire at all
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "line_brawl:pot" for o in options)


def test_pot_resolve_fizzles_if_the_announced_target_stops_qualifying():
    """RUL-007: the target is chosen at `apply()`
    time (announce), with `resolve()` only ever re-validating -- never
    re-choosing -- that same target, per VTES's general "fizzles" ruling
    (an unblocked action whose target no longer meets its condition at
    resolve time still succeeds but has no effect). Not reachable through
    ordinary play today (nothing in this engine's current scope mutates an
    opposing vampire's zone during a block-attempt window), so exercised
    directly against the hook machinery, bypassing `minion_phase`, to prove
    `resolve()` degrades gracefully instead of crashing or picking a new
    target if that ever changes."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    state = game.state
    state.agents["P1"] = ScriptedAgent("P1")

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "line_brawl:pot"]
    spec = option.apply(state)  # single eligible target (B1): bound directly, no Decision.

    game.vampire("B1").zone = "torpor"  # simulate the target leaving "ready" post-announce.

    spec.resolve({})

    assert game.vampire("B1").wounded is False  # fizzled: no combat happened
    actor_hand = state.players["P1"].hand
    assert actor_hand == []  # the card itself was still consumed at apply() time


# --- "[pre] Ⓓ Bleed with +1 bleed." -----------------------------------------


def test_pre_bleeds_for_2_and_is_consumed_as_a_one_shot_action():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pre")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + 1 printed = 2
    assert game.state.edge_holder == "P1"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_pre_blocked_does_not_resolve_but_the_card_is_still_consumed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "line_brawl:pre")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # blocked: resolve() never ran
    assert game.state.edge_holder is None
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pre_clause_is_tagged_a_real_bleed_so_bonding_still_fires():
    """Because this clause's card text literally says "Bleed",
    `ActionCardSpec.action` must be `ACTION_BLEED`, not the generic
    `ACTION_ACTION_CARD` default -- otherwise an existing bleed-gated
    provider sharing the same window (Bonding's own real superior clause,
    gated on `context.get("action") == ACTION_BLEED`) would be silently and
    wrongly suppressed. Mirrors `test_enchant_kindred.py`'s own proof for
    its basic `[pre]` clause."""
    with contextlib.suppress(ValueError):
        hooks.unregister(
            bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior
        )
    hooks.register(bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior)

    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre", "DOM")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_line_brawl_card())
    p1.hand.append(
        LibraryCard(krcg_id=bonding_module.KRCG_ID, name="Bonding", card_type="modifier")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    seen_choices: dict[str, list[str]] = {"values": []}

    class ActorAgent:
        player_id = "P1"

        def decide(self, observation, decision):
            del observation
            by_kind = {
                "minion_phase_choice": "act_with:V1",
                "action_choice": "line_brawl:pre",
                "stealth_modifier": "decline",
                "strike_choice": "no_strike",
                "press": "end_combat",
            }
            if decision.kind == "stealth_modifier":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            expected_value = by_kind[decision.kind]
            matching = [c for c in decision.choices if c.value == expected_value]
            assert matching, (
                f"{expected_value!r} not among {[c.value for c in decision.choices]} "
                f"for kind {decision.kind!r}"
            )
            return matching[0]

    game.state.agents["P1"] = ActorAgent()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert "bonding:superior" in seen_choices["values"]
    defender.assert_exhausted()
