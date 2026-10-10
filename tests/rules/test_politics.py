"""Political action announce/block/polling/tally (`engine/politics.py`).
OQ-6 (`docs/OPEN_QUESTIONS.md`) is resolved: these scenarios cover both the
generic "announce -> block attempt -> (blocked: combat) | (unblocked:
referendum)" path and the referendum's polling step / vote tally itself
(Rulebook SS4 "The Referendum", see `engine/politics.py`'s own docstring for
the verbatim sources).
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.politics import (
    POLLING_STEP_HOOK,
    REFERENDUM_TALLIED_HOOK,
    political_action,
    resolve_referendum,
)


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_a_blocked_political_action_goes_to_combat_and_never_calls_a_referendum():
    """Political action's baseline stealth is +1 (Rulebook SS4 default
    action list), which -- like hunt's own +1 baseline (see
    `tests/rules/test_minion_hunt.py`) -- always evades a bare block attempt
    with no intercept-granting card implemented; a fake intercept-modifier
    provider stands in for one here purely to exercise the "blocked ->
    combat" path end to end. A blocked political action's card is burned
    before any referendum is called (OQ-5), so `political_action` returns
    `None`, never resolving a tally."""

    def fake_intercept(state, context):
        if context.get("player") != "P2":
            return []
        return [
            hooks.HookOption(choice=Choice("use_fake_intercept", "+2 intercept"), apply=lambda s: 2)
        ]

    hooks.register("intercept_modifier", fake_intercept)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_fake_intercept")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is None
    assert game.vampire("V1").locked is True  # announcing locks the acting vampire
    assert game.vampire("B1").locked is True  # a successful block locks the blocker
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_an_uncontested_referendum_passes_one_to_nothing():
    """No candidate blocker, no titled vampires, no Edge holder: the only
    vote source is the acting Methuselah's own political-action-card vote
    (Rulebook SS4 Politics > Gaining Votes > Political Action Cards), which
    the acting Methuselah chooses to cast "for", 1-0, which passes (more for
    than against)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_acting_methuselah_may_decline_their_own_political_action_card_vote():
    """The political-action-card vote is an ordinary `VoteSource`, not a
    hardcoded automatic "for": "there is no obligation to cast votes or
    ballots" (Rulebook SS4 "The Referendum" step 2, quoted in full in
    `engine/politics.py`'s module docstring) applies to it exactly like any
    other source. Declining it leaves 0 votes cast at all, which ties
    (0-0) and fails."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "pass")
    defender = ScriptedAgent("P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_acting_methuselah_may_cast_their_own_political_action_card_vote_against():
    """Same "no special case" point as the decline test above, the other
    direction: the acting Methuselah may cast their own political-action-
    card vote "against" their own referendum ("a Methuselah may cast some of
    their votes and ballots in favour and some against, as they choose" --
    same module-docstring quote), which here is the only vote cast at all,
    0-1, and fails."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "against:political_action_card:P1")
    defender = ScriptedAgent("P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_declined_block_then_a_lone_opposing_title_ties_and_fails():
    """Defender declines to block (keeping their vampire ready/unlocked so
    it can vote instead); the acting Methuselah casts their own political-
    action-card vote "for", the defender then uses their titled vampire's 1
    vote "against": 1 for vs 1 against ties, and "[t]ied referendums fail"
    (Rulebook SS4 Politics)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_ready_opposing_prince_outvotes_the_lone_actor_and_the_referendum_fails():
    """A ready prince is worth 2 votes (Rulebook SS4 Politics > Gaining
    Votes > Titled Vampires); 1 for (actor's own political-action-card vote,
    cast "for") vs 2 against (defender's prince) fails outright, no tie
    involved. The prince is left locked (`locked=True`) on purpose: "[w]hether
    or not a minion is locked or unlocked does not have any impact on their
    ability to vote" (same source) -- being locked only removes it as a
    block *candidate* (`attempt_block` finds no ready-unlocked vampire to
    offer, so no block decision is even raised), not as a vote source."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=1, title="Prince", locked=True
    )
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_edge_holder_burns_it_for_an_extra_vote_and_the_edge_is_returned_uncontrolled():
    """ "The Methuselah who has the Edge can burn it (return it, uncontrolled,
    to the central area) to gain 1 vote" (Rulebook SS4 Politics > Gaining
    Votes > The Edge): the acting Methuselah casts their own political-
    action-card vote "for", the defender holds the Edge with no titled
    vampire and burns it against the referendum, tying (1-1, and failing)
    it; `edge_holder` is cleared as a result."""
    builder = ScenarioBuilder(seed=1).edge_holder("P2")
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:edge:P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    assert game.state.edge_holder is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_polling_step_hook_provider_adds_a_vote_source_and_it_is_cast():
    """Generic dispatch proof (no real card): a fake `POLLING_STEP_HOOK`
    provider -- standing in for e.g. Perfect Paragon's "[pre] ... This
    vampire gets +3 votes" -- adds a new vote source for the acting
    Methuselah during the pre-cast window (Rulebook SS4 "The Referendum"
    step 2: cards usable "before votes and ballots are cast"); the new
    source is then offered, and cast, during the casting step itself."""

    def fake_vote_grant(state, context):
        if context.get("player") != "P1" or context.get("phase") != "before_cast":
            return []
        already_granted = any(
            extra["source_id"] == "fake:paragon" for extra in context["pending"]["extra_sources"]
        )
        if already_granted:
            return []

        def apply(s):
            context["pending"]["extra_sources"].append(
                {"source_id": "fake:paragon", "player": "P1", "votes": 5, "label": "Fake Paragon"}
            )

        return [hooks.HookOption(choice=Choice("grant_fake_votes", "Grant 5 votes"), apply=apply)]

    hooks.register(POLLING_STEP_HOOK, fake_vote_grant)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "grant_fake_votes")
    actor.expect("polling_step_cast", "for:fake:paragon")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    # 1 (political action card, cast for) + 5 (fake Paragon) for vs 0 against.
    assert result is True
    actor.assert_exhausted()


