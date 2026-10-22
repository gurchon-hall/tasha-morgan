"""Diana Iadanza (krcg id 201694, `src/vtesbot/cards/diana_iadanza.py`).

Card text: "Camarilla Toreador Justicar: During a referendum she calls,
Diana can burn 1 blood to cancel a reaction card as it is played (cost is
still paid). +1 bleed."

Clause 2 ("+1 bleed") tests are scenario tests against the real
`BLEED_AMOUNT_FIXED_MODIFIER_HOOK` machinery (`engine/phases/minion.py::
_perform_bleed`), not a fake provider. Clause 1 (cancel-as-played) has no
live `POLLING_STEP_HOOK` provider offering a Reaction-type option anywhere
in the pool yet (module docstring), so its tests drive a real
`resolve_referendum` call (bypassing the block-attempt step, same pattern
as `tests/rules/test_politics.py::
test_a_forced_abstain_source_is_excluded_from_casting_end_to_end`) with a
temporary fake `POLLING_STEP_HOOK` provider standing in for a genuine
Reaction card, mirroring `tests/rules/test_hooks.py`'s own ENG-023 proof
(`test_cancel_context_carries_the_canceled_options_played_card_type`/
`test_a_reaction_only_canceler_cannot_reach_a_non_card_play_option`).

One assertion per clause/ruling: registry status, the +1 bleed bonus for
Diana herself bleeding (and its absence for a different vampire's bleed or
the opposing Methuselah's own bleed), the Reaction-only gate, the
Diana-must-be-the-caller gate, the once-per-referendum cap (Rulebook §3
"During X, do Y"), the exact 1-blood cost, and the no-blood-no-offer gate.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.diana_iadanza import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.politics import POLLING_STEP_HOOK, resolve_referendum


def _make_diana(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Diana's real printed
    identity (`CryptCard` is frozen, mirrors `test_carmelita_neillson.py::
    _make_carmelita`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Diana Iadanza",
        capacity=9,
        group=7,
        clan="Toreador",
        title="Justicar",
        disciplines=("aus", "cel", "for", "pre"),
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.blocked_reason is None
    assert reg.name == "Diana Iadanza"


def test_plus_1_bleed_when_diana_herself_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=1)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Diana1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base bleed 1 + Diana's own +1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bonus_when_a_different_vampire_bleeds_for_the_same_controller():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=1, locked=True)  # already acted this turn
    _make_diana(p1, "Diana1")
    p1.ready_vampire("Other1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Other1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only, Diana did not act
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bonus_for_the_opposing_methuselahs_own_bleed():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("Other1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Diana1", capacity=9, blood=1)  # not acting; just defending/blocking
    _make_diana(p2, "Diana1")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Other1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    # Diana belongs to the defending Methuselah here, not the bleeder: her
    # own "+1 bleed" is scoped to a bleed she herself performs, never one
    # performed against her.
    assert game.pool_of("P2") == 29
    actor.assert_exhausted()
    defender.assert_exhausted()


# -- "During a referendum she calls, Diana can burn 1 blood to cancel a --
# -- reaction card as it is played (cost is still paid)." (clause 1) -------


def _one_shot_card_play_provider(
    target_player: str, choice_value: str, played: list[str], *, card_type: str | None
):
    """A throwaway `POLLING_STEP_HOOK` provider standing in for a real
    card/ability play, one-shot like a real card (`cost` marks it used
    immediately, regardless of cancellation, mirroring `tests/rules/
    test_hooks.py::test_apply_chosen_option_is_offered_to_the_non_acting_
    side_in_an_impulse_window`'s own fake). `played` records whether the
    option's own `apply` actually ran (suppressed if canceled)."""
    used = [False]

    def provider(state, context):
        if context.get("player") != target_player or context.get("phase") != "before_cast":
            return []
        if used[0]:
            return []

        def _cost(s):
            used[0] = True

        def _apply(s):
            played.append(choice_value)

        return [
            hooks.HookOption(
                choice=Choice(choice_value, f"Fake card play ({choice_value})"),
                cost=_cost,
                apply=_apply,
                played_card_type=card_type,
            )
        ]

    return provider


def test_cancels_a_reaction_card_played_in_the_polling_step_window():
    """A genuine Reaction-card play (`played_card_type == "Reaction"`)
    reachable in Diana's own referendum's pre-cast polling-step window is
    canceled: its own effect never runs (`apply_chosen_option`, ENG-022),
    and Diana burns exactly 1 blood."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=2)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30)
    game = builder.build()
    played: list[str] = []
    provider = _one_shot_card_play_provider("P2", "play_reaction", played, card_type="Reaction")
    hooks.register(POLLING_STEP_HOOK, provider)
    try:
        actor = ScriptedAgent("P1")
        actor.expect(hooks.CANCEL_AS_PLAYED_HOOK, "diana_iadanza_cancel:Diana1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")
        defender.expect(POLLING_STEP_HOOK, "play_reaction")
        game.state.agents["P2"] = defender

        resolve_referendum(game.state, "P1", "P2", game.vampire("Diana1"))

        assert played == []  # the canceled option's own effect was suppressed
        assert game.blood_of("Diana1") == 1  # exactly 1 blood burned
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(POLLING_STEP_HOOK, provider)


def test_does_not_cancel_a_non_reaction_option_in_the_same_window():
    """Diana cancels only a Reaction card -- a non-Reaction option
    reachable in the same window (the shape Modius's/Oxford University,
    England's own abilities use: `played_card_type` left at its default
    `None`) is never offered a cancellation at all, matching `tests/rules/
    test_hooks.py::test_a_reaction_only_canceler_cannot_reach_a_non_card_
    play_option`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=2)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30)
    game = builder.build()
    played: list[str] = []
    provider = _one_shot_card_play_provider("P2", "use_ability", played, card_type=None)
    hooks.register(POLLING_STEP_HOOK, provider)
    try:
        actor = ScriptedAgent("P1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")  # never asked CANCEL_AS_PLAYED_HOOK: not a Reaction card
        defender.expect(POLLING_STEP_HOOK, "use_ability")
        game.state.agents["P2"] = defender

        resolve_referendum(game.state, "P1", "P2", game.vampire("Diana1"))

        assert played == ["use_ability"]  # not suppressed: no legal cancellation was offered
        assert game.blood_of("Diana1") == 2  # Diana never acted
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(POLLING_STEP_HOOK, provider)


