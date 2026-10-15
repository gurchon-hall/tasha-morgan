"""Organized Resistance (krcg id 102230,
`src/vtesbot/cards/organized_resistance.py`).

Card text: "Requires a baron. Usable by a locked baron.\nAn Anarch you
control gets +1 intercept. Also usable to unlock a locked Anarch you
control; that Anarch attempts to block with +1 intercept, even if
intercept is not yet needed."

One assertion per clause/qualifier/ruling: the "Requires a baron"
card-level gate for each clause (no Baron in play -> nothing offered);
the "Usable by a locked baron" relaxation for each clause; clause 1's
"+1 intercept" gated on the *vampire currently attempting the block*
being an Anarch the player controls (Rulebook §4 "Stealth and
Intercept" -- see the module docstring's own citation for why this, not
a generic "controls some Anarch somewhere", is the correct reading);
clause 2's unlock-and-force-block gated on controlling at least one
locked Anarch, unconditional success even against a stealth an ordinary
attempt could never beat, and real combat following through
`perform_minion_action`; the shared "a minion cannot play the same
reaction card more than once during a single action" restriction applied
across *both* clauses for one Baron (module docstring's documented
reading of §8), while a second, distinct eligible Baron is unaffected;
and ruling [ANK 20181122-2] ("can be used by a vampire who is already
attempting to block"), modeled as "offered again after an earlier
ordinary block attempt this same action already failed" -- the only
shape of that ruling this engine's sequential, one-attempt-at-a-time
block model can construct.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.organized_resistance import KRCG_ID, USED_BY_KEY
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_INJECTION_HOOK,
    INTERCEPT_MODIFIER_HOOK,
    attempt_block,
    perform_minion_action,
)

NAME = "Organized Resistance"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `sect`
    (mirrors `test_protection_racket.py::_set_sect`: `ready_vampire` has no
    `sect=` parameter and `CryptCard` is frozen, so a fresh instance is
    swapped in, preserving every other field)."""
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


def _offer_intercept(game, *, defender, actor, blocking_vampire=None, pending=None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        blocking_vampire=blocking_vampire,
        pending=pending,
    )


def _offer_block_candidate(
    game, *, defender, actor, acting_vampire=None, pending=None, base_stealth=0
):
    return hooks.offer(
        BLOCK_CANDIDATE_INJECTION_HOOK,
        game.state,
        player=defender,
        actor=actor,
        defender=defender,
        acting_vampire=acting_vampire,
        action=None,
        directed=None,
        base_stealth=base_stealth,
        pending=pending,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Requires a baron" -- clause 1 (intercept) -----------------------------


def test_clause1_not_offered_without_a_baron_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D2", capacity=3, blood=0)
    _set_sect(p2, "D2", Sect.ANARCH)  # D2 is the current blocker -- but no Baron in play.
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1", blocking_vampire="D2")
    assert options == []


def test_clause1_locked_baron_may_still_play_it_usable_by_a_locked_baron():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron", locked=True)
        .ready_vampire("D2", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1", blocking_vampire="D2")
    assert {o.choice.value for o in options} == {"organized_resistance:intercept:D1"}

    delta = options[0].apply(game.state)
    assert delta == 1
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_clause1_not_offered_when_the_blocking_vampire_is_not_an_anarch():
    """ "An Anarch you control gets +1 intercept" -- per Rulebook §4
    "Stealth and Intercept" (module docstring citation), intercept is
    always a property of the vampire *currently attempting the block*, so
    this bonus has no effect unless that vampire is itself an Anarch the
    player controls, even though the player controls a Baron and the card
    is in hand."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)  # the current blocker -- not an Anarch.
    )
    p2.hand.append(_card())
    game = builder.build()

    assert game.vampire("D2").card.sect is None
    options = _offer_intercept(game, defender="P2", actor="P1", blocking_vampire="D2")
    assert options == []


def test_clause1_not_offered_without_a_blocking_vampire_in_context():
    """Degrades to "no bonus", never a guess, when the hook is asked
    outside the real block-attempt flow (no `blocking_vampire` supplied)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1", blocking_vampire=None)
    assert options == []


def test_clause1_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1", blocking_vampire="D2")
    assert options == []


def test_clause1_not_offered_a_second_time_by_the_same_baron_this_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D2", pending=pending
    )
    assert {o.choice.value for o in first} == {"organized_resistance:intercept:D1"}
    first[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    second = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D2", pending=pending
    )
    assert second == []  # D1 already played this card once this action.


def test_clause1_a_second_eligible_baron_can_still_use_their_own_copy():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D4", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D2", pending=pending
    )
    next(o for o in first if o.choice.value == "organized_resistance:intercept:D1").apply(
        game.state
    )

    second = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D2", pending=pending
    )
    assert {o.choice.value for o in second} == {"organized_resistance:intercept:D4"}


