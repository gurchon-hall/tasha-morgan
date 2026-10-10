"""The "action_card_play" hook/call site (OQ-17, `docs/OPEN_QUESTIONS.md`,
resolved by this pass): the engine entry point for a library card of printed
`types == ["Action"]` (Rulebook SS2 Card Types) that is itself the acting
vampire's entire minion action for the turn, rather than a decoration of an
already-chosen default Bleed/Hunt.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake `"action_card_play"` providers (standing in
for Enchant Kindred's own future card module, which remains
`card-implementer`'s job once this hook exists) -- mirrors
`tests/rules/test_recruit_ally_action.py`'s own disclaimer for OQ-12, and
generalizes its coverage beyond Allies.
"""

import contextlib

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import bonding as bonding_module
from vtesbot.cards._shared import play_from_hand, play_from_hand_pending
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD, ACTION_BLEED
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.observation import Observation
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec, minion_phase
from vtesbot.engine.pool import lose_pool

FAKE_ACTION_CARD_KRCG_ID = 777
FAKE_ACTION_CARD_STEALTH = 0
FAKE_ACTION_CARD_BLEED_AMOUNT = 2


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_action_card() -> LibraryCard:
    return LibraryCard(
        krcg_id=FAKE_ACTION_CARD_KRCG_ID, name="Fake Action Card", card_type="action"
    )


def _fake_action_card_provider(state, context):
    """Stand-in for a real Action card module's own `"action_card_play"`
    provider: one option, offered only while its own card is in hand;
    consumes its card immediately (announce time), mirroring a plain
    one-shot Action card's own placement, which does not depend on the
    later block outcome (OQ-17, `ActionCardSpec`'s own docstring). Its
    `resolve` is mechanically a directed bleed for a fixed amount, standing
    in for Enchant Kindred's own basic clause."""
    player = context["player"]
    other = next(p for p in state.players if p != player)
    if not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        play_from_hand(s, player, FAKE_ACTION_CARD_KRCG_ID)

        def resolve(pending):
            del pending
            lose_pool(s, other, FAKE_ACTION_CARD_BLEED_AMOUNT)

        return ActionCardSpec(
            base_stealth=FAKE_ACTION_CARD_STEALTH,
            directed=True,
            resolve=resolve,
        )

    return [
        hooks.HookOption(
            choice=Choice("play_fake_action_card", "Play Fake Action Card"),
            apply=_apply,
        )
    ]


def test_action_card_play_is_not_offered_without_a_registered_provider():
    """Zero-regression check (OQ-17): with no `"action_card_play"` provider
    registered at all, `action_choice` degrades to exactly the pre-OQ-17
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


def test_action_card_play_is_not_offered_when_the_provider_has_no_matching_hand_card():
    """The provider is registered, but `player`'s hand has no matching card
    yet -- still "only when needed", no extra choice appears."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
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


