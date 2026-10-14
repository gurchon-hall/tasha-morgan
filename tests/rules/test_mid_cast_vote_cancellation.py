"""Mid-polling-step retroactive vote cancellation (OQ-37, `docs/
OPEN_QUESTIONS.md`): `engine/politics.py::_cast_votes` now also offers any
`POLLING_STEP_HOOK` option with `context["phase"] == "mid_cast"`, merged
into each player's own per-turn `"polling_step_cast"` `Decision` -- Scalpel
Tongue (krcg id 101686, "Choose a vampire who has cast votes or ballots in
this referendum. The chosen vampire is locked and abstains (this cancels
the chosen vampire's votes and ballots)") needs exactly this.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `POLLING_STEP_HOOK` provider -- Scalpel
Tongue's own card module remains `card-implementer`'s job once this
capability exists.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK, resolve_referendum


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_scalpel_tongue(target_source_id: str, *, burns_blood: bool = False):
    """Stand-in for Scalpel Tongue's own `[CEL][PRE]` superior clause: locks
    the targeted vampire (here, a plain marker list, since no real vampire
    needs to exist for the mechanism test) and returns the canceled
    `VoteSource.source_id`, per the `"mid_cast"` phase's own `apply`
    contract (`engine/politics.py::_cast_votes`'s own docstring)."""
    locked: list[str] = []

    def provider(state, context):
        if context.get("phase") != "mid_cast":
            return []
        if not any(source_id == target_source_id for (_p, source_id, _v, _d) in context["casts"]):
            return []  # not yet cast: Scalpel Tongue's own text requires it has already cast

        def _apply(s):
            locked.append(target_source_id)
            if burns_blood:
                pass  # card-specific cost, irrelevant to the engine mechanism itself
            return target_source_id

        return [
            HookOption(choice=Choice("scalpel_tongue", "Cancel with Scalpel Tongue"), apply=_apply)
        ]

    return provider, locked


def test_mid_cast_option_is_only_offered_once_the_target_has_already_cast():
    seen_at_p2s_first_turn: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if self.player_id == "P2" and not seen_at_p2s_first_turn:
                seen_at_p2s_first_turn.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    provider, _locked = _fake_scalpel_tongue("title:B1")
    hooks.register(POLLING_STEP_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = RecordingAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    # Offered once title:B1 has cast (symmetric, this fake provider does not
    # gate by player -- see its own docstring): declined here, letting the
    # window close via two further silent (nothing-to-offer) turns.
    actor.expect("polling_step_cast", "pass")
    defender = RecordingAgent("P2")
    # No "scalpel_tongue" choice yet on P2's very first turn: their own
    # title:B1 source has not cast anything yet.
    defender.expect("polling_step_cast", "against:title:B1")
    defender.expect("polling_step_cast", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert "scalpel_tongue" not in seen_at_p2s_first_turn[0]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_canceling_an_already_cast_source_retroactively_removes_its_votes():
    """P1 casts their own political-action-card vote "for"; P2 casts
    title:B1 "against" (now eligible); P1 then uses the fake Scalpel Tongue
    option on their own next turn to cancel it -- the final tally must be
    1-0 (passes), not 1-1 (ties, fails), and `title:B1` must be gone from
    the final `casts` log."""
    provider, locked = _fake_scalpel_tongue("title:B1")
    hooks.register(POLLING_STEP_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "scalpel_tongue")
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    votes_for, votes_against, casts = resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert (votes_for, votes_against) == (1, 0)  # title:B1's -1 against was undone
    assert all(source_id != "title:B1" for (_p, source_id, _v, _d) in casts)
    assert locked == ["title:B1"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_canceled_source_cannot_cast_again_this_referendum():
    """Even though `title:B1` is removed from `remaining` the instant it
    casts (ordinary casting, unrelated to cancellation), this proves the
    cancellation path leaves it unable to cast again: P2 is never offered a
    `"polling_step_cast"` decision at all after the cancellation -- there is
    nothing left for P2 to cast, and `title:B1` no longer qualifies the fake
    provider's own `"has cast votes"` check (it was removed from `casts`),
    so no cancel option is offered to re-trigger it either."""
    provider, _locked = _fake_scalpel_tongue("title:B1")
    hooks.register(POLLING_STEP_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    offered_to_p2: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if self.player_id == "P2" and decision.kind == "polling_step_cast":
                offered_to_p2.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "scalpel_tongue")
    defender = RecordingAgent("P2")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert len(offered_to_p2) == 1  # P2's one and only "polling_step_cast" decision
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_canceling_a_source_resets_the_consecutive_pass_counter():
    """A cancellation is treated exactly like a cast for the
    alternation/closing logic -- it must not, by itself, let the window
    close prematurely (OQ-20's own "a fresh full lap with nobody casting
    anything" closing condition)."""
    provider, _locked = _fake_scalpel_tongue("title:B1")
    hooks.register(POLLING_STEP_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, title="Primogen")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "scalpel_tongue")  # resets the pass counter
    actor.expect("polling_step_cast", "for:title:V1")  # still gets a further turn
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    votes_for, votes_against, _casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("V1")
    )

    # 1 (political action card) + 1 (V1's own Primogen title) for vs 0
    # against (B1's Primogen title cast against, then canceled).
    assert (votes_for, votes_against) == (2, 0)
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_mid_cast_hook_context_carries_the_caster_identity_and_casts_log():
    seen: list[dict] = []

    def recording_provider(state, context):
        if context.get("phase") != "mid_cast":
            return []
        seen.append(dict(context))
        return []

    hooks.register(POLLING_STEP_HOOK, recording_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert seen  # offered at least once
    assert seen[0]["caller"] == "P1"
    assert seen[0]["other"] == "P2"
    assert seen[0]["caller_vampire_id"] == "V1"
    assert seen[0]["casts"] == []  # nothing cast yet on P1's very first turn


def test_no_mid_cast_provider_registered_is_a_zero_regression_no_op():
    """With nothing registered against `POLLING_STEP_HOOK` at all, the
    merged offer contributes nothing -- byte-for-byte the pre-OQ-37
    `"polling_step_cast"` choice set (mirrors every existing `test_politics.
    py` scenario, none of which registers this hook for the cast step)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    votes_for, votes_against, _casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("V1")
    )

    assert (votes_for, votes_against) == (1, 0)
    actor.assert_exhausted()
