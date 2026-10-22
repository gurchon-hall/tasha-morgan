"""Slam (krcg id 101798, `src/vtesbot/cards/slam.py`).

Card text: "[pot] Strike: hand strike at +2 damage.\n[POT] As above, with 1
optional maneuver, only usable to get to close range." Rulings: "Additional
damage inherits all of the properties of the base damage. [TOM 19960225]";
"[POT]The optional maneuver cannot be used if the strike cannot be used (eg.
{Hidden Lurker}). [LSJ 20021028]".

One assertion per clause/qualifier: the `[pot]` basic clause's own
discipline/hand/blood-cost gates; the `[POT]` superior clause's own
discipline/hand/blood-cost/"only at long range"/"cannot use a second strike
card to maneuver again" (ENG-019, now resolved)
gates; the committed-strike behaviour end to end through `run_combat` (no
independent strike choice is ever raised for the combatant who maneuvered
with Slam); the "Hidden Lurker" ruling's current vacuous satisfaction (no
engine mechanism makes a strike "unusable" today); and that this card's own
new `commit_strike_for_round` usage does not regress Pursuit's own plain,
non-strike-bundled `[cel]` maneuver clause (RUL-008) -- a combatant may still
use a plain maneuver after committing a strike-bundled one the same round.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.pursuit import KRCG_ID as PURSUIT_ID
from vtesbot.cards.slam import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.combat import (
    CLOSE_RANGE,
    COMBAT_STRIKE_OPTION_HOOK,
    LONG_RANGE,
    MANEUVER_HOOK,
    run_combat,
)

NAME = "Slam"


def _slam_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _pursuit_card() -> LibraryCard:
    return LibraryCard(krcg_id=PURSUIT_ID, name="Pursuit", card_type="combat")


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.COMBAT_STRIKE_OPTION in reg.hooks
    assert registry.Hook.MANEUVER in reg.hooks


# --- "[pot] Strike: hand strike at +2 damage." -------------------------------


def test_basic_strike_not_offered_without_pot():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=())
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
    )
    assert options == []


def test_basic_strike_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("pot",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
    )
    assert options == []


def test_basic_strike_not_offered_without_enough_blood():
    """Printed 1-blood cost: must have at least 1 blood to play at all."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("pot",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
    )
    assert options == []


def test_basic_strike_offered_with_basic_pot_and_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            combat_state={},
        )
    }
    assert values == {"slam:basic"}


def test_basic_strike_also_offered_with_superior_pot():
    """Superior Potence presence satisfies the basic-level discipline check
    too (Rulebook §3 "may opt to use either effect")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            combat_state={},
        )
    }
    assert values == {"slam:basic"}


# --- "[POT] As above, with 1 optional maneuver, only usable to get to close
# range." --------------------------------------------------------------------


def _maneuver_options(game, *, round_state: dict | None = None):
    return hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
        round_state=round_state if round_state is not None else {},
    )


def test_superior_maneuver_not_offered_with_only_basic_pot():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pot",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    assert _maneuver_options(game) == []


def test_superior_maneuver_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("POT",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    assert _maneuver_options(game) == []


def test_superior_maneuver_not_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    assert _maneuver_options(game) == []


def test_superior_maneuver_not_offered_at_close_range():
    """ "Only usable to get to close range": not offered while already at
    close range (the default) -- only while currently at long range."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = CLOSE_RANGE

    assert _maneuver_options(game) == []


def test_superior_maneuver_not_offered_with_no_combat_range_set():
    """No combat currently in progress (`combat_range is None`, `run_combat`'s
    own reset value) is likewise not "at long range"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    assert game.state.combat_range is None

    assert _maneuver_options(game) == []


def test_superior_maneuver_offered_at_long_range_with_superior_pot_and_enough_blood():
    """Also doubles as proof that "[POT]The optional maneuver cannot be used
    if the strike cannot be used (eg. {Hidden Lurker})" [LSJ 20021028] is
    currently vacuously satisfied: Hidden Lurker is not implemented in this
    project, and no mechanism anywhere makes a combatant's strike "unusable"
    today (module docstring) -- so, absent any such restriction, this clause
    is offered unconditionally once its own printed gates are met."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    values = {o.choice.value for o in _maneuver_options(game)}
    assert values == {"slam:superior_maneuver"}