def test_action_card_play_is_offered_and_succeeds_resolving_its_own_effect():
    """End-to-end success path: the provider's option is offered alongside
    bleed/hunt, chosen, the card leaves hand immediately (announce time,
    straight to the ash heap -- Rulebook SS4 "Resolve the Action": a plain
    one-shot Action card's own placement does not depend on the later block
    outcome, OQ-17), and once unblocked `resolve` performs the card's own
    effect (here, a directed bleed stand-in)."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
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
    actor.expect("action_choice", "play_fake_action_card")
    # P2 has no ready vampire: "no vacuous decision" -- no "block_attempt" is
    # ever raised (mirrors `tests/rules/test_recruit_ally_action.py`'s own
    # pattern).
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen_choices["values"] == ["bleed", "hunt", "play_fake_action_card"]
    assert game.pool_of("P2") == 30 - FAKE_ACTION_CARD_BLEED_AMOUNT
    assert not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].hand)
    assert any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].ash_heap)
    actor.assert_exhausted()


def test_action_card_play_blocked_does_not_resolve_but_still_consumed_the_card():
    """Rulebook SS4 "Resolve the Action": a blocked action's own effect never
    happens. The fake provider here already consumed its card immediately at
    announce time (not via the two-destination dance -- see the generality
    test below for that case), so the card is in the ash heap regardless of
    the block outcome, but `resolve`'s pool-loss effect must not fire."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_action_card")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    # Base stealth is 0 (`FAKE_ACTION_CARD_STEALTH`): the defender's default
    # 0 intercept already meets it, so a bare block attempt with no
    # modifiers succeeds outright (unlike recruit ally's +1 stealth
    # baseline, no intercept bump is needed here).
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # resolve() never ran: no bleed-stand-in effect
    assert not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].hand)
    assert any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].ash_heap)
    # The blocking vampire locked and entered combat, per the general block
    # consequences (Rulebook SS4) -- confirms this is a real block, not a
    # degenerate no-op.
    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").locked is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_action_card_play_threads_the_action_discriminator_and_directed_flag():
    """OQ-9 (`action=`) and OQ-17 (`directed=`): `_perform_action_card` must
    forward both the fixed `ACTION_ACTION_CARD` discriminator and the
    provider's own `directed` flag into the block-attempt phase's hook
    context, exactly like `_perform_bleed`/`_perform_hunt`/`_perform_
    recruit_ally` already do for their own `action=`/`directed=` values."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    seen = {}

    def recorder(state, context):
        del state
        seen["action"] = context.get("action")
        seen["directed"] = context.get("directed")
        return []

    # Base stealth is 0 and the defender's default intercept is 0: the
    # attempt currently *succeeds* (intercept >= stealth), so it is the
    # *actor*'s "stealth_modifier" hook that gets offered first (`engine/
    # action.py::_duel_stealth_intercept`'s "only when needed" ping-pong),
    # not "intercept_modifier".
    hooks.register("stealth_modifier", recorder)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_action_card")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert seen["action"] == ACTION_ACTION_CARD
    assert seen["directed"] is True  # the fake provider's own ActionCardSpec
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_action_card_play_hook_context_carries_the_acting_vampires_identity():
    """OQ-13's own binding (`docs/OPEN_QUESTIONS.md`, resolved -- re-proven
    here for the generalized hook): `_choose_and_perform_action` threads the
    acting vampire's own identity (`vampire=vampire.instance_id`) into the
    `"action_card_play"` hook context too, mirroring `"recruit_ally_play"`'s
    own OQ-13 wiring, so a provider can gate on *which* ready-unlocked
    vampire is actually attempting to play the card."""
    target_instance_id = "V1"

    def _gated_provider(state, context):
        del state
        if context.get("vampire") != target_instance_id:
            return []
        return [
            hooks.HookOption(
                choice=Choice("play_gated_action_card", "Play Gated Action Card"),
                apply=lambda s: pytest.fail("not expected to be chosen in this test"),
            )
        ]

    hooks.register(ACTION_CARD_PLAY_HOOK, _gated_provider)
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
    assert seen[1] == ["bleed", "hunt", "play_gated_action_card"]
    actor.assert_exhausted()


def test_action_card_play_supports_the_two_destination_dance_generically():
    """OQ-17's own generality requirement: the hook's contract must not
    hard-code the immediate-consumption assumption -- a future Action card
    whose own placement depends on the later block outcome (mirroring
    Recruit Ally's Ally card) must be able to use `vtesbot.cards._shared.
    play_from_hand_pending` plus `ActionCardSpec.on_blocked`, exactly like
    `_perform_recruit_ally` already does for `RecruitAllySpec`.

    `resolve`/`on_blocked` below land the card in two genuinely *different*
    destinations (unlike an earlier draft of this test, which mistakenly
    sent both branches to the ash heap and so could not actually
    distinguish them -- rules-auditor finding): `resolve` (unblocked)
    places the card into a stand-in "in play" marker, mirroring
    `_perform_recruit_ally`'s own unblocked branch, which calls
    `recruit_ally` to put the Ally card's *effect* into play rather than
    discarding the card; `on_blocked` burns it to the ash heap, mirroring
    `_perform_recruit_ally`'s own blocked branch (Rulebook SS4 "Resolve the
    Action": "any card played to perform the action is burned"). `calls`
    also records which closure actually ran, so this test independently
    confirms `resolve` fires exactly when unblocked and `on_blocked` exactly
    when blocked -- never both -- mirroring `tests/rules/
    test_recruit_ally_action.py`'s own generic `perform_minion_action`
    check."""
    pending_krcg_id = 888
    calls: list[str] = []
    in_play: dict[str, LibraryCard] = {}

    def _pending_provider(state, context):
        player = context["player"]
        if not any(c.krcg_id == pending_krcg_id for c in state.players[player].hand):
            return []

        def _apply(s):
            card = play_from_hand_pending(s, player, pending_krcg_id)

            def resolve(pending):
                del pending
                calls.append("resolve")
                in_play[player] = card  # distinct destination: NOT the ash heap.

            def on_blocked(pending):
                del pending
                calls.append("on_blocked")
                s.players[player].ash_heap.append(card)  # distinct destination: burned.

            return ActionCardSpec(
                base_stealth=0,
                directed=False,
                resolve=resolve,
                on_blocked=on_blocked,
            )

        return [
            hooks.HookOption(
                choice=Choice("play_pending_action_card", "Play Pending Action Card"),
                apply=_apply,
            )
        ]

    hooks.register(ACTION_CARD_PLAY_HOOK, _pending_provider)

    # Unblocked: no ready vampire on the defending side to block with at all.
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(
        LibraryCard(krcg_id=pending_krcg_id, name="Fake Pending Action Card", card_type="action")
    )
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_pending_action_card")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert calls == ["resolve"]
    assert not any(c.krcg_id == pending_krcg_id for c in game.state.players["P1"].hand)
    # Resolved (unblocked): landed in the "in play" marker, NOT the ash heap.
    assert in_play.get("P1") is not None and in_play["P1"].krcg_id == pending_krcg_id
    assert not any(c.krcg_id == pending_krcg_id for c in game.state.players["P1"].ash_heap)
    actor.assert_exhausted()
    in_play.clear()

    # Blocked: defender has a ready vampire and blocks (0 stealth, 0
    # intercept by default -- a block attempt always succeeds with no
    # modifiers).
    calls.clear()
    builder2 = ScenarioBuilder(seed=1)
    pb2 = builder2.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb2.hand.append(
        LibraryCard(krcg_id=pending_krcg_id, name="Fake Pending Action Card", card_type="action")
    )
    builder2.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game2 = builder2.build()
    actor2 = ScriptedAgent("P1")
    actor2.expect("minion_phase_choice", "act_with:V1")
    actor2.expect("action_choice", "play_pending_action_card")
    actor2.expect("strike_choice", "no_strike")
    actor2.expect("press", "end_combat")
    defender2 = ScriptedAgent("P2")
    defender2.expect("block_attempt", "block_with:B1")
    defender2.expect("strike_choice", "no_strike")
    defender2.expect("press", "end_combat")
    game2.state.agents["P1"] = actor2
    game2.state.agents["P2"] = defender2

    minion_phase(game2.state, "P1")

    assert calls == ["on_blocked"]
    assert not any(c.krcg_id == pending_krcg_id for c in game2.state.players["P1"].hand)
    # Blocked: burned to the ash heap, NOT the "in play" marker `resolve` uses.
    assert any(c.krcg_id == pending_krcg_id for c in game2.state.players["P1"].ash_heap)
    assert "P1" not in in_play
    actor2.assert_exhausted()
    defender2.assert_exhausted()


def _run_bonding_integration_scenario(declared_action: str | None) -> list[str]:
    """Shared body for the test below: build a scenario where the acting
    vampire has superior Dominate and Bonding itself in hand, play a fake
    Action card whose `ActionCardSpec.action` is either left unset
    (`declared_action is None`, defaulting to `ACTION_ACTION_CARD`) or set to
    `ACTION_BLEED`, and record which choices Bonding's own real `"stealth_
    modifier"` provider (`cards/bonding.py::_provide_bonding_superior`) offers
    during the resulting block attempt's stealth window.

    Registers Bonding's own real superior-clause provider function directly
    (`contextlib.suppress(ValueError)` guards the defensive `unregister` in
    case it is not currently registered -- e.g. if an earlier test in this
    file's own `hooks.clear()` teardown already wiped it, or if this test
    file is the first one `vtesbot.cards.bonding` is ever imported in, this
    test must not depend on *either* possibility to pass reliably) rather
    than relying on its own module-import side effect surviving whatever
    hook state an earlier test in this session left behind -- this keeps the
    test deterministic regardless of execution order, while still exercising
    Bonding's real, unmodified card logic (not a test-local reimplementation
    of its gate)."""
    with contextlib.suppress(ValueError):
        hooks.unregister(
            bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior
        )
    hooks.register(bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior)
    # This helper is called twice per test (once per `declared_action`
    # value) -- drop any fake provider a previous call within this same
    # test already registered, so the two runs never offer a duplicate
    # "play_fake_action_card" choice.
    hooks.clear(ACTION_CARD_PLAY_HOOK)

    def _provider(state, context):
        player = context["player"]
        if not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in state.players[player].hand):
            return []

        def _apply(s):
            play_from_hand(s, player, FAKE_ACTION_CARD_KRCG_ID)

            def resolve(pending):
                del pending  # not exercised by this test: the option is declined below.

            kwargs: dict = {"base_stealth": 0, "directed": True, "resolve": resolve}
            if declared_action is not None:
                kwargs["action"] = declared_action
            return ActionCardSpec(**kwargs)

        return [
            hooks.HookOption(
                choice=Choice("play_fake_action_card", "Play Fake Action Card"),
                apply=_apply,
            )
        ]

    hooks.register(ACTION_CARD_PLAY_HOOK, _provider)

    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    pb.hand.append(_fake_action_card())
    pb.hand.append(
        LibraryCard(krcg_id=bonding_module.KRCG_ID, name="Bonding", card_type="modifier")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    seen_choices: dict[str, list[str]] = {"values": []}

    class ActorAgent:
        """Not a `ScriptedAgent`: whether a `"stealth_modifier"` decision is
        raised at all here depends on `declared_action` (Bonding's own gate
        either offers something or offers nothing -- CLAUDE.md "only when
        needed", `engine/hooks.py::offer`), so a fixed answer script would
        have to vary per branch; this agent instead answers generically by
        `decision.kind`, and records the "stealth_modifier" choices exactly
        if/when that decision actually appears."""

        player_id = "P1"

        def decide(self, observation: Observation, decision: Decision) -> Choice:
            del observation
            by_kind = {
                "minion_phase_choice": "act_with:V1",
                "action_choice": "play_fake_action_card",
                "stealth_modifier": "decline",
                "strike_choice": "no_strike",
                "press": "end_combat",
            }
            if decision.kind == "stealth_modifier":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            expected_value = by_kind.get(decision.kind)
            if expected_value is None:
                raise AssertionError(f"unexpected decision kind {decision.kind!r}")
            matching = [c for c in decision.choices if c.value == expected_value]
            assert matching, (
                f"{expected_value!r} not among offered choices "
                f"{[c.value for c in decision.choices]} for kind {decision.kind!r}"
            )
            return matching[0]

    actor = ActorAgent()
    defender = ScriptedAgent("P2")
    # Base stealth 0 meets the defender's default 0 intercept: the block
    # attempt already succeeds, so it is the actor's "stealth_modifier"
    # window that opens next (Bonding's own superior-clause hook).
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    defender.assert_exhausted()
    return seen_choices["values"]


def test_action_card_play_can_declare_itself_a_real_bleed_so_bonding_still_fires():
    """Rules-auditor finding (OQ-17 follow-up): `ActionCardSpec.action` lets
    a provider declare the real mechanical action identity its own clause's
    card text matches (CLAUDE.md SS2 card-text precedence over rulings --
    settled directly by the text itself, no judgment call needed, when a
    clause's own printed text literally says "Bleed", e.g. Enchant Kindred's
    basic clause "[pre] Ⓓ Bleed with +1 bleed").

    Left unset, `ActionCardSpec.action` defaults to `ACTION_ACTION_CARD`,
    correctly keeping Bonding's superior clause's own ruling-sourced gate
    (`cards/bonding.py`: "[DOM] Cannot be used to increase the stealth of a
    non-bleed action", `context.get("action") != ACTION_BLEED: return []`)
    from firing for a clause that genuinely is not a bleed. Declared as
    `ACTION_BLEED`, the exact same real Bonding provider must now offer its
    superior clause, indistinguishable from an ordinary `_perform_bleed`
    call -- proving the rules-auditor's finding is fixed, not merely
    asserted."""
    without_declared_action = _run_bonding_integration_scenario(declared_action=None)
    assert "bonding:superior" not in without_declared_action

    with_declared_action = _run_bonding_integration_scenario(declared_action=ACTION_BLEED)
    assert "bonding:superior" in with_declared_action