def test_only_usable_once_per_referendum():
    """Rulebook §3 "Wording templates" > "During X, do Y", verbatim:
    "only one Y can be done per X with this card" -- a second Reaction-card
    play later in the *same* referendum is not cancelable again, even
    though Diana still has blood to spare (not a blood-scarcity gate)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=3)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30)
    game = builder.build()
    played: list[str] = []
    provider_a = _one_shot_card_play_provider("P2", "play_reaction_a", played, card_type="Reaction")
    provider_b = _one_shot_card_play_provider("P2", "play_reaction_b", played, card_type="Reaction")
    hooks.register(POLLING_STEP_HOOK, provider_a)
    hooks.register(POLLING_STEP_HOOK, provider_b)
    try:
        actor = ScriptedAgent("P1")
        actor.expect(hooks.CANCEL_AS_PLAYED_HOOK, "diana_iadanza_cancel:Diana1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")
        defender.expect(POLLING_STEP_HOOK, "play_reaction_a")
        defender.expect(POLLING_STEP_HOOK, "play_reaction_b")
        game.state.agents["P2"] = defender

        resolve_referendum(game.state, "P1", "P2", game.vampire("Diana1"))

        assert played == ["play_reaction_b"]  # "a" was canceled; "b" could not be (cap spent)
        assert game.blood_of("Diana1") == 2  # exactly one burn, not two
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(POLLING_STEP_HOOK, provider_a)
        hooks.unregister(POLLING_STEP_HOOK, provider_b)


def test_not_usable_if_the_referendum_was_not_called_by_diana_herself():
    """ "During a referendum **she** calls" -- not any referendum her
    controller happens to call, even with another titled vampire of
    their own."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=2)
    _make_diana(p1, "Diana1")
    p1.ready_vampire("OtherCaller", capacity=4, blood=1, title="Primogen")
    builder.player("P2", pool=30)
    game = builder.build()
    played: list[str] = []
    provider = _one_shot_card_play_provider("P2", "play_reaction", played, card_type="Reaction")
    hooks.register(POLLING_STEP_HOOK, provider)
    try:
        actor = ScriptedAgent("P1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")  # never asked: Diana herself did not call this referendum
        defender.expect(POLLING_STEP_HOOK, "play_reaction")
        game.state.agents["P2"] = defender

        resolve_referendum(game.state, "P1", "P2", game.vampire("OtherCaller"))

        assert played == ["play_reaction"]  # not canceled
        assert game.blood_of("Diana1") == 2  # Diana never acted
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(POLLING_STEP_HOOK, provider)


def test_not_offered_if_diana_has_0_blood():
    """The ability costs blood she doesn't have to burn is illegal to
    offer: with 0 blood, Diana is never offered the cancellation at all."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=0)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30)
    game = builder.build()
    played: list[str] = []
    provider = _one_shot_card_play_provider("P2", "play_reaction", played, card_type="Reaction")
    hooks.register(POLLING_STEP_HOOK, provider)
    try:
        actor = ScriptedAgent("P1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")  # never asked: Diana has no blood to burn
        defender.expect(POLLING_STEP_HOOK, "play_reaction")
        game.state.agents["P2"] = defender

        resolve_referendum(game.state, "P1", "P2", game.vampire("Diana1"))

        assert played == ["play_reaction"]  # not canceled
        assert game.blood_of("Diana1") == 0
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(POLLING_STEP_HOOK, provider)
