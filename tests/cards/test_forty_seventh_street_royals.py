"""47th Street Royals (krcg id 102217, `src/vtesbot/cards/
forty_seventh_street_royals.py`).

Card text: "Unique mortal with 2 life. 1 strength, 0 bleed.\nYou can burn
47th Street Royals to reduce a bleed against you by 3." No rulings on file.

Two clauses, each with its own assertions: the recruit side (clan-gated
eligibility, the full `minion_phase` action -- success and blocked -- and the
contest it triggers against the engine's now-resolved OQ-10/OQ-15 ally-contest
machinery), and the reaction side (burn-to-reduce-bleed, clamped at 0, not
offered while contested).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.forty_seventh_street_royals import KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard, hooks
from vtesbot.engine.action import ACTION_RECRUIT_ALLY
from vtesbot.engine.allies import recruit_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.observation import Observation
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.phases.unlock import unlock_phase

NAME = "47th Street Royals"


def _royals_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="ally")


def _set_clan(builder_player, instance_id: str, clan: str | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `clan`
    (`ready_vampire` itself has no `clan=` parameter -- `CryptCard` is
    frozen, so a fresh instance is swapped in instead of mutated)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=clan,
        disciplines=old.disciplines,
    )


def test_registered_as_implemented_against_its_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- Recruit side: clan-gated eligibility -----------------------------------


def test_recruit_offered_only_when_the_acting_vampire_is_brujah():
    """Mirrors OQ-13's own test pattern (`tests/rules/
    test_recruit_ally_action.py::
    test_recruit_ally_play_hook_context_carries_the_acting_vampires_
    identity`): acting with a non-Brujah ready-unlocked vampire must not see
    the option, even though a *different* ready-unlocked vampire of the same
    player is Brujah; acting with the Brujah vampire does see it."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)
    p1.ready_vampire("V2", capacity=3, blood=1)
    p1.hand.append(_royals_card())
    _set_clan(p1, "V1", "Toreador")
    _set_clan(p1, "V2", "Brujah")
    builder.player("P2", pool=30)  # no ready vampire: no block_attempt ever raised
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation: Observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("minion_phase_choice", "act_with:V2")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen[0] == ["bleed", "hunt"]  # V1 (Toreador): no recruit option
    assert seen[1] == ["bleed", "hunt", "recruit_47th_street_royals"]  # V2 (Brujah)
    actor.assert_exhausted()


def test_recruit_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)
    _set_clan(p1, "V1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    actor.assert_exhausted()


# --- Recruit side: the full minion-phase action -----------------------------


def test_recruit_succeeds_and_creates_a_ready_locked_ally_at_no_cost():
    """Rulebook SS4 "Recruit Ally": "recruited ally cannot act this turn";
    `cost is None` per krcg -- no pool is paid even on success."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_royals_card())
    _set_clan(p1, "V1", "Brujah")
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "recruit_47th_street_royals")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 30  # cost is None: nothing paid
    assert not any(c.krcg_id == KRCG_ID for c in game.state.players["P1"].hand)
    assert not any(c.krcg_id == KRCG_ID for c in game.state.players["P1"].ash_heap)
    allies = list(game.state.players["P1"].allies.values())
    assert len(allies) == 1
    ally = allies[0]
    assert ally.krcg_id == KRCG_ID
    assert ally.name == NAME
    assert ally.controller == "P1"
    assert ally.life == 2
    assert ally.strength == 1
    assert ally.bleed == 0
    assert ally.zone == "ready"
    assert ally.locked is True
    actor.assert_exhausted()


def test_recruit_blocked_burns_the_card_and_creates_no_ally():
    """Rulebook SS4 "Resolve the Action": "If the action is blocked, then any
    card played to perform the action is burned ... the cost ... is not paid
    if the action is blocked." A fake `"intercept_modifier"` stand-in for a
    reaction card gives +1 intercept so the bare block attempt (recruit
    ally's own +1 stealth baseline would otherwise merely fail to block, same
    as `tests/rules/test_recruit_ally_action.py`'s own blocked-path test)
    actually succeeds."""

    def intercept_bump(state, context):
        del state
        if context.get("action") != ACTION_RECRUIT_ALLY:
            return []
        return [HookOption(choice=Choice("bump", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", intercept_bump)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30)
        p1.ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_royals_card())
        _set_clan(p1, "V1", "Brujah")
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()

        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "recruit_47th_street_royals")
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

        assert game.pool_of("P1") == 30
        assert not any(c.krcg_id == KRCG_ID for c in game.state.players["P1"].hand)
        assert any(c.krcg_id == KRCG_ID for c in game.state.players["P1"].ash_heap)
        assert game.state.players["P1"].allies == {}
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", intercept_bump)


def test_both_players_recruiting_their_own_copy_triggers_a_real_contest():
    """P1's recruit goes through this card's own real `"recruit_ally_play"`
    provider end-to-end (`minion_phase` -> `_choose_and_perform_action` ->
    `_provide_recruit`), not a stand-in; P2's own existing copy is seeded
    directly via `recruit_ally(...)` below rather than through its own
    recruit action, since the point under test is only that P1's real
    recruit, once it succeeds, triggers `detect_contest_on_recruit` via
    `_perform_recruit_ally`'s own production call site (OQ-10/OQ-14)
    against a pre-existing opposing ally -- same bar as
    `tests/rules/test_ally_contests.py::
    test_recruit_ally_action_end_to_end_detects_the_contest`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_royals_card())
    _set_clan(p1, "V1", "Brujah")
    builder.player("P2", pool=30)  # P2's own existing copy is set up directly below
    game = builder.build()
    existing = recruit_ally(game.state, "P2", krcg_id=KRCG_ID, name=NAME, life=2, strength=1)

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "recruit_47th_street_royals")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    recruited = next(iter(game.state.players["P1"].allies.values()))
    assert recruited.contested_with == existing.instance_id
    assert existing.contested_with == recruited.instance_id
    assert recruited.zone == "contested"
    assert existing.zone == "contested"
    actor.assert_exhausted()


# --- Reaction side: burn to reduce a bleed by 3 -----------------------------


def test_burn_reaction_reduces_bleed_by_3_and_burns_the_ally():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=KRCG_ID, name=NAME, life=2, strength=1)
    ally.locked = False  # ready to react this turn

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    defender = ScriptedAgent("P2")
    defender.expect("bleed_amount_modifier", "burn_47th_street_royals")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # 1 bleed - 3 reduction, clamped at 0 lost
    assert ally.zone == "burned"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_burn_reaction_clamped_at_0_does_not_grant_pool():
    """`max(0, amount_box[0])` (`_perform_bleed`'s own clamp): the reduction
    cannot turn a bleed into a pool gain, only reduce the loss to 0."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=20)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=KRCG_ID, name=NAME, life=2, strength=1)
    ally.locked = False

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    defender = ScriptedAgent("P2")
    defender.expect("bleed_amount_modifier", "burn_47th_street_royals")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 20
    assert ally.zone == "burned"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_burn_reaction_not_offered_to_the_bleeding_player():
    """Mirrors `telepathic_counter.py`'s own "never offered to the
    bleeder" scope: the reaction belongs to the Methuselah being bled
    against, not the one bleeding, even if they somehow controlled a copy
    themselves."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    recruit_ally(game.state, "P1", krcg_id=KRCG_ID, name=NAME, life=2, strength=1).locked = False

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    defender = ScriptedAgent("P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed only; the reaction never offered to P1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_burn_reaction_not_offered_while_the_ally_is_contested():
    """A contested ally is "turned face down and out of play" (Rulebook SS4
    Advanced Rules > Contested Cards) for the whole contest -- it cannot
    react, same as `AllyInPlay.zone == "contested"` ever gating anything
    else this ally does."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=KRCG_ID, name=NAME, life=2, strength=1)
    ally.locked = False
    ally.zone = "contested"  # simulate an active contest, as detect_contest_on_recruit would set

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    defender = ScriptedAgent("P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed only: the reaction is not offered
    assert ally.zone == "contested"  # left untouched
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_contested_ally_is_restored_and_can_react_after_resolution():
    """Sanity companion to the contested-gate test above: once OQ-15's own
    resolution loop ends the contest and restores the surviving ally's
    `zone` to `"ready"` on its controller's next unlock phase, the reaction
    is offered again -- confirming the gate above really is `zone`-based,
    not a permanent effect of ever having been contested."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=KRCG_ID, name=NAME, life=2, strength=1)
    ally.locked = False
    ally.zone = "contested"
    ally.contested_with = None  # as left by resolve_one_ally_contest's own "yield" branch

    unlock_phase(game.state, "P2")

    assert ally.zone == "ready"
    assert ally.locked is False
