"""The "recruit ally" minion action (OQ-12, `docs/OPEN_QUESTIONS.md`): the
first real entry point a player's agent can reach to bring an Ally library
card into play, built on top of OQ-7's `AllyInPlay`/`recruit_ally`
(`engine/state.py`, `engine/allies.py`) -- which existed but had nothing
offering it as a legal choice in a real game.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `"recruit_ally_play"` provider (standing
in for 47th Street Royals' own future card module, which remains
`card-implementer`'s job once this capability exists) -- mirrors
`tests/rules/test_allies.py`'s own disclaimer for OQ-7.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_RECRUIT_ALLY, perform_minion_action
from vtesbot.engine.allies import RecruitAllySpec
from vtesbot.engine.decision import Choice
from vtesbot.engine.observation import Observation
from vtesbot.engine.phases.minion import RECRUIT_ALLY_PLAY_HOOK, minion_phase
from vtesbot.engine.pool import lose_pool

FAKE_ALLY_KRCG_ID = 555
FAKE_ALLY_COST = 2


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_ally_provider(state, context):
    """Stand-in for a real Ally card module's own `"recruit_ally_play"`
    provider: one option, offered only while its own card is in hand."""
    player = context["player"]
    if not any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        card = play_from_hand_pending(s, player, FAKE_ALLY_KRCG_ID)
        return RecruitAllySpec(
            card=card,
            life=2,
            strength=1,
            bleed=0,
            pay_cost=lambda s2: lose_pool(s2, player, FAKE_ALLY_COST),
        )

    return [
        hooks.HookOption(
            choice=Choice("recruit_fake_ally", "Recruit Fake Ally"),
            apply=_apply,
        )
    ]


def _fake_ally_card() -> LibraryCard:
    return LibraryCard(krcg_id=FAKE_ALLY_KRCG_ID, name="Fake Ally", card_type="ally")


def test_recruit_ally_is_not_offered_without_a_registered_provider():
    """Zero-regression check (OQ-12): with no `"recruit_ally_play"` provider
    registered at all, `action_choice` degrades to exactly the pre-OQ-12
    bleed/hunt pair."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    seen_choices = {}

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation: Observation, decision):
            if decision.kind == "action_choice":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen_choices["values"] == ["bleed", "hunt"]
    actor.assert_exhausted()


def test_recruit_ally_is_not_offered_when_the_provider_has_no_matching_hand_card():
    """The provider is registered, but `player`'s hand has no matching card
    yet -- still "only when needed", no extra choice appears."""
    hooks.register(RECRUIT_ALLY_PLAY_HOOK, _fake_ally_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    seen_choices = {}

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation: Observation, decision):
            if decision.kind == "action_choice":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen_choices["values"] == ["bleed", "hunt"]
    actor.assert_exhausted()


def test_recruit_ally_is_offered_and_succeeds_entering_play_locked():
    """End-to-end success path: the provider's option is offered alongside
    bleed/hunt, chosen, the card leaves hand immediately (announce time) and
    never reaches the ash heap, the cost is paid only now (on success), and
    the ally enters play ready-but-locked under its controller (Rulebook SS4
    "recruited ally cannot act this turn")."""
    hooks.register(RECRUIT_ALLY_PLAY_HOOK, _fake_ally_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_ally_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    seen_choices = {}

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation: Observation, decision):
            if decision.kind == "action_choice":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "recruit_fake_ally")
    # P2 has no ready vampire: "no vacuous decision" -- no "block_attempt" is
    # ever raised (mirrors `tests/rules/test_allies.py`'s own pattern).
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen_choices["values"] == ["bleed", "hunt", "recruit_fake_ally"]
    assert game.pool_of("P1") == 30 - FAKE_ALLY_COST  # cost paid only on success
    assert not any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in game.state.players["P1"].hand)
    assert not any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in game.state.players["P1"].ash_heap)
    allies = list(game.state.players["P1"].allies.values())
    assert len(allies) == 1
    ally = allies[0]
    assert ally.krcg_id == FAKE_ALLY_KRCG_ID
    assert ally.controller == "P1"
    assert ally.life == 2
    assert ally.strength == 1
    assert ally.bleed == 0
    assert ally.zone == "ready"
    assert ally.locked is True  # "recruited ally cannot act this turn"
    actor.assert_exhausted()