def test_the_pre_cast_and_post_tally_hook_contexts_both_carry_the_calling_vampires_identity():
    """`resolve_referendum` threads the calling vampire's identity (not just
    `caller_player`'s id) into both the pre-cast `POLLING_STEP_HOOK` window
    and the post-tally `REFERENDUM_TALLIED_HOOK` dispatch -- needed by any
    card whose own trigger names a *specific* titled vampire's referendum
    (e.g. Queen Anne's "a referendum called by Anne", Marcos Belegrad's "a
    referendum called by Marcos") rather than any referendum its controller
    happens to call (`engine/politics.py` module docstring, OQ-6).

    The two contexts carry this identity differently, by design (`rules-
    auditor` finding, round 3): the pre-cast window may raise a real
    `Decision` (agent-visible), so it only ever carries the plain-string
    `caller_vampire_id` (`instance_id`), never the live `VampireInPlay`; the
    post-tally dispatch (`hooks.run_effects`, never a `Decision`, only
    trusted provider code) still carries the live object."""
    seen_pre_cast: list[object] = []
    seen_tallied: list[object] = []

    def capture_pre_cast(state, context):
        seen_pre_cast.append(context.get("caller_vampire_id"))
        return []

    def capture_tallied(state, context):
        seen_tallied.append(context.get("caller_vampire"))

    hooks.register(POLLING_STEP_HOOK, capture_pre_cast)
    hooks.register(REFERENDUM_TALLIED_HOOK, capture_tallied)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    acting_vampire = game.vampire("V1")
    result = political_action(game.state, "P1", acting_vampire)

    assert result is True
    # `capture_pre_cast` is offered once per side of the two-sided impulse
    # window (CLAUDE.md rule 4), so it may be called more than once; every
    # call must see the same acting vampire's identity, for both players.
    assert seen_pre_cast
    assert all(vampire_id == acting_vampire.instance_id for vampire_id in seen_pre_cast)
    assert seen_tallied == [acting_vampire]
    actor.assert_exhausted()


def test_the_pre_cast_decision_context_never_leaks_the_live_vampire_object():
    """`rules-auditor` finding (round 3): a real `POLLING_STEP_HOOK` provider
    offering an actual `HookOption` forces `hooks.resolve_impulse_window` to
    raise a real `Decision`, whose `context` is handed straight to
    `agent.decide(observation, decision)` -- i.e. to agent-visible code
    (CLAUDE.md "Information hiding": agents receive an `Observation`, never
    the raw, mutable `GameState` object graph). This proves the `Decision`
    the agent actually receives carries no `VampireInPlay` (or any other
    live game-state object) anywhere in its context -- only plain data."""
    from vtesbot.engine.state import VampireInPlay

    seen_decisions: list[object] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    def fake_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("noop", "No-op option"), apply=lambda s: None)]

    hooks.register(POLLING_STEP_HOOK, fake_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = RecordingAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "noop")
    actor.expect(POLLING_STEP_HOOK, "pass")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True
    assert seen_decisions  # at least the POLLING_STEP_HOOK decision was raised
    for decision in seen_decisions:
        for value in decision.context.values():
            assert not isinstance(value, VampireInPlay), (
                f"Decision.context leaked a live VampireInPlay: {value!r}"
            )
    actor.assert_exhausted()


