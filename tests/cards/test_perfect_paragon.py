"""Perfect Paragon (`src/vtesbot/cards/perfect_paragon.py`, krcg id 101387).

One assertion per clause/ruling (CLAUDE.md "One test per clause"): the
`[pre]` basic clause's own discipline/hand/blood-cost/caller-only gates and
its `POLLING_STEP_HOOK` end-to-end wiring through a real `political_action`
call; the "automatically passing" ruling's current vacuous satisfaction (no
engine gate of that kind exists); the `[PRE]` superior clause's own
discipline/hand/blood-cost gates and its `INTERCEPT_DECREASE_HOOK` end-to-end
wiring (both the "younger vampire" qualifying case and the non-qualifying
case) through a real `attempt_block` call; the currently-unreachable
"Allies" half of the superior clause; and the hand-membership self-gating
that prevents one physical card from being spent twice across
`INTERCEPT_DECREASE_HOOK`'s two offer points (OQ-31).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.perfect_paragon import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import INTERCEPT_DECREASE_HOOK, attempt_block
from vtesbot.engine.allies import recruit_ally
from vtesbot.engine.politics import POLLING_STEP_HOOK, political_action

NAME = "Perfect Paragon"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action modifier")


def test_card_is_registered_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.blocked_reason is None


# -- "[pre] ... This vampire gets +3 votes." (basic clause) -----------------


def _polling_step_options(game, *, player: str, caller: str, caller_vampire_id: str):
    pending = {"extra_sources": [], "forced_abstain": set()}
    return hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player=player,
        caller=caller,
        caller_vampire_id=caller_vampire_id,
        phase="before_cast",
        pending=pending,
    )


def test_basic_not_offered_without_pre_discipline():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _polling_step_options(game, player="P1", caller="P1", caller_vampire_id="V1")

    assert options == []


def test_basic_offered_with_basic_pre_discipline():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _polling_step_options(game, player="P1", caller="P1", caller_vampire_id="V1")

    assert {o.choice.value for o in options} == {"perfect_paragon:basic"}


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("pre",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = _polling_step_options(game, player="P1", caller="P1", caller_vampire_id="V1")

    assert options == []


def test_basic_not_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("pre",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _polling_step_options(game, player="P1", caller="P1", caller_vampire_id="V1")

    assert options == []


def test_basic_not_offered_to_the_other_methuselahs_own_polling_step_window():
    """Only the referendum's own calling vampire may play this card for the
    bonus (module docstring, Rulebook glossary "Action Modifier") -- never
    the other Methuselah's own offer of the same two-sided impulse window,
    even if that Methuselah also holds a copy and controls a `[pre]`
    vampire."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("pre",))
    p2 = builder.player("P2", pool=30).ready_vampire(
        "V2", capacity=3, blood=1, disciplines=("pre",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _polling_step_options(game, player="P2", caller="P1", caller_vampire_id="V1")

    assert options == []


def test_basic_not_offered_through_a_different_ready_vampire_of_the_caller():
    """ "This vampire" is specifically the referendum's own calling vampire
    (`caller_vampire_id`), never some *other* ready vampire the caller
    happens to control, even one with `[pre]` and the card in hand -- the
    provider never enumerates "which of my vampires plays this"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)  # the actual caller: no pre discipline.
    p1.ready_vampire("V2", capacity=3, blood=1, disciplines=("pre",))
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _polling_step_options(game, player="P1", caller="P1", caller_vampire_id="V1")

    assert options == []


def test_basic_clause_end_to_end_through_a_real_political_action():
    """Playing the card during the polling step pays its 1-blood cost,
    moves it to the ash heap, and adds a +3-vote source the caller then
    casts for -- combined with the caller's own automatic political-action-
    card vote (1), the referendum passes 4 to 0. This end-to-end pass is
    also the demonstration that the "[pre] cannot be used during an
    automatically passing referendum" ruling [PIB 20150105] [LSJ 19980107]
    has no engine gate to violate today: nothing here special-cases an
    "automatically passing" state (module docstring -- `resolve_referendum`
    has no such code path), so the clause is offered and resolves
    unconditionally."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "perfect_paragon:basic")
    actor.expect("polling_step_cast", "for:perfect_paragon:V1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True  # 1 (political action card) + 3 (Perfect Paragon) for vs 0 against.
    assert game.blood_of("V1") == 0  # 1-blood cost paid
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


# -- "[PRE] Allies and younger vampires get -1 intercept." (superior clause) -


def _proactive_options(game, *, actor: str, defender: str, acting_vampire_id: str):
    pending: dict = {}
    return hooks.offer(
        INTERCEPT_DECREASE_HOOK,
        game.state,
        player=actor,
        actor=actor,
        defender=defender,
        acting_vampire=acting_vampire_id,
        action=None,
        directed=None,
        base_stealth=0,
        pending=pending,
    )


def test_superior_not_offered_with_only_basic_pre_discipline():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _proactive_options(game, actor="P1", defender="P2", acting_vampire_id="V1")

    assert options == []


def test_superior_offered_with_superior_pre_discipline():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _proactive_options(game, actor="P1", defender="P2", acting_vampire_id="V1")

    assert {o.choice.value for o in options} == {"perfect_paragon:superior"}


def test_superior_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("PRE",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = _proactive_options(game, actor="P1", defender="P2", acting_vampire_id="V1")

    assert options == []


def test_superior_not_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _proactive_options(game, actor="P1", defender="P2", acting_vampire_id="V1")

    assert options == []


def test_superior_clause_end_to_end_decreases_a_younger_blockers_intercept():
    """Proactively activated, before any candidate is chosen (OQ-30): the
    acting vampire's own capacity (3) makes the younger candidate (capacity
    1) qualify for -1 intercept, flipping a would-have-succeeded block
    (intercept 0 >= stealth 0) into a failure."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1").expect(INTERCEPT_DECREASE_HOOK, "perfect_paragon:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    assert game.blood_of("V1") == 0  # 1-blood cost paid
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clause_does_not_affect_a_blocker_who_is_not_younger():
    """Zero-regression counterpart: a blocker whose own capacity (5) is not
    strictly lower than the acting vampire's (3) does not qualify -- its
    block still succeeds at the default intercept 0 >= stealth 0."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1").expect(INTERCEPT_DECREASE_HOOK, "perfect_paragon:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    assert blocker.instance_id == "B1"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clause_declined_proactively_can_still_be_played_reactively_once_only():
    """OQ-31 (resolved -- Reading B): the proactive, top-of-retry-loop offer
    is not the only chance to play this card -- the actor may decline it and
    still use the exact same physical card reactively, once a specific
    blocking candidate is already fixed (`_duel_stealth_intercept`'s own
    "stealth_modifier" offer). Once played there, the card is gone from
    hand -- the critical "not spent twice across both offer points"
    constraint this card relies on the hand-membership gate (not a separate
    `used` flag) to enforce, per the module docstring."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=1, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(INTERCEPT_DECREASE_HOOK, "pass")  # declines the proactive offer
    actor.expect("stealth_modifier", "perfect_paragon:superior")  # plays it reactively instead
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    # Would otherwise have succeeded at once (intercept 0 >= stealth 0); the
    # reactive decrease flips it to a failure, then the defender declines a
    # further attempt to end the test cleanly.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    assert game.blood_of("V1") == 0  # cost paid exactly once
    assert game.state.players["P1"].hand == []  # exactly one copy consumed, not two
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clauses_allies_half_is_currently_unreachable():
    """ "Allies ... get -1 intercept": `engine/action.py::attempt_block`'s
    own candidate pool (`state.ready_unlocked_vampires`) is built only from
    `PlayerState.vampires`, never `PlayerState.allies` (`engine/allies.py`'s
    own "ally block participation ... deliberately out of scope" module
    docstring) -- so even with a ready, unlocked ally in play and nothing
    else to block with, the defender is offered no block-attempt decision
    at all. There is no reachable scenario in this engine today where this
    card's `qualifies` predicate is ever asked to judge an Ally -- the
    "not reachable today, but correctly modeled either way" status the
    module docstring documents."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)  # no vampire at all: an ally is the only thing in play.
    game = builder.build()
    recruit_ally(game.state, "P2", krcg_id=1, name="Some Ally", life=2).locked = False

    actor = ScriptedAgent("P1").expect(INTERCEPT_DECREASE_HOOK, "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # never consulted: no decision is raised.

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None  # no block-attempt decision at all: the ally was never a candidate.
    actor.assert_exhausted()