def test_recruit_ally_blocked_burns_the_card_pays_no_cost_and_creates_no_ally():
    """Rulebook SS4 "Resolve the Action": "If the action is blocked, then any
    card played to perform the action is burned ... the cost ... is not paid
    if the action is blocked." The already-set-aside card (removed from hand
    at announce time) goes to the ash heap; no `AllyInPlay` is ever created.

    Recruit ally's own +1 stealth baseline (`RECRUIT_ALLY_STEALTH`) exceeds
    the defender's default 0 intercept, so (exactly like
    `test_action_discriminator.py`'s hunt case) a bare block attempt with no
    intercept bonus would merely fail, not block -- a fake `"intercept_
    modifier"` provider stands in for a reaction card giving +1 intercept,
    so the attempt actually succeeds and this test can observe the blocked
    outcome."""

    def intercept_bump(state, context):
        del state
        if context.get("action") != ACTION_RECRUIT_ALLY:
            return []
        return [hooks.HookOption(choice=Choice("bump", "+1 intercept"), apply=lambda s: 1)]

    hooks.register(RECRUIT_ALLY_PLAY_HOOK, _fake_ally_provider)
    hooks.register("intercept_modifier", intercept_bump)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_ally_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "recruit_fake_ally")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "bump")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 30  # cost not paid: the action never succeeded
    assert not any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in game.state.players["P1"].hand)
    assert any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in game.state.players["P1"].ash_heap)
    assert game.state.players["P1"].allies == {}
    # The blocking vampire locked and entered combat, per the general block
    # consequences (Rulebook SS4) -- confirms this is a real block, not a
    # degenerate no-op.
    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").locked is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_recruit_ally_undirected_blockable_by_the_single_2p_opponent():
    """Rulebook SS4 Recruit Ally: "Default target: None. Undirected action."
    2P structural collapse (CLAUDE.md SS3): the sole opponent is both prey
    and predator, so it is simply offered the block attempt -- already
    exercised by the two tests above; this test only pins down the +1
    stealth baseline (`RECRUIT_ALLY_STEALTH`) via `perform_minion_action`
    directly, the same style as `tests/rules/test_action_discriminator.py`."""
    seen = {}

    def recorder(state, context):
        seen["stealth"] = context["stealth"]
        return []

    hooks.register("intercept_modifier", recorder)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    vampire = game.vampire("V1")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", vampire, 1, resolve, action=ACTION_RECRUIT_ALLY)

    assert seen["stealth"] == 1  # RECRUIT_ALLY_STEALTH


def test_recruit_ally_play_hook_context_carries_the_acting_vampires_identity():
    """OQ-13 (`docs/OPEN_QUESTIONS.md`, resolved): `_choose_and_perform_action`
    threads the acting vampire's own identity (`vampire=vampire.instance_id`)
    into the `"recruit_ally_play"` hook context, so a provider can gate on
    *which* ready-unlocked vampire is actually attempting the recruit
    (Rulebook SS2 "Card Types" > "Requirements for Playing Cards": a minion
    card's requirement binds to the specific acting minion, e.g. 47th Street
    Royals' clan requirement -- not merely to "the Methuselah controls one
    somewhere").

    Two simultaneously ready-unlocked vampires stand in for "different
    clans": a stub provider offers its option only when `context["vampire"]`
    matches the specific `instance_id` of the one meeting the (stand-in)
    requirement. Acting with the *other* ready-unlocked vampire first must
    not see the option at all -- the exact mis-resolution OQ-13 flagged
    (silently offering the recruit whenever the player chose to act with an
    unrelated vampire this impulse, merely because some other vampire of
    theirs happens to qualify) -- while acting with the matching vampire
    does see it.
    """
    target_instance_id = "V1"

    def _gated_provider(state, context):
        del state
        if context.get("vampire") != target_instance_id:
            return []
        return [
            hooks.HookOption(
                choice=Choice("recruit_gated_ally", "Recruit Gated Ally"),
                apply=lambda s: pytest.fail("not expected to be chosen in this test"),
            )
        ]

    hooks.register(RECRUIT_ALLY_PLAY_HOOK, _gated_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1).ready_vampire(
        "V2", capacity=3, blood=1
    )
    builder.player("P2", pool=30)  # no ready vampire: no block_attempt ever raised
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation: Observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    # Act with the non-matching vampire first: the option must not appear.
    actor.expect("minion_phase_choice", "act_with:V2")
    actor.expect("action_choice", "bleed")
    # Then act with the matching vampire: the option must now appear.
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen[0] == ["bleed", "hunt"]
    assert seen[1] == ["bleed", "hunt", "recruit_gated_ally"]
    actor.assert_exhausted()


def test_perform_minion_action_on_blocked_runs_only_when_blocked():
    """Generic `engine/action.py::perform_minion_action` behaviour (not
    recruit-ally specific): `on_blocked` fires exactly when the action is
    blocked, `resolve` exactly when it is not -- never both."""
    calls = []

    def resolve(pending):
        del pending
        calls.append("resolve")

    def on_blocked(pending):
        del pending
        calls.append("on_blocked")

    # Unblocked: no ready vampire on the defending side to block with at all.
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), 0, resolve, on_blocked=on_blocked
    )
    assert calls == ["resolve"]

    # Blocked: defender has a ready vampire and blocks (0 stealth, 0 intercept
    # by default -- a block attempt always succeeds with no modifiers).
    calls.clear()
    builder2 = ScenarioBuilder(seed=1)
    builder2.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder2.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game2 = builder2.build()
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game2.state.agents["P1"] = actor
    game2.state.agents["P2"] = defender
    perform_minion_action(
        game2.state, "P1", "P2", game2.vampire("V1"), 0, resolve, on_blocked=on_blocked
    )
    assert calls == ["on_blocked"]
    actor.assert_exhausted()
    defender.assert_exhausted()
