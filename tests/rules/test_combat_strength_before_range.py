"""`combat_state` (OQ-60 primitive, `engine/damage.py::COMBAT_STATE_CONTEXT_KEY`)
threaded into `BEFORE_RANGE_HOOK`'s and `COMBAT_STRENGTH_MODIFIER_HOOK`'s own
contexts (`engine/combat.py::_ask_before_range`/`_strike_strength`, reached
via `_resolve_one_strike`/`_resolve_strike_pair`) -- the same combat-scoped
scratch dict `MANEUVER_HOOK`/`DAMAGE_PREVENTION_HOOK` already receive
(`cards/saku_pihlajamaki.py`'s/`cards/opikun.py`'s own once-per-combat caps).

Motivating card (still `Status.BLOCKED`, `cards/kasim_bayar.py`, krcg id
201598): "Once each combat, Kasim can discard a political action card
before range is determined to get +2 strength that combat" needs a flag
recorded during the Before Range window (Rulebook §4 Combat Sequence step 1)
to (a) cap the discard at once per combat and (b) make the resulting bonus
persist through every later strike of that same combat, across rounds, but
never survive into a separate, later combat for the same vampire in the same
turn (a vampire can fight more than one separate combat per turn, e.g. one
per block attempt it is involved in). These are scenario tests for the
*mechanism* only, using a fake `BEFORE_RANGE_HOOK`/`COMBAT_STRENGTH_MODIFIER_
HOOK` pair shaped like that clause -- Kasim Bayar itself stays a follow-up
`card-implementer` pass.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    BEFORE_RANGE_HOOK,
    COMBAT_STATE_CONTEXT_KEY,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    run_combat,
)
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK
from vtesbot.engine.decision import Choice

BONUS_KEY = "fake_kasim_bonus_active"
BONUS_AMOUNT = 2


def _register_fake_kasim_bayar_pair() -> None:
    """A once-per-combat `BEFORE_RANGE_HOOK` activation, gated and recorded
    in `combat_state` by the acting vampire's own instance id, read back by a
    `COMBAT_STRENGTH_MODIFIER_HOOK` provider (the `sum_modifiers` plain-
    callable shape, matching `cards/valeriya_zinovieva.py`'s own provider) --
    exactly the two hooks this test proves are now wired together."""

    def before_range_provider(state, context):
        del state
        if context.get("player") != context.get("acting_player"):
            return []  # only the acting combatant may discard, per the card text
        combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
        vampire_id = context.get("acting_vampire")
        if combat_state is None or vampire_id is None:
            return []
        if combat_state.get(BONUS_KEY, {}).get(vampire_id):
            return []  # "once each combat": already used this combat

        def activate(s):
            del s
            combat_state.setdefault(BONUS_KEY, {})[vampire_id] = True

        return [
            hooks.HookOption(
                choice=Choice("activate_bonus", "Discard political action for +2 strength"),
                apply=activate,
            )
        ]

    def strength_provider(state, context):
        del state
        combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
        vampire_id = context.get("vampire")
        if combat_state is None or vampire_id is None:
            return 0
        if combat_state.get(BONUS_KEY, {}).get(vampire_id):
            return BONUS_AMOUNT
        return 0

    hooks.register(BEFORE_RANGE_HOOK, before_range_provider)
    hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, strength_provider)


def _register_damage_logger(calls: list[int]) -> None:
    """Logs the pre-mend normal damage `DAMAGE_PREVENTION_HOOK` sees for
    every strike, without preventing anything -- the signal this test reads
    to confirm the actual strength a hand strike computed."""

    def provider(state, context):
        del state
        calls.append(context["damage"]["normal"])
        return []

    hooks.register(DAMAGE_PREVENTION_HOOK, provider)


def _combat_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=10)
    return builder.build()


def test_before_range_activated_bonus_persists_through_every_later_strike_same_combat():
    """ "that combat" -- the +2 activated once, before range is determined,
    applies to V1's hand strike in round 1 *and* again in round 2 of the
    same combat (no re-activation offered or needed the second time)."""
    calls: list[int] = []
    _register_fake_kasim_bayar_pair()
    _register_damage_logger(calls)
    game = _combat_game()

    actor = ScriptedAgent("P1")
    actor.expect("before_range", "activate_bonus")
    actor.expect("strike_choice", "hand_strike")  # round 1: 1 (base) + 2 (bonus) = 3
    actor.expect("press", "press")
    actor.expect("press", "end_combat")
    actor.expect("strike_choice", "hand_strike")  # round 2: bonus still active
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "3")
    defender.expect("press", "end_combat")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "3")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert calls == [3, 3]  # both rounds: base 1 + the once-activated +2 bonus
    assert game.vampire("B1").zone == "ready"  # fully mended both times
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_bonus_does_not_leak_into_a_separate_later_combat_same_turn():
    """A vampire can fight more than one separate combat in the same turn
    (e.g. a second block attempt against the same acting minion). Each
    `run_combat` call creates its own fresh `combat_state` dict (module
    docstring, `engine/combat.py::run_combat`), so an activation recorded in
    one combat must not still read as active in a second, independent
    `run_combat` call for the very same pair of vampires -- proven here by
    declining the activation in combat 2 and confirming the strike is back
    to base strength, not the bonus."""
    calls: list[int] = []
    _register_fake_kasim_bayar_pair()
    _register_damage_logger(calls)
    game = _combat_game()

    # --- Combat 1: bonus activated, deals 3 (1 base + 2 bonus). ---
    actor = ScriptedAgent("P1")
    actor.expect("before_range", "activate_bonus")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "3")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))
    actor.assert_exhausted()
    defender.assert_exhausted()
    assert calls == [3]

    # --- Combat 2: same pair, same turn, no activation this time. ---
    actor2 = ScriptedAgent("P1")
    actor2.expect("before_range", "pass")  # declines: the bonus is not re-activated
    actor2.expect("strike_choice", "hand_strike")
    actor2.expect("press", "end_combat")
    defender2 = ScriptedAgent("P2")
    defender2.expect("strike_choice", "no_strike")
    defender2.expect("mend_damage", "1")
    defender2.expect("press", "end_combat")
    game.state.agents["P1"] = actor2
    game.state.agents["P2"] = defender2

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert calls == [3, 1]  # combat 2's strike is base strength only: no leaked bonus
    actor2.assert_exhausted()
    defender2.assert_exhausted()
