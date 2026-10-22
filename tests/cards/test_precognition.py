"""Precognition (krcg id 101475, `src/vtesbot/cards/precognition.py`).

Card text: "[aus] +1 intercept. [AUS] As above, and this vampire can
prevent 1 damage during the first round of the resulting combat if they
block."

One assertion per clause/qualifier/ruling: the basic "+1 intercept" offered
to any ready, unlocked Auspex vampire (no "is this the current block
candidate" check, mirroring `second_tradition_domain.py`'s own clause-1
precedent); the superior clause additionally recording a block-time combat
grant for *that* vampire; the §8 "a minion cannot play the same reaction
card more than once during a single action" cap shared across both
clauses; the damage-prevention half's own three gates (round 1 only
[LSJ 20010813]/[LSJ 20010819-2], the grant must exist, and `block.=True`
i.e. this vampire ended up the blocker -- proven by the grant simply never
reaching a different blocker); and a full end-to-end run through
`perform_minion_action` reproducing the engine's own two new primitives
(ENG-040, resolved).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.precognition import GRANT_NAME, KRCG_ID, USED_BY_KEY
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, perform_minion_action
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK

NAME = "Precognition"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _offer_intercept(game, *, defender, actor, pending=None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        blocking_vampire=None,
        pending=pending,
    )


def _offer_prevention(game, *, player, vampire, damage, round_state=None, combat_state=None):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player=player,
        vampire=vampire,
        damage=damage,
        round_state=round_state,
        combat_state=combat_state,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "[aus] +1 intercept." / "[AUS] As above, ..." --------------------------


def test_intercept_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, disciplines=("aus",))
    game = builder.build()

    assert _offer_intercept(game, defender="P2", actor="P1") == []


def test_intercept_not_offered_for_a_non_auspex_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_intercept(game, defender="P2", actor="P1") == []


def test_intercept_not_offered_for_a_locked_auspex_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",), locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_intercept(game, defender="P2", actor="P1") == []


def test_basic_auspex_is_offered_only_the_basic_option():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert {o.choice.value for o in options} == {"precognition:basic:D1"}

    delta = options[0].apply(game.state)
    assert delta == 1
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_superior_auspex_is_offered_both_options():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", actor="P1")
    assert {o.choice.value for o in options} == {
        "precognition:basic:D1",
        "precognition:superior:D1",
    }


def test_basic_option_records_no_block_time_grant():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    options = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    next(o for o in options if o.choice.value == "precognition:basic:D1").apply(game.state)

    assert "block_time_combat_grants" not in pending


def test_superior_option_records_a_block_time_grant_for_that_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    options = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    delta = next(o for o in options if o.choice.value == "precognition:superior:D1").apply(
        game.state
    )

    assert delta == 1
    assert pending["block_time_combat_grants"]["D1"][GRANT_NAME] == 1


def test_not_offered_a_second_time_by_the_same_vampire_this_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",)
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    next(o for o in first if o.choice.value == "precognition:basic:D1").apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    second = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert second == []  # D1 already played this card once this action.


def test_a_second_eligible_vampire_can_still_use_their_own_copy():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, blood=0, disciplines=("aus",))
        .ready_vampire("D2", capacity=3, blood=0, disciplines=("aus",))
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    next(o for o in first if o.choice.value == "precognition:basic:D1").apply(game.state)

    second = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert {o.choice.value for o in second} == {"precognition:basic:D2"}


# --- "this vampire can prevent 1 damage during the first round of the
# resulting combat if they block." ------------------------------------------


def _one_vampire_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    return builder.build()


def test_prevention_not_offered_without_round_state_at_all():
    game = _one_vampire_game()
    options = _offer_prevention(
        game, player="P1", vampire="D1", damage={"normal": 1, "aggravated": 0}, round_state=None
    )
    assert options == []


def test_prevention_not_offered_outside_round_one():
    """[LSJ 20010819-2]: "does not carry over to a follow-up combat" -- here
    modeled as round 2 of the very same combat, the sharpest version of the
    same underlying gate."""
    game = _one_vampire_game()
    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    options = _offer_prevention(
        game,
        player="P1",
        vampire="D1",
        damage={"normal": 1, "aggravated": 0},
        round_state={"round_number": 2},
        combat_state=combat_state,
    )
    assert options == []


def test_prevention_not_offered_without_a_recorded_grant():
    """[LSJ 20010813]: only if the block was successful for *this* vampire."""
    game = _one_vampire_game()
    options = _offer_prevention(
        game,
        player="P1",
        vampire="D1",
        damage={"normal": 1, "aggravated": 0},
        round_state={"round_number": 1},
        combat_state={},
    )
    assert options == []


def test_prevention_not_offered_with_no_damage_to_prevent():
    game = _one_vampire_game()
    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    options = _offer_prevention(
        game,
        player="P1",
        vampire="D1",
        damage={"normal": 0, "aggravated": 0},
        round_state={"round_number": 1},
        combat_state=combat_state,
    )
    assert options == []


def test_prevention_reduces_normal_damage_and_consumes_the_grant():
    game = _one_vampire_game()
    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    damage = {"normal": 1, "aggravated": 0}
    options = _offer_prevention(
        game,
        player="P1",
        vampire="D1",
        damage=damage,
        round_state={"round_number": 1},
        combat_state=combat_state,
    )
    assert {o.choice.value for o in options} == {"precognition:prevent"}

    options[0].apply(game.state)
    assert damage["normal"] == 0
    assert combat_state["block_time_combat_grants"]["D1"][GRANT_NAME] == 0


def test_prevention_reduces_aggravated_damage_when_that_is_what_is_dealt():
    game = _one_vampire_game()
    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    damage = {"normal": 0, "aggravated": 1}
    options = _offer_prevention(
        game,
        player="P1",
        vampire="D1",
        damage=damage,
        round_state={"round_number": 1},
        combat_state=combat_state,
    )
    options[0].apply(game.state)
    assert damage["aggravated"] == 0


def test_prevention_raises_if_both_damage_types_are_simultaneously_positive():
    """Engine invariant (mirrors `cards/rolling_with_the_punches.py`'s own
    precedent): no production call site produces this; surfaced loudly."""
    import pytest

    game = _one_vampire_game()
    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    with pytest.raises(AssertionError):
        _offer_prevention(
            game,
            player="P1",
            vampire="D1",
            damage={"normal": 1, "aggravated": 1},
            round_state={"round_number": 1},
            combat_state=combat_state,
        )


# --- End to end, through `perform_minion_action` ---------------------------


def test_end_to_end_superior_clause_prevents_round_one_damage_if_it_blocks():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=10, blood=5)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=10, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()
    acting = game.vampire("A1")

    def resolve(pending):
        del pending
        raise AssertionError("must not resolve unblocked: the attempt succeeds")

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "precognition:superior:D1")
    defender.expect("strike_choice", "no_strike")
    defender.expect(DAMAGE_PREVENTION_HOOK, "precognition:prevent")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=1, resolve=resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is False  # prevented
    assert game.state.players["P2"].hand == []


def test_end_to_end_a_failed_attempt_still_records_the_grant_but_never_reaches_combat():
    """The reacting vampire's own attempt can still fail overall (its own
    +1 is not enough): the grant is written into `pending` the moment the
    card is played, but `perform_minion_action` only ever forwards it for
    whichever vampire ends up the successful `blocker` -- here, nobody, so
    the action resolves unblocked and `resolve()` runs instead. The
    low-level `_offer_prevention` tests above already prove the forwarding
    side reads the grant keyed by the specific blocking vampire; this proves
    a failed attempt never reaches that forwarding step at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=10, blood=5)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=10, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()
    acting = game.vampire("A1")

    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "precognition:superior:D1")  # 0+1=1 < stealth 2
    defender.expect("block_attempt", "decline")  # no more options; D1 already used its own copy
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=2, resolve=resolve)

    assert resolve_calls == [True]  # unblocked: the reaction was not enough
    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").zone == "ready"
    assert game.vampire("D1").locked is False  # failed attempt: never locks
    assert game.state.players["P2"].hand == []  # the card was still played and spent