# --- "Requires a baron" -- clause 2 (unlock + force block) -----------------


def test_clause2_not_offered_without_a_baron_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, locked=True)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_not_offered_without_controlling_a_locked_anarch():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0)  # unlocked -- no "locked" Anarch to unlock.
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_not_offered_when_no_anarch_at_all_is_controlled():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)  # locked, but not Anarch.
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_locked_baron_may_still_play_it_and_unlocks_the_chosen_anarch():
    """ "Usable by a locked baron." for clause 2 too, and "unlock a locked
    Anarch you control" -- `apply()` flips the chosen Anarch's own `.locked`
    to `False` and returns it, the `BLOCK_CANDIDATE_INJECTION_HOOK` contract.
    """
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron", locked=True)
        .ready_vampire("D2", capacity=3, blood=0, locked=True)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", base_stealth=5
    )
    assert {o.choice.value for o in options} == {"organized_resistance:unlock:D2:by:D1"}

    blocker = options[0].apply(game.state)
    assert blocker.instance_id == "D2"
    assert game.vampire("D2").locked is False
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_clause2_unconditional_block_through_attempt_block_even_against_high_stealth():
    """End-to-end through the real call site: `base_stealth=5` would fail
    every ordinary stealth/intercept attempt (intercept is hardcoded 0
    this milestone, with no other provider registered); choosing the
    injected option unlocks D2 and `attempt_block` returns it directly as a
    successful blocker, never consulting `_duel_stealth_intercept`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "organized_resistance:unlock:D2:by:D1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "D2"
    assert game.vampire("D2").locked is False
    defender.assert_exhausted()


def test_clause2_leads_to_real_combat_through_perform_minion_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()
    acting = game.vampire("A1")

    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "organized_resistance:unlock:D2:by:D1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, 5, resolve)

    assert resolve_calls == []  # blocked branch: resolve() never ran
    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D2").locked is True  # re-locked for combat, like any successful blocker.


# --- "A minion cannot play the same reaction card more than once during a
# single action" -- shared across both clauses for one Baron -------------


def test_same_baron_cannot_use_clause1_then_clause2_in_the_same_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)  # for clause 2's own unlock target.
        .ready_vampire("D3", capacity=3, blood=0)  # the current blocker, for clause 1.
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    _set_sect(p2, "D3", Sect.ANARCH)
    p2.hand.append(_card())
    p2.hand.append(_card())  # a second physical copy -- still the same Baron, though.
    game = builder.build()

    pending: dict = {}
    clause1 = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D3", pending=pending
    )
    assert {o.choice.value for o in clause1} == {"organized_resistance:intercept:D1"}
    clause1[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    clause2 = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", pending=pending, base_stealth=5
    )
    assert clause2 == []  # D1 already played this physical card this action.


def test_same_baron_cannot_use_clause2_then_clause1_in_the_same_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)
        .ready_vampire("D3", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    _set_sect(p2, "D3", Sect.ANARCH)
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    clause2 = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", pending=pending, base_stealth=5
    )
    assert {o.choice.value for o in clause2} == {"organized_resistance:unlock:D2:by:D1"}
    clause2[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    clause1 = _offer_intercept(
        game, defender="P2", actor="P1", blocking_vampire="D3", pending=pending
    )
    assert clause1 == []  # D1 already played this physical card this action.


# --- "Can be used by a vampire who is already attempting to block." -------
# [ANK 20181122-2]


def test_can_be_used_after_an_earlier_ordinary_block_attempt_already_failed_this_action():
    """Models the ruling the only way this engine's sequential,
    one-attempt-at-a-time block model can construct: D3 (ordinary,
    non-Anarch, ready, unlocked) is offered first and its attempt fails
    (`base_stealth=5`, intercept hardcoded 0 -- Organized Resistance's own
    clause 1 does not apply either, since D3 is not an Anarch) -- D3 stays
    unlocked and the window re-offers; this time the defender picks
    Organized Resistance's injected D2 instead, which still succeeds
    unconditionally."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Baron")
        .ready_vampire("D2", capacity=3, blood=0, locked=True)
        .ready_vampire("D3", capacity=3, blood=0)
    )
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D3")
    defender.expect("block_attempt", "organized_resistance:unlock:D2:by:D1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "D2"
    assert game.vampire("D2").locked is False
    assert game.vampire("D3").locked is False  # the earlier, failed attempt: never locked.
    defender.assert_exhausted()
