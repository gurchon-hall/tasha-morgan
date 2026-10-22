"""The "woken" eligibility override (ENG-028,
resolved -- Reading A): On the Qui Vive (krcg id 101321, Reaction), "This
minion wakes (they ignore the requirement to be unlocked for playing
reaction cards and attempting to block until the end of the action). If
this minion is an ally, they do not unlock as normal during their next
unlock phase."

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* -- `VampireInPlay.woken`/`is_ready_unlocked`, `engine/action.py::
clear_woken_vampires`, and `AllyInPlay.skip_next_unlock`/the now-fixed
unconditional ally-unlock step -- using trivial fake providers standing in
for a reaction card and for On the Qui Vive itself. On the Qui Vive's own
card module remains `card-implementer`'s job once this capability exists;
it stays registered `blocked`/`ENG-028`.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    INTERCEPT_DECREASE_HOOK,
    attempt_block,
    clear_woken_vampires,
    perform_minion_action,
)
from vtesbot.engine.allies import recruit_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.pool import lose_pool

REACTION_ELIGIBILITY_HOOK = "fake_reaction_eligibility"
"""Stand-in for a real reaction-card hook (e.g. `"bleed_amount_modifier"`,
`telepathic_counter.py`'s own) -- every such provider in `src/vtesbot/
cards/` gates its own candidate list with `vampire.is_ready_unlocked`
exactly like this fake one does, so proving the fake one picks up a woken,
locked vampire proves the real ones do too, with zero per-card change."""


def _register_eligibility_provider(seen: list[str]) -> None:
    def provider(state, context):
        player = context["player"]
        for vampire in state.players[player].vampires.values():
            if vampire.is_ready_unlocked:
                seen.append(vampire.instance_id)
        return []

    hooks.register(REACTION_ELIGIBILITY_HOOK, provider)


# --- VampireInPlay.woken / is_ready_unlocked --------------------------------


def test_woken_locked_vampire_is_ready_unlocked():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30)
    game = builder.build()

    game.vampire("V1").woken = True

    assert game.vampire("V1").is_ready_unlocked is True
    assert game.vampire("V1").locked is True  # "while remaining structurally locked"


def test_locked_non_woken_vampire_is_still_not_ready_unlocked():
    """Zero-regression check: `woken` defaults to `False`, so an ordinary
    locked vampire is unaffected."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30)
    game = builder.build()

    assert game.vampire("V1").is_ready_unlocked is False


# --- Block candidacy (engine/action.py::attempt_block) ----------------------


def test_woken_locked_vampire_is_offered_as_an_ordinary_block_candidate():
    """`ready_unlocked_vampires`/`attempt_block` pick up the woken vampire
    for free -- no `BLOCK_CANDIDATE_INJECTION_HOOK`-style special-casing, and
    the normal stealth/intercept ping-pong still applies (not an
    unconditional success)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()
    game.vampire("B1").woken = True
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_locked_non_woken_vampire_is_not_offered_as_a_block_candidate():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()
    defender = ScriptedAgent("P2")  # no decision expected: nothing legal to offer
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    defender.assert_exhausted()


# --- Reaction-card eligibility (every existing provider's own check) -------


def test_woken_locked_vampire_passes_a_reaction_card_eligibility_check():
    seen: list[str] = []
    _register_eligibility_provider(seen)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30)
    game = builder.build()
    game.vampire("V1").woken = True

    hooks.offer(REACTION_ELIGIBILITY_HOOK, game.state, player="P1")

    assert seen == ["V1"]


def test_locked_non_woken_vampire_fails_a_reaction_card_eligibility_check():
    seen: list[str] = []
    _register_eligibility_provider(seen)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30)
    game = builder.build()

    hooks.offer(REACTION_ELIGIBILITY_HOOK, game.state, player="P1")

    assert seen == []


# --- clear_woken_vampires ----------------------------------------------------


def test_clear_woken_vampires_resets_the_flag_for_both_players():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()
    game.vampire("V1").woken = True
    game.vampire("B1").woken = True

    clear_woken_vampires(game.state)

    assert game.vampire("V1").woken is False
    assert game.vampire("B1").woken is False
    # Clearing `woken` never touches `locked` itself (structural lock state
    # is untouched by waking or by its own cleanup).
    assert game.vampire("V1").locked is True
    assert game.vampire("B1").locked is True


# --- End-of-action cleanup, through the real call site ----------------------


def _woken_blocker_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    # blood=0 on B1: no mend decision needed in the combat branch below.
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, locked=True)
    return builder.build()


def test_woken_flag_is_cleared_at_the_end_of_an_unblocked_action():
    """The unblocked-resolved exit point, reached via a decline: B1 is woken
    (eligible to block, per the tests above) but the defender's agent
    declines anyway, so the action resolves unblocked -- the cleanup at that
    branch's own exit must still fire even though a woken candidate was
    legitimately on offer."""
    game = _woken_blocker_game()
    game.vampire("B1").woken = True
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve
    )

    assert resolve_calls == [True]
    assert game.vampire("B1").woken is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_woken_flag_is_cleared_at_the_end_of_a_blocked_action_after_combat():
    """The blocked-then-combat-resolved exit point: B1 is woken, blocks (via
    the normal ping-pong, not an injection), combat resolves, and the
    cleanup at that branch's own exit must still fire -- even though B1
    stays `locked` throughout (re-locked for combat on a successful block,
    exactly like any other blocker)."""
    game = _woken_blocker_game()
    game.vampire("B1").woken = True
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve
    )

    assert resolve_calls == []  # blocked branch: resolve() never ran
    assert game.vampire("B1").woken is False
    assert game.vampire("B1").locked is True  # re-locked for having blocked, unaffected by cleanup
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- game_over short-circuits (rules-auditor finding) -----------------------


def test_woken_flag_is_cleared_even_when_ousted_mid_block_attempt():
    """`clear_woken_vampires` must also run on `perform_minion_action`'s two
    `state.game_over` short-circuits (right after `attempt_block` and right
    after `run_combat`), not only the ordinary unblocked/blocked-resolved
    branches. Here an `INTERCEPT_DECREASE_HOOK` option's own pool cost (the
    actor's proactive block-attempt-phase hook, offered before any block is
    even possible) ousts the defender mid-action -- `attempt_block` itself
    returns `None` without ever reaching the block-candidate step, and
    `perform_minion_action`'s first short-circuit (right after
    `attempt_block`) must still sweep the stale `woken` flag."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=1).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()
    game.vampire("B1").woken = True

    def fake_decrease(state, context):
        del state
        if context["player"] != "P1":
            return []

        def apply(s):
            lose_pool(s, "P2", 1)  # drops P2 to 0 pool -> ousted (check_oust)

        return [hooks.HookOption(choice=Choice("oust_p2", "Pay to oust P2"), apply=apply)]

    hooks.register(INTERCEPT_DECREASE_HOOK, fake_decrease)
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1").expect("intercept_decrease", "oust_p2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve
    )

    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert resolve_calls == []  # the action never got to resolve unblocked
    assert game.vampire("B1").woken is False
    actor.assert_exhausted()


# --- Ally bookkeeping (engine/phases/unlock.py::_unlock_own_allies) ---------


def test_unlock_phase_now_unconditionally_unlocks_a_ready_ally():
    """Fixes the previously-dormant gap this entry's own resolution notes:
    before ENG-028, nothing in the engine ever unlocked a recruited ally
    again (`AllyInPlay.locked` stayed `True` forever)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=1, name="Some Ally", life=1)
    assert ally.locked is True  # "recruited ally cannot act this turn"
    game.state.agents["P1"] = ScriptedAgent("P1")  # no pending effects: no decisions expected

    unlock_phase(game.state, "P1")

    assert ally.locked is False


def test_ally_with_skip_next_unlock_stays_locked_through_one_unlock_phase_only():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=1, name="Some Ally", life=1)
    ally.skip_next_unlock = True
    game.state.agents["P1"] = ScriptedAgent("P1")

    unlock_phase(game.state, "P1")

    assert ally.locked is True  # skipped once
    assert ally.skip_next_unlock is False  # consumed, not left set forever

    unlock_phase(game.state, "P1")

    assert ally.locked is False  # unlocks normally the next time


# --- Stale-flag safety of minion_phase's own two callers (rules-auditor) ---


def test_stale_woken_flag_never_leaks_into_the_next_minion_phase():
    """Pinning regression for the two `rules-auditor`-flagged callers outside
    `VampireInPlay.woken`'s own enumerated set -- `engine/phases/minion.py::
    minion_phase`'s mandatory-hunt loop and its own optional act-with
    candidate list (see `clear_woken_vampires`'s own docstring for why both
    are safe). B1 becomes `woken` as a successful blocker in P1's action,
    stays `locked` afterwards (re-locked for having blocked), and the action
    ends -- `woken` is correctly cleared by `clear_woken_vampires`, so when
    P2's own `minion_phase` next runs (before any unlock phase reaches B1),
    neither caller may treat the still-locked, bloodless B1 as eligible: no
    mandatory hunt is forced on it, and no `act_with:B1` choice is offered
    (i.e. no decision is raised for P2 at all -- its only vampire is
    correctly excluded from both candidate lists)."""
    game = _woken_blocker_game()
    game.vampire("B1").woken = True

    def resolve(pending):
        del pending

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve
    )

    assert game.vampire("B1").woken is False
    assert game.vampire("B1").locked is True  # still locked, not yet unlocked

    p2_next_phase = ScriptedAgent("P2")  # no decision expected at all
    game.state.agents["P2"] = p2_next_phase

    minion_phase(game.state, "P2")

    p2_next_phase.assert_exhausted()