def test_the_other_methuselah_may_burn_a_political_action_card_from_hand_for_a_vote():
    """Rulebook SS4 Politics > Gaining Votes > Political Action Cards,
    clause 2 (verbatim, re-fetched live this round): "Other political action
    cards used for votes are simply burned without regard to the text on
    the cards." Found missing entirely by `rules-auditor` (round 3): P2
    (the non-calling Methuselah) holds a "Political Action"-type card in
    hand and burns it for 1 vote "against" the referendum; P1's own
    political-action-card vote (clause 1) is cast "for". 1-1 ties, and
    "[t]ied referendums fail." The burned card actually leaves P2's hand for
    the ash heap."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).hand_cards(["Fake PAC"], card_type="Political Action")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:political_action_card_hand:P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False
    p2_state = game.state.players["P2"]
    assert p2_state.hand == []
    assert [c.name for c in p2_state.ash_heap] == ["Fake PAC"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_calling_methuselah_is_never_offered_the_burn_from_hand_political_action_card_source():
    """The burn-from-hand source (clause 2) is gated purely on "this player
    did not call the referendum" -- not a shared 1-vote cap the caller could
    fill via either clause (`rules-auditor`/this round's own module
    docstring discussion). Proven here even though P1 (the caller) *also*
    holds a "Political Action"-type card in hand: `political_action_card_
    hand:P1` must never appear among P1's offered choices."""

    class AssertingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "polling_step_cast":
                offered = {c.value for c in decision.choices}
                assert not any("political_action_card_hand:P1" in value for value in offered), (
                    f"caller was offered a clause-2 source: {offered}"
                )
            return super().decide(observation, decision)

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1).hand_cards(
        ["Fake PAC"], card_type="Political Action"
    )
    builder.player("P2", pool=30)
    game = builder.build()
    actor = AssertingAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True
    # P1's own political-action-card hand card is untouched: clause 2 never
    # fires for the caller, so nothing is burned from it.
    assert [c.name for c in game.state.players["P1"].hand] == ["Fake PAC"]
    actor.assert_exhausted()


def test_a_forced_abstain_source_is_excluded_from_casting_end_to_end():
    """`pending["forced_abstain"]` (the Queen-Anne-style forced-abstain
    mechanism, module docstring) had zero test coverage before this round
    (`rules-auditor` finding, round 3). A fake `POLLING_STEP_HOOK` provider
    stands in for a card like Queen Anne, adding the defender's titled
    vampire's own vote-source id to `pending["forced_abstain"]`; that source
    must never be offered as a castable option (the defender gets no
    `polling_step_cast` decision at all) nor appear in the final tally."""

    def fake_forced_abstain(state, context):
        if context.get("player") != "P1" or context.get("phase") != "before_cast":
            return []
        if "title:B1" in context["pending"]["forced_abstain"]:
            return []

        def apply(s):
            context["pending"]["forced_abstain"].add("title:B1")

        return [
            hooks.HookOption(choice=Choice("force_abstain", "Force B1 to abstain"), apply=apply)
        ]

    hooks.register(POLLING_STEP_HOOK, fake_forced_abstain)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "force_abstain")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")  # B1's vote source is forced to abstain: no decision at all.
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    _votes_for, _votes_against, casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("V1")
    )

    assert all(source_id != "title:B1" for (_player, source_id, _votes, _direction) in casts)
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_referendum_tallied_hook_fires_with_no_providers_registered():
    """`REFERENDUM_TALLIED_HOOK` (OQ-6, Marcos Belegrad's future trigger
    moment) has no provider registered in this pass: `hooks.run_effects`
    must still be a safe no-op (the project's "no providers => no behaviour
    change" invariant), proven here with the hooks registry left untouched
    by this test."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True
    actor.assert_exhausted()
