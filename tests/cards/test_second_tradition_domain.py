"""Second Tradition: Domain (krcg id 101706,
`src/vtesbot/cards/second_tradition_domain.py`).

Card text: "Requires a prince or justicar.\n[REACTION] +2 intercept.\n
[REACTION] Only usable by a locked prince or justicar. This vampire burns
1 blood to unlock and attempt to block with +2 intercept, even if
intercept is not yet needed."

One assertion per clause/qualifier/ruling: the "Requires a prince or
justicar" gate for each clause (no qualifying title in play -> nothing
offered, for either title); clause 1's flat "+2 intercept", untargeted
(no "blocking_vampire" identity check, mirroring `protection_racket.py`'s
own precedent); clause 2's "Only usable by a locked prince or justicar",
its 1-blood cost (cannot play if unaffordable [ANK 20210226]), its
unconditional success even against a stealth an ordinary attempt could
never beat, and real combat following through `perform_minion_action`;
the shared "a minion cannot play the same reaction card more than once
during a single action" restriction applied across *both* clauses for one
vampire (a second, distinct eligible vampire is unaffected); and ruling
[ANK 20181122-2] ("can be used by a vampire who is already attempting to
block"), modeled as "offered again after an earlier ordinary block
attempt this same action already failed" -- the only shape of that ruling
this engine's sequential, one-attempt-at-a-time block model can
construct.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.second_tradition_domain import KRCG_ID, USED_BY_KEY
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_INJECTION_HOOK,
    INTERCEPT_MODIFIER_HOOK,
    attempt_block,
    perform_minion_action,
)

NAME = "Second Tradition: Domain"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _offer_intercept(game, *, defender, actor, pending=None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        defender=defender,
        acting_vampire=None,
        action=None,
        directed=None,
        stealth=1,
        intercept=0,
        blocking_vampire=None,
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


# --- "Requires a prince or justicar" -- clause 1 (intercept) ---------------


def test_clause1_not_offered_without_a_qualifying_title_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)  # no title.
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert options == []


def test_clause1_offered_for_a_ready_unlocked_prince():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, title="Prince")
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert {o.choice.value for o in options} == {"second_tradition_domain:intercept:D1"}

    delta = options[0].apply(game.state)
    assert delta == 2
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_clause1_offered_for_a_ready_unlocked_justicar():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, title="Justicar")
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert {o.choice.value for o in options} == {"second_tradition_domain:intercept:D1"}


def test_clause1_not_offered_for_a_locked_prince():
    """Clause 1 keeps the standard Reaction-card eligibility rule (ready,
    unlocked) -- only clause 2 relaxes it."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, title="Prince", locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert options == []


def test_clause1_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, title="Prince")
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert options == []


def test_clause1_not_offered_a_second_time_by_the_same_vampire_this_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, title="Prince")
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert {o.choice.value for o in first} == {"second_tradition_domain:intercept:D1"}
    first[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    second = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert second == []  # D1 already played this card once this action.


def test_clause1_a_second_eligible_vampire_can_still_use_their_own_copy():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, title="Prince")
        .ready_vampire("D2", capacity=3, blood=0, title="Justicar")
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    next(o for o in first if o.choice.value == "second_tradition_domain:intercept:D1").apply(
        game.state
    )

    second = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert {o.choice.value for o in second} == {"second_tradition_domain:intercept:D2"}


# --- "Only usable by a locked prince or justicar" -- clause 2 --------------


def test_clause2_not_offered_without_a_qualifying_title_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=1, locked=True)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_not_offered_for_an_unlocked_prince():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Prince"
    )  # unlocked -- clause 2 needs locked.
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_not_offered_when_the_vampire_cannot_afford_the_blood_cost():
    """[ANK 20210226]: "The card cannot be played if the minion cannot
    afford to burn the blood." """
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, title="Prince", locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_clause2_locked_prince_may_play_it_pays_blood_and_unlocks():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Prince", locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", base_stealth=5
    )
    assert {o.choice.value for o in options} == {"second_tradition_domain:unlock:D1"}

    blocker = options[0].apply(game.state)
    assert blocker.instance_id == "D1"
    assert game.vampire("D1").locked is False
    assert game.vampire("D1").blood == 0
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_clause2_locked_justicar_also_qualifies():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Justicar", locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_block_candidate(game, defender="P2", actor="P1", acting_vampire="A1")
    assert {o.choice.value for o in options} == {"second_tradition_domain:unlock:D1"}


def test_clause2_unconditional_block_through_attempt_block_even_against_high_stealth():
    """End-to-end through the real call site: `base_stealth=5` would fail
    every ordinary stealth/intercept attempt (intercept is hardcoded 0
    this milestone); choosing the injected option unlocks D1 and
    `attempt_block` returns it directly as a successful blocker, never
    consulting `_duel_stealth_intercept`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Prince", locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "second_tradition_domain:unlock:D1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "D1"
    assert game.vampire("D1").locked is False
    defender.assert_exhausted()


def test_clause2_leads_to_real_combat_through_perform_minion_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Prince", locked=True
    )
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
    defender.expect("block_attempt", "second_tradition_domain:unlock:D1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, 5, resolve)

    assert resolve_calls == []  # blocked branch: resolve() never ran
    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").locked is True  # re-locked for combat, like any successful blocker.


# --- "A minion cannot play the same reaction card more than once during a
# single action" -- shared across both clauses for one vampire -----------


def test_same_vampire_cannot_use_clause1_then_clause2_in_the_same_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=1, title="Prince")
    p2.hand.append(_card())
    p2.hand.append(_card())  # a second physical copy -- still the same vampire, though.
    game = builder.build()

    pending: dict = {}
    clause1 = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert {o.choice.value for o in clause1} == {"second_tradition_domain:intercept:D1"}
    clause1[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    # D1 is still unlocked (clause 1 never locks the playing vampire) -- but
    # clause 2 also requires `locked`, so to isolate the §8 restriction
    # itself (not the separate "locked" gate) lock D1 by hand here.
    game.vampire("D1").locked = True
    clause2 = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", pending=pending, base_stealth=5
    )
    assert clause2 == []  # D1 already played this physical card this action.


def test_same_vampire_cannot_use_clause2_then_clause1_in_the_same_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=1, title="Prince", locked=True
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    clause2 = _offer_block_candidate(
        game, defender="P2", actor="P1", acting_vampire="A1", pending=pending, base_stealth=5
    )
    assert {o.choice.value for o in clause2} == {"second_tradition_domain:unlock:D1"}
    clause2[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]
    assert game.vampire("D1").locked is False  # unlocked by clause 2's own apply.

    clause1 = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert clause1 == []  # D1 already played this physical card this action.


# --- "Can be used by a vampire who is already attempting to block." -------
# [ANK 20181122-2]


def test_can_be_used_after_an_earlier_ordinary_block_attempt_already_failed_this_action():
    """Models the ruling the only way this engine's sequential,
    one-attempt-at-a-time block model can construct: D2 (ordinary, ready,
    unlocked, untitled) is offered first and its attempt fails
    (`base_stealth=5`, intercept hardcoded 0) -- D2 stays unlocked and the
    window re-offers; this time the defender picks Second Tradition:
    Domain's injected D1 instead, which still succeeds unconditionally."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3, blood=1)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=1, title="Prince", locked=True)
        .ready_vampire("D2", capacity=3, blood=0)
    )
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D2")
    defender.expect("block_attempt", "second_tradition_domain:unlock:D1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "D1"
    assert game.vampire("D1").locked is False
    assert game.vampire("D2").locked is False  # the earlier, failed attempt: never locked.
    defender.assert_exhausted()
