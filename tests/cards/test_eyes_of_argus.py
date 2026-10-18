"""Eyes of Argus (krcg id 100680, `src/vtesbot/cards/eyes_of_argus.py`).

Card text: "[aus] Only usable during an action directed at you (or a card
you control). +2 intercept.\n[AUS] Only usable by a locked vampire. This
vampire wakes (they ignore the requirement to be unlocked for playing
reaction cards and attempting to block until the end of the action)."

One assertion per clause/qualifier/ruling: the basic clause's own
"directed at you" gate (offered for a directed action, withheld for an
undirected one), basic-vs-superior Auspex eligibility, +2 intercept;
the superior clause's wake mechanism through the real `attempt_block` call
site (an ordinary, contestable block, not an unconditional success), gated
on superior Auspex and "only usable by a locked vampire"; [TOM 19951129]
("need not attempt to block ... merely an option" -- declining after
waking); the shared "cannot play the same reaction card twice in one
action" cap across both clauses.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.eyes_of_argus import KRCG_ID, USED_BY_KEY
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, WAKE_LOCKED_MINION_HOOK, attempt_block

NAME = "Eyes of Argus"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _offer_intercept(game, *, defender, actor="P1", directed=True, pending=None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        blocking_vampire=None,
        directed=directed,
        pending=pending,
    )


def _offer_wake(game, *, defender, actor="P1", pending=None):
    return hooks.offer(
        WAKE_LOCKED_MINION_HOOK,
        game.state,
        player=defender,
        actor=actor,
        defender=defender,
        acting_vampire=None,
        action=None,
        directed=None,
        base_stealth=0,
        pending=pending,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "[aus] Only usable during an action directed at you (or a card you
# control). +2 intercept." ---------------------------------------------------


def test_intercept_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0, disciplines=("aus",))
    game = builder.build()

    assert _offer_intercept(game, defender="P2") == []


def test_intercept_not_offered_for_a_non_auspex_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_intercept(game, defender="P2") == []


def test_intercept_not_offered_for_a_locked_auspex_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",), locked=True
    )
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_intercept(game, defender="P2") == []


def test_intercept_not_offered_for_an_undirected_action():
    """"Only usable during an action directed at you (or a card you
    control)." -- an undirected action (e.g. hunt) never offers this
    clause at all, regardless of eligibility."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",)
    )
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_intercept(game, defender="P2", directed=False) == []
    assert _offer_intercept(game, defender="P2", directed=None) == []


def test_basic_auspex_offered_the_bonus_for_a_directed_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", directed=True)
    assert {o.choice.value for o in options} == {"eyes_of_argus:basic:D1"}

    delta = options[0].apply(game.state)
    assert delta == 2
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_superior_auspex_also_offered_the_basic_intercept_bonus():
    """Superior Auspex still only grants the "+2 intercept" clause through
    `INTERCEPT_MODIFIER_HOOK` -- the superior effect is a different mode of
    the same card (the wake clause below), not an additional bonus."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_intercept(game, defender="P2", directed=True)
    assert {o.choice.value for o in options} == {"eyes_of_argus:basic:D1"}


def test_not_offered_again_by_the_same_vampire_this_action_intercept():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, blood=0, disciplines=("aus",)
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_intercept(game, defender="P2", directed=True, pending=pending)
    next(o for o in first if o.choice.value == "eyes_of_argus:basic:D1").apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    second = _offer_intercept(game, defender="P2", directed=True, pending=pending)
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
    first = _offer_intercept(game, defender="P2", directed=True, pending=pending)
    next(o for o in first if o.choice.value == "eyes_of_argus:basic:D1").apply(game.state)

    second = _offer_intercept(game, defender="P2", directed=True, pending=pending)
    assert {o.choice.value for o in second} == {"eyes_of_argus:basic:D2"}


# --- "[AUS] Only usable by a locked vampire. This vampire wakes (...)." ----


def test_wake_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_wake_not_offered_for_an_unlocked_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(  # unlocked.
        "D1", capacity=3, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_wake_not_offered_for_a_basic_auspex_vampire():
    """Only superior Auspex ("[AUS]") unlocks the wake clause -- basic
    Auspex ("[aus]") only ever grants the intercept clause above."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("aus",)
    )
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_wake_offered_for_a_locked_superior_auspex_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_wake(game, defender="P2")
    assert {o.choice.value for o in options} == {"eyes_of_argus:superior:D1"}


def test_an_already_woken_vampire_is_not_reoffered_for_wake():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()
    game.vampire("D1").woken = True

    assert _offer_wake(game, defender="P2") == []


def test_not_offered_again_by_the_same_vampire_this_action_wake():
    """The shared `USED_BY_KEY` cap applies across both clauses: once a
    vampire has used the wake clause this action, it cannot use it again
    with a second physical copy."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    pending: dict = {}
    first = _offer_wake(game, defender="P2", pending=pending)
    first[0].apply(game.state)
    assert "D1" in pending[USED_BY_KEY]

    game.vampire("D1").woken = False  # a later action's own clear_woken_vampires.
    game.vampire("D1").locked = True
    second = _offer_wake(game, defender="P2", pending=pending)
    assert second == []


def test_wake_through_attempt_block_is_an_ordinary_contestable_block():
    """[TOM 19951129]: waking D1 does not itself guarantee a successful
    block -- against `base_stealth=0` (intercept baseline 0) the attempt
    succeeds only because intercept also starts at 0, not because waking is
    an unconditional success."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect(WAKE_LOCKED_MINION_HOOK, "eyes_of_argus:superior:D1")
    defender.expect("block_attempt", "block_with:D1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "D1"
    assert game.vampire("D1").locked is True  # "while remaining structurally locked".
    assert game.vampire("D1").woken is True
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]
    defender.assert_exhausted()


def test_wake_need_not_attempt_to_block_tom_ruling():
    """[TOM 19951129]: "The minion need not attempt to block nor play
    further reaction cards: that is merely an option." Waking D1 against a
    higher stealth (base_stealth=1, intercept baseline 0) fails, and the
    defender may simply decline further attempts."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "D1", capacity=3, locked=True, disciplines=("AUS",)
    )
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect(WAKE_LOCKED_MINION_HOOK, "eyes_of_argus:superior:D1")
    defender.expect("block_attempt", "block_with:D1")
    # Retry: D1 is already woken, so the hook offers nothing and no second
    # wake decision is raised.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert game.vampire("D1").woken is True  # still woken: can play further reaction cards.
    defender.assert_exhausted()
