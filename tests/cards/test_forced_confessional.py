"""Forced Confessional (`src/vtesbot/cards/forced_confessional.py`, krcg id
102250).

Card text: "Only usable if a minion attempts to block.\n[dom] The blocking
minion gets -1 intercept.\n[DOM] That attempt fails and the blocking minion
cannot attempt to block this action again."

One assertion per clause/qualifier (CLAUDE.md "One test per clause"): the
shared "only usable if a minion attempts to block" gate (nothing offered at
`attempt_block`'s own proactive point); the basic clause's own Salubri
clan/`dom` discipline/hand gates and its `INTERCEPT_DECREASE_HOOK` end-to-end
wiring, scoped to the one specific blocking vampire only; the superior
clause's own superior-`DOM` gate and its `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK`
end-to-end wiring -- forcing the current attempt to fail outright *and*
barring that specific vampire from attempting to block this same action
again, while a different vampire remains a legal candidate.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.forced_confessional import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import INTERCEPT_DECREASE_HOOK, attempt_block

NAME = "Forced Confessional"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action modifier")


def test_card_is_registered_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.INTERCEPT_DECREASE in reg.hooks
    assert registry.Hook.FORCE_BLOCK_ATTEMPT_FAILURE in reg.hooks


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# -- shared "only usable if a minion attempts to block" gate -----------------


def _proactive_decrease_options(game, *, actor: str, defender: str, acting_vampire_id: str):
    """`INTERCEPT_DECREASE_HOOK`'s own proactive offer point (top of
    `attempt_block`'s retry loop) carries no `blocking_vampire` context at
    all -- this card must never offer anything there."""
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


def test_basic_clause_not_offered_before_a_block_candidate_is_fixed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("dom",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    options = _proactive_decrease_options(game, actor="P1", defender="P2", acting_vampire_id="V1")

    assert options == []


def test_neither_clause_asks_the_actor_anything_before_a_blocker_is_chosen():
    """End-to-end confirmation: `INTERCEPT_DECREASE_HOOK`'s own proactive
    offer point (before any candidate is fixed) carries no
    `blocking_vampire` context, so this card's basic clause offers nothing
    there -- no `intercept_decrease` decision is raised at all, and the
    defender declining leaves the attempt undecided (`None`), with the
    actor never consulted."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("DOM",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")  # no answers scripted: raises if ever asked anything here.
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()


# -- "[dom] The blocking minion gets -1 intercept." (basic clause) ----------


def test_basic_not_offered_without_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, clan="Salubri")
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None  # succeeds normally: no clause ever offered.
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_not_offered_without_salubri_clan():
    """Clan requirement is independent of, and in addition to, the
    Dominate discipline gate."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, disciplines=("dom",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("dom",), clan="Salubri"
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_clause_end_to_end_flips_a_would_have_succeeded_block_to_a_failure():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("dom",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "forced_confessional:basic")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_clause_penalty_does_not_leak_onto_a_different_later_blocker():
    """ "The blocking minion" is the one specific vampire fixed when the
    card is played -- it must not persist onto a *different* vampire's own,
    separate block attempt later in the same action."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("dom",), clan="Salubri"
    )
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("stealth_modifier", "forced_confessional:basic")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # fails: intercept -1 < stealth 0
    defender.expect("block_attempt", "block_with:B2")  # succeeds: unaffected, intercept 0 >= 0
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    assert blocker.instance_id == "B2"
    actor.assert_exhausted()
    defender.assert_exhausted()


# -- "[DOM] That attempt fails and the blocking minion cannot attempt to
#     block this action again." (superior clause) ---------------------------


def test_superior_not_offered_with_only_basic_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("dom",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    # Only the basic clause may be offered; picking it proves the superior
    # one was never in the choice set to begin with (would otherwise be a
    # duplicate "stealth_modifier" option error if it leaked through).
    actor.expect("stealth_modifier", "forced_confessional:basic")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_not_offered_without_salubri_clan():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, disciplines=("DOM",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("DOM",), clan="Salubri"
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clause_offered_and_bars_the_blocker_even_while_already_failing_on_the_numbers():
    """rules-auditor finding: `base_stealth=1` with B1's default intercept 0
    and no intercept-boost provider means B1's attempt already fails on the
    raw numbers alone. The superior clause's "cannot attempt to block this
    action again" half must still be offered to the actor there -- it has
    nothing to do with whether the numbers already fail -- and B1 must be
    gone from the next `block_attempt` choice set while B2 remains legal."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("DOM",), clan="Salubri"
    )
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=3)
    game = builder.build()
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1").expect("stealth_modifier", "forced_confessional:superior")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # already fails: stealth 1 > intercept 0.
    defender.expect("block_attempt", "decline")  # B1 excluded; B2 still offered, declined.
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=1, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    block_decisions = [d for d in seen_decisions if d.kind == "block_attempt"]
    assert len(block_decisions) == 2
    second_choice_values = {c.value for c in block_decisions[1].choices}
    assert "block_with:B1" not in second_choice_values  # cannot attempt to block again.
    assert "block_with:B2" in second_choice_values  # a different vampire remains legal.
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clause_forces_failure_and_bars_the_same_vampire_while_another_remains_legal():
    """The full superior-clause scenario: B1's currently-succeeding attempt
    (intercept 0 >= stealth 0) is forced to fail outright, B1 is then never
    offered again this action, and a different vampire (B2) remains a legal
    block candidate, eventually succeeding normally."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("DOM",), clan="Salubri"
    )
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=3)
    game = builder.build()
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    actor = RecordingAgent("P1").expect("stealth_modifier", "forced_confessional:superior")
    game.state.agents["P1"] = actor
    defender = RecordingAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # forced to fail; B1 barred.
    defender.expect("block_attempt", "block_with:B2")  # still legal; succeeds normally.
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is not None
    assert blocker.instance_id == "B2"
    assert game.vampire("B1").locked is False  # the forced-failed attempt never locked B1.
    block_decisions = [d for d in seen_decisions if d.kind == "block_attempt"]
    assert len(block_decisions) == 2
    second_choice_values = {c.value for c in block_decisions[1].choices}
    assert "block_with:B1" not in second_choice_values  # cannot attempt to block again.
    assert "block_with:B2" in second_choice_values  # a different vampire remains legal.
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_clause_forces_failure_outright_even_with_no_other_candidate_left():
    """Real call site proof through `attempt_block` directly with a single
    defending vampire: once forced to fail and barred, nothing legal
    remains to block with -- `attempt_block` returns `None` with no further
    `block_attempt` decision raised (not even a re-offer of B1)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, disciplines=("DOM",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()
    actor = ScriptedAgent("P1").expect("stealth_modifier", "forced_confessional:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("V1")
    )

    assert blocker is None
    actor.assert_exhausted()
    defender.assert_exhausted()  # no second block_attempt decision: B1 was the only candidate.
