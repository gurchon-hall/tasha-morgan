"""Determine Range and the maneuver mechanic (`engine/combat.py`): a new
combat step, resolved before the strike step every round, that lets a
card/printed-ability grant move the round between close and long range.

Per the task that added this file, only an ability-granted maneuver *not*
bundled with choosing a strike is exercised here (e.g. Saku Pihlajamäki's
printed "1 optional maneuver each combat") -- fake, test-only providers stand
in for it, proving the *generic* mechanism rather than any one real card's
wording (no combat card using `"maneuver"` is implemented yet).
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    CLOSE_RANGE,
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    HAND_STRIKE_VALUE,
    LONG_RANGE,
    MANEUVER_HOOK,
    ROUND_STATE_CONTEXT_KEY,
    StrikeDamage,
    commit_strike_for_round,
    run_combat,
    strike_committed_this_round,
)
from vtesbot.engine.decision import Choice


def _combat_game(*, acting_label: str = "V1", blocking_label: str = "B1", blocking_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(acting_label, capacity=10, blood=5)
    builder.player("P2", pool=30).ready_vampire(blocking_label, capacity=10, blood=blocking_blood)
    return builder.build()


def _capture_range_via_strength_modifier(captured: list, *, player: str = "P1"):
    """`"combat_strength_modifier"` is a passive, always-consulted hook
    (`hooks.sum_modifiers`) fired from `_strike_strength`, so registering a
    fake provider against it is a convenient, zero-side-effect way to read
    `state.combat_range` at the exact moment a hand strike resolves, without
    inventing a new test-only hook."""

    def capture(state, context):
        if context.get("player") == player:
            captured.append(state.combat_range)
        return 0

    hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, capture)


def test_no_maneuver_choice_is_offered_without_a_registered_provider():
    """Regression guard: with no `"maneuver"` provider registered, Determine
    Range never raises a `maneuver_choice` decision at all (CLAUDE.md "only
    when needed"), and the round stays at the rulebook's own default --
    Rulebook SS4 Combat > Determine Range: "Close range is the default for
    each round." Byte-for-byte the pre-maneuver result: no existing combat
    test's script needed a new entry for this."""
    captured: list = []
    _capture_range_via_strength_modifier(captured)
    game = _combat_game()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured == [CLOSE_RANGE]
    assert game.state.combat_range is None  # reset once combat (run_combat) returns
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_ayelech_colette_worked_example():
    """Rulebook SS4 Combat > Determine Range's own worked example, reproduced
    exactly: "Ayelech has just blocked Colette, and combat ensues. Ayelech
    has a .44 Magnum that allows her to strike for 2 damage at either close
    or long range, and gives her an optional maneuver. Colette, as the acting
    minion, declines to maneuver. Ayelech uses the maneuver from the gun to
    move to long range, where she cannot be harmed by Colette's hand strike.
    Colette plays a maneuver card to get back to close range. However,
    Ayelech has another maneuver card as well, and she plays it to move back
    to long range. Colette has no more maneuvers to play, so the range is set
    to long."

    Colette is the acting minion (she was blocked while bleeding/hunting),
    Ayelech is the blocking minion. Fake `"maneuver"` providers stand in for
    Colette's one maneuver card and Ayelech's gun + second maneuver card (the
    strike-card/weapon-bundled part of the real worked example is out of
    scope for this pass -- see module docstring's "Determine Range and
    maneuvers" section -- only the maneuver grant itself, and the alternation
    it produces, is under test here).
    """
    colette_card_available = {"value": True}
    ayelech_cards_remaining = {"value": 2}

    def colette_maneuver(state, context):
        if context.get("player") != "P1" or not colette_card_available["value"]:
            return []

        def use(s):
            colette_card_available["value"] = False

        return [
            hooks.HookOption(choice=Choice("colette_card", "Colette's maneuver card"), apply=use)
        ]

    def ayelech_maneuver(state, context):
        if context.get("player") != "P2" or ayelech_cards_remaining["value"] <= 0:
            return []
        label = "gun" if ayelech_cards_remaining["value"] == 2 else "second_card"

        def use(s):
            ayelech_cards_remaining["value"] -= 1

        choice = Choice(f"ayelech_{label}", f"Ayelech's {label}")
        return [hooks.HookOption(choice=choice, apply=use)]

    hooks.register(MANEUVER_HOOK, colette_maneuver)
    hooks.register(MANEUVER_HOOK, ayelech_maneuver)
    captured: list = []
    _capture_range_via_strength_modifier(captured)

    game = _combat_game(acting_label="Colette", blocking_label="Ayelech", blocking_blood=0)

    actor = ScriptedAgent("P1")  # Colette, acting
    actor.expect("maneuver_choice", hooks.PASS_VALUE)  # turn 1: declines first opportunity
    actor.expect("maneuver_choice", "colette_card")  # turn 3: back to close
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")  # Ayelech, blocking
    defender.expect("maneuver_choice", "ayelech_gun")  # turn 2: gun to long
    defender.expect("maneuver_choice", "ayelech_second_card")  # turn 4: back to long
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("Colette"), "P2", game.vampire("Ayelech"))

    # Turn 5: Colette has nothing left, declines (no decision raised, since
    # her provider now returns no options). Turn 6: Ayelech also has nothing
    # left (no decision raised either) -- the second consecutive decline
    # that closes the step, with the range left at long from turn 4.
    assert captured == [LONG_RANGE]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_maneuver_grant_is_scoped_to_the_whole_combat_not_reset_each_round():
    """A Saku Pihlajamäki-style grant ("1 optional maneuver each combat") must
    stay used for every round of the *same* combat, unlike a combat card's
    own round-scoped grant -- contrast with `test_combat_dodge_and_
    additional_strike.py::test_additional_strike_limit_resets_every_round_
    of_the_same_combat`, which proves the opposite lifetime for a different
    mechanism. `context["combat_state"]` is the shared dict `run_combat`
    creates once, outside its per-round loop (module docstring's "Per-combat,
    not per-round, scoping" paragraph)."""

    def saku_style_maneuver(state, context):
        if context.get("player") != "P1":
            return []
        used = context["combat_state"].setdefault("saku_used", set())
        if context["vampire"] in used:
            return []

        def use(s):
            used.add(context["vampire"])

        return [hooks.HookOption(choice=Choice("saku_maneuver", "Saku's maneuver"), apply=use)]

    hooks.register(MANEUVER_HOOK, saku_style_maneuver)
    captured: list = []
    _capture_range_via_strength_modifier(captured)

    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    # Round 1: use the once-per-combat grant.
    actor.expect("maneuver_choice", "saku_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "press")
    # Round 2: the grant was already used this combat -- no maneuver_choice
    # decision at all, even though round_state-scoped mechanisms would reset.
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # round 1
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Round 1's hand strike wounds B1 (0 blood, no mend decision possible);
    # round 2's hand strike on an already-wounded B1 sends it to torpor,
    # ending combat at once with no round-2 press decision for either side.
    assert game.zone_of("B1") == "torpor"
    assert captured == [LONG_RANGE, CLOSE_RANGE]
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Maneuver bundled with a strike (OQ-28, `docs/OPEN_QUESTIONS.md`, resolved) ---


def test_strike_bundled_maneuver_commits_the_initial_strike_and_skips_the_strike_choice():
    """A `MANEUVER_HOOK` grant that also calls `commit_strike_for_round` --
    the generic mechanism a card like Slam's superior "[POT] As above, with 1
    optional maneuver, only usable to get to close range" (where "as above"
    bundles the maneuver with "Strike: hand strike at +2 damage") must use --
    fixes the maneuvering combatant's *initial* strike of the round to that
    same bundled effect. Rulebook SS4 Combat > Strike > Choose Strike: "If a
    minion has used a maneuver from a strike ... this round, then they cannot
    choose any other strike for their initial strike of the round." No
    `strike_choice` decision is raised for P1 at all this round -- not "may
    also pick this strike," a hard lock, enforced by never scripting one for
    P1 below (an unscripted-but-raised decision would fail loudly via
    `ScriptedAgent`'s own "unexpected decision" check)."""
    card_available = {"value": True}

    def bundled_maneuver(state, context):
        if context.get("player") != "P1" or not card_available["value"]:
            return []

        def strike_apply(s):
            return StrikeDamage(amount=3)

        def use(s):
            card_available["value"] = False
            commit_strike_for_round(
                context,
                hooks.HookOption(
                    choice=Choice("fake_card:superior", "Fake card [SUP]: bundled strike"),
                    apply=strike_apply,
                ),
            )

        return [
            hooks.HookOption(
                choice=Choice("fake_card:maneuver", "Fake card: maneuver + strike"), apply=use
            )
        ]

    hooks.register(MANEUVER_HOOK, bundled_maneuver)
    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_card:maneuver")  # turn 1: claims the bundled grant
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    # Turn 2: B1 has no "maneuver" provider registered, so no decision at all.
    defender.expect("strike_choice", "no_strike")  # B1's own strike is untouched, full choice
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").wounded is True  # took the committed strike's 3 damage, 0 blood
    assert game.vampire("B1").blood == 0
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_committed_strike_lock_does_not_extend_to_additional_strikes():
    """The Rulebook's own restriction is scoped to "their initial strike of
    the round" only (Choose Strike, quoted above) -- Additional Strikes
    (Rulebook SS4 Combat > Additional Strikes, a separate, later choose-
    strike step) are unaffected: a combatant whose initial strike was
    pre-committed by a strike-bundled maneuver still gets a full, independent
    strike choice for any additional strike they separately gain that same
    round. Proves `commit_strike_for_round`'s entry is popped (consumed), not
    merely read, by `_ask_strike`."""
    maneuver_available = {"value": True}

    def bundled_maneuver(state, context):
        if context.get("player") != "P1" or not maneuver_available["value"]:
            return []

        def use(s):
            maneuver_available["value"] = False
            commit_strike_for_round(
                context,
                hooks.HookOption(
                    choice=Choice("fake_card:superior", "Fake card [SUP]: bundled strike"),
                    apply=lambda s: StrikeDamage(amount=1),
                ),
            )

        return [
            hooks.HookOption(
                choice=Choice("fake_card:maneuver", "Fake card: maneuver + strike"), apply=use
            )
        ]

    additional_available = {"value": True}

    def additional_strike(state, context):
        if context.get("player") != "P1" or not additional_available["value"]:
            return []

        def use(s):
            additional_available["value"] = False

        return [
            hooks.HookOption(
                choice=Choice("fake_card:additional", "Fake additional strike"), apply=use
            )
        ]

    hooks.register(MANEUVER_HOOK, bundled_maneuver)
    hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, additional_strike)
    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_card:maneuver")
    # Initial strike pair: pre-committed, no strike_choice decision for P1.
    actor.expect("additional_strike_choice", "fake_card:additional")
    actor.expect("strike_choice", "hand_strike")  # additional strike: full, independent choice
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # initial pair; B1 has no additional strike
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # B1 (0 blood) is wounded by the initial committed strike's 1 damage, then
    # sent to torpor by the additional strike's own hand strike -- combat
    # ends at once (Rulebook SS4: "combat ends at once if a combatant is no
    # longer ready"), with no press decision for either side. The scripted
    # answers above are exhausted either way: this is what proves the
    # additional strike actually reached a full, independent `hand_strike`
    # choice rather than reusing the already-consumed committed strike.
    assert game.zone_of("B1") == "torpor"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_plain_maneuver_does_not_commit_a_strike_and_full_choice_remains():
    """Regression guard: a plain `MANEUVER_HOOK` grant that never calls
    `commit_strike_for_round` -- the same shape Pursuit's own basic "[cel]
    Maneuver." clause and Saku Pihlajamäki's printed ability use (OQ-27,
    `cards/pursuit.py`) -- must leave the maneuvering combatant's strike step
    completely untouched: a full, independent `strike_choice` decision is
    still raised for them afterward, exactly as before this pass's
    `round_state` threading into `MANEUVER_HOOK`'s own context."""
    card_available = {"value": True}

    def plain_maneuver(state, context):
        if context.get("player") != "P1" or not card_available["value"]:
            return []

        def use(s):
            card_available["value"] = False

        return [hooks.HookOption(choice=Choice("plain_maneuver", "Plain maneuver"), apply=use)]

    hooks.register(MANEUVER_HOOK, plain_maneuver)
    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "plain_maneuver")
    actor.expect("strike_choice", "hand_strike")  # full, independent choice -- not locked
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").wounded is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_second_strike_bundled_maneuver_is_not_offered_once_committed():
    """Rulebook SS4 Combat > Determine Range: "If a minion uses the maneuver
    from a strike card or a weapon, they are effectively choosing their
    strike as well. As such, they cannot use a second strike card or weapon
    to maneuver again in the same round." Two independent fake providers
    stand in for a vampire holding two separate strike-bundled-maneuver
    sources (e.g. two physical copies of Slam, or Slam plus .44 Magnum) --
    once the first commits, the second must never even be *offered* again,
    not merely be unusable if picked: each provider below gates its own
    offer on `not strike_committed_this_round(context)`, the house
    convention `additional_strike_limit_used` already establishes for the
    "(limited)" cap. If that gate were missing, P1's third `maneuver_choice`
    decision would offer `"card_b:maneuver"`, which this test's script does
    not expect -- `ScriptedAgent` would fail loudly on the mismatch."""
    card_a_available = {"value": True}
    card_b_available = {"value": True}

    def provide_card_a(state, context):
        if context.get("player") != "P1" or not card_a_available["value"]:
            return []
        if strike_committed_this_round(context):
            return []

        def use(s):
            card_a_available["value"] = False
            commit_strike_for_round(
                context,
                hooks.HookOption(
                    choice=Choice("card_a:strike", "Card A's bundled strike"),
                    apply=lambda s: StrikeDamage(amount=2),
                ),
            )

        return [hooks.HookOption(choice=Choice("card_a:maneuver", "Card A"), apply=use)]

    def provide_card_b(state, context):
        if context.get("player") != "P1" or not card_b_available["value"]:
            return []
        if strike_committed_this_round(context):
            return []

        def use(s):
            card_b_available["value"] = False
            commit_strike_for_round(
                context,
                hooks.HookOption(
                    choice=Choice("card_b:strike", "Card B's bundled strike"),
                    apply=lambda s: StrikeDamage(amount=2),
                ),
            )

        return [hooks.HookOption(choice=Choice("card_b:maneuver", "Card B"), apply=use)]

    hooks.register(MANEUVER_HOOK, provide_card_a)
    hooks.register(MANEUVER_HOOK, provide_card_b)
    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "card_a:maneuver")  # turn 1: commits via card A
    # Turn 3 would offer card B too, if its own gate were missing -- it is
    # not scripted here, so an unexpected offer fails the test loudly.
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").wounded is True  # took card A's committed 2 damage
    assert card_b_available["value"] is True  # card B was never claimed
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_commit_strike_for_round_raises_if_already_committed():
    """Backstop (module docstring's "Maneuver bundled with a strike"
    section): `commit_strike_for_round` must refuse, not silently overwrite,
    a second commitment for the same vampire in the same round -- in case a
    provider's own `strike_committed_this_round` offer-time gate (proven
    above) is ever skipped by a future card module's bug. Also exercises
    `strike_committed_this_round` directly, without going through
    `run_combat`."""
    round_state: dict = {}
    context = {"vampire": "v1", ROUND_STATE_CONTEXT_KEY: round_state}
    first = hooks.HookOption(choice=Choice("first:strike", "First"), apply=lambda s: 1)
    second = hooks.HookOption(choice=Choice("second:strike", "Second"), apply=lambda s: 2)

    assert strike_committed_this_round(context) is False
    commit_strike_for_round(context, first)
    assert strike_committed_this_round(context) is True
    with pytest.raises(ValueError, match="already has a committed strike"):
        commit_strike_for_round(context, second)


def test_commit_strike_for_round_raises_on_builtin_choice_value_collision():
    """A committed strike's own `choice.value` must never collide with a
    built-in strike choice (`HAND_STRIKE_VALUE`/`NO_STRIKE_VALUE`) -- a
    collision would silently mis-resolve `_resolve_one_strike`'s own
    `if choice == ...` branching onto the wrong, built-in effect instead of
    the intended committed one. Enforced here as a hard failure rather than
    left to docstring convention alone."""
    context = {"vampire": "v1", ROUND_STATE_CONTEXT_KEY: {}}
    colliding = hooks.HookOption(
        choice=Choice(HAND_STRIKE_VALUE, "Collides with the built-in hand strike"),
        apply=lambda s: 1,
    )
    with pytest.raises(ValueError, match="collides with a built-in strike choice"):
        commit_strike_for_round(context, colliding)
