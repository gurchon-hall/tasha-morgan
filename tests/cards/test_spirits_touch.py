"""Spirit's Touch (krcg id 101850, `src/vtesbot/cards/spirits_touch.py`).

Card text: "[aus] +1 intercept. [AUS] As above, with 1 optional maneuver
during the resulting combat if this vampire blocks."

One assertion per clause/qualifier/ruling: the basic "+1 intercept" offered
to any ready, unlocked Auspex vampire (no "is this the current block
candidate" check, mirroring `precognition.py`'s own basic clause); the
superior clause additionally recording a block-time combat grant for
*that* vampire; the §8 "a minion cannot play the same reaction card more
than once during a single action" cap shared across both clauses; the
maneuver half's own two gates (the grant must exist, and it is keyed to
the vampire that ended up the blocker -- proven by the grant simply never
reaching a different blocker, and by never surviving into a second,
separate combat [LSJ 20010819-2]); and a full end-to-end run through
`perform_minion_action` reproducing the engine's own block-time-combat-
grant primitive wired to `MANEUVER_HOOK` instead of `DAMAGE_PREVENTION_
HOOK`.

[LSJ 20010814-2] ("provided again if a second block happens on the same
action") is not reachable by any mechanism implemented in this project
today (no Form-of-Mist-like "dissolved blocker triggers a new attempt"
effect) -- not exercised here, same latitude `precognition.py`'s own test
file takes for its sibling ruling.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.spirits_touch import GRANT_NAME, KRCG_ID, USED_BY_KEY
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, perform_minion_action
from vtesbot.engine.combat import MANEUVER_HOOK, run_combat, seed_block_time_combat_grants

NAME = "Spirit's Touch"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _offer_intercept(game, *, defender, actor="P1", pending=None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        defender=defender,
        acting_vampire=None,
        action=None,
        directed=None,
        stealth=1,
        intercept=0,
        blocking_vampire=None,
        pending=pending,
    )


def _offer_maneuver(game, *, player, vampire, combat_state=None):
    return hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player=player,
        vampire=vampire,
        opponent=None,
        combat_state=combat_state,
        round_state={},
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
    assert {o.choice.value for o in options} == {"spirits_touch:basic:D1"}

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
        "spirits_touch:basic:D1",
        "spirits_touch:superior:D1",
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
    next(o for o in options if o.choice.value == "spirits_touch:basic:D1").apply(game.state)

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
    delta = next(o for o in options if o.choice.value == "spirits_touch:superior:D1").apply(
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
    next(o for o in first if o.choice.value == "spirits_touch:basic:D1").apply(game.state)
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
    next(o for o in first if o.choice.value == "spirits_touch:basic:D1").apply(game.state)

    second = _offer_intercept(game, defender="P2", actor="P1", pending=pending)
    assert {o.choice.value for o in second} == {"spirits_touch:basic:D2"}


# --- "1 optional maneuver during the resulting combat if this vampire
# blocks." ---------------------------------------------------------------


def test_maneuver_not_offered_without_combat_state_at_all():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer_maneuver(game, player="P1", vampire="D1", combat_state=None) == []


def test_maneuver_not_offered_without_a_recorded_grant():
    """[LSJ 20010813]: only if the block was successful for *this* vampire."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer_maneuver(game, player="P1", vampire="D1", combat_state={}) == []


def test_maneuver_offered_and_consumes_the_grant():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    options = _offer_maneuver(game, player="P1", vampire="D1", combat_state=combat_state)
    assert {o.choice.value for o in options} == {"spirits_touch:maneuver"}

    options[0].apply(game.state)
    assert combat_state["block_time_combat_grants"]["D1"][GRANT_NAME] == 0


def test_maneuver_does_not_carry_over_to_a_separate_follow_up_combat():
    """[LSJ 20010819-2]: a second, separate `run_combat` call (modeling a
    follow-up combat such as Psyche!) gets its own fresh `combat_state` and
    never receives the grant recorded for the first, resulting combat."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    first_combat_state = {"block_time_combat_grants": {"D1": {GRANT_NAME: 1}}}
    follow_up_combat_state: dict = {}

    assert _offer_maneuver(game, player="P1", vampire="D1", combat_state=first_combat_state) != []
    assert (
        _offer_maneuver(game, player="P1", vampire="D1", combat_state=follow_up_combat_state) == []
    )


# --- End to end, through `perform_minion_action` ---------------------------


def test_end_to_end_superior_clause_grants_a_maneuver_if_it_blocks():
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
    defender.expect(INTERCEPT_MODIFIER_HOOK, "spirits_touch:superior:D1")
    defender.expect("maneuver_choice", "spirits_touch:maneuver")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=1, resolve=resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.state.players["P2"].hand == []


def test_end_to_end_a_failed_attempt_still_records_the_grant_but_never_reaches_combat():
    """The reacting vampire's own attempt can still fail overall (its own
    +1 is not enough): the grant is written into `pending` the moment the
    card is played, but `perform_minion_action` only ever forwards it for
    whichever vampire ends up the successful `blocker` -- here, nobody, so
    the action resolves unblocked and `resolve()` runs instead."""
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
    defender.expect(INTERCEPT_MODIFIER_HOOK, "spirits_touch:superior:D1")  # 0+1=1 < stealth 2
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


def test_end_to_end_grant_does_not_survive_a_second_run_combat_call():
    """Direct companion to the follow-up-combat scenario test above, driven
    through the real primitives `perform_minion_action` uses
    (`seed_block_time_combat_grants`/`run_combat`): a grant seeded for one
    `run_combat` call is gone by the time a second, independent call runs,
    even for the same vampire."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=10, blood=5)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=10, blood=0)
    game = builder.build()

    seed = seed_block_time_combat_grants({"D1": {GRANT_NAME: 1}})
    actor = ScriptedAgent("P1")
    # A1 is never asked a "maneuver_choice" at all: it holds no grant, so
    # `MANEUVER_HOOK` offers it nothing and `_ask_maneuver` auto-declines
    # without raising a `Decision` (`engine/action.py::_ask_maneuver`).
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("maneuver_choice", "spirits_touch:maneuver")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("A1"), "P2", game.vampire("D1"), seed)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert seed["block_time_combat_grants"]["D1"][GRANT_NAME] == 0  # consumed

    # A second, independent run_combat call (follow-up combat): no grant
    # seeded, so neither side is ever asked a "maneuver_choice" either.
    actor2 = ScriptedAgent("P1")
    actor2.expect("strike_choice", "no_strike")
    actor2.expect("press", "end_combat")
    defender2 = ScriptedAgent("P2")
    defender2.expect("strike_choice", "no_strike")
    defender2.expect("press", "end_combat")
    game.state.agents["P1"] = actor2
    game.state.agents["P2"] = defender2

    run_combat(game.state, "P1", game.vampire("A1"), "P2", game.vampire("D1"))

    actor2.assert_exhausted()
    defender2.assert_exhausted()