def test_superior_maneuver_not_offered_twice_in_the_same_round():
    """ENG-019's own "cannot use a second strike card or weapon to maneuver
    again in the same round" cap: gated via `strike_committed_this_round`,
    consulted fresh on every offer, shared across the round via `round_state`
    (the same object `run_combat` threads through both Determine Range and
    the strike step within one round)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=5, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    p1.hand.append(_slam_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    round_state: dict = {}
    first = _maneuver_options(game, round_state=round_state)
    assert {o.choice.value for o in first} == {"slam:superior_maneuver"}
    first[0].apply(game.state)  # plays the first copy, commits the strike.

    second = _maneuver_options(game, round_state=round_state)
    assert second == []  # the second copy's [POT] clause is not offered again this round.
    assert len(game.state.players["P1"].hand) == 1  # second copy stayed unused in hand


# --- Committed-strike behaviour, end to end through `run_combat` -----------


def test_maneuvering_with_slam_commits_the_initial_strike_with_no_separate_choice():
    """V1 (Potence only) has nothing to maneuver with at close range (the
    round's default); B1 (Celerity, holding Pursuit) maneuvers first to long
    range, which then makes Slam's own superior clause available to V1.
    Choosing it both flips the range back to close and commits V1's initial
    strike for the round -- no `strike_choice` decision is ever raised for
    V1 at all; B1 still gets an ordinary, independent one."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=2, disciplines=("POT",)
    )
    p1.hand.append(_slam_card())
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=0, disciplines=("cel",)
    )
    p2.hand.append(_pursuit_card())
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "slam:superior_maneuver")
    # No "strike_choice" entry for P1 at all: the committed strike resolves
    # directly, with no Decision raised for V1's initial strike this round.
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("maneuver_choice", "pursuit:maneuver")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").wounded is True  # 1 (hand strike) + 2 (Slam bonus) = 3 damage
    assert game.zone_of("B1") == "ready"  # a single hit only wounds, never straight to torpor
    assert game.vampire("V1").blood == 1  # 2 - 1 (printed blood cost)
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Does not regress Pursuit's own plain, non-strike-bundled maneuver -----


def test_committing_a_slam_strike_does_not_block_a_later_plain_pursuit_maneuver():
    """`strike_committed_this_round` only gates a *second strike-bundled*
    maneuver source (ENG-019's own documented scope) -- a combatant who has
    already committed Slam's strike-bundled maneuver this round may still
    use an entirely separate, plain, non-strike-bundled maneuver afterward
    (Pursuit's own basic `[cel]` clause, RUL-008), since the Rulebook's own
    restriction only bars a second strike *card or weapon*, not maneuvering
    as such."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("POT", "cel")
    )
    p1.hand.append(_slam_card())
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = LONG_RANGE

    round_state: dict = {}
    # Both are offered at once here (V1 qualifies for both from the start);
    # pick out Slam's own option specifically to commit it.
    before = _maneuver_options(game, round_state=round_state)
    before_values = {o.choice.value for o in before}
    assert before_values == {"slam:superior_maneuver", "pursuit:maneuver"}
    slam_option = next(o for o in before if o.choice.value == "slam:superior_maneuver")
    slam_option.apply(game.state)  # commits the strike; Slam's own copy is now used.

    after = _maneuver_options(game, round_state=round_state)
    values = {o.choice.value for o in after}
    assert values == {"pursuit:maneuver"}  # Pursuit's plain maneuver is unaffected
    assert "slam:superior_maneuver" not in values  # no more Slam copies in hand either way
