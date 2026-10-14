"""On the Qui Vive (krcg id 101321, `src/vtesbot/cards/on_the_qui_vive.py`).

Card text: "Only usable by a locked minion. A minion can play only one On
the Qui Vive between their unlock phases.\nThis minion wakes (they ignore
the requirement to be unlocked for playing reaction cards and attempting
to block until the end of the action). If this minion is an ally, they
do not unlock as normal during their next unlock phase."

One assertion per clause/qualifier/ruling: "Only usable by a locked
minion" (not offered for an unlocked or torpid vampire); "A minion can
play only one On the Qui Vive between their unlock phases" (excluded
within the same action, across a later action before the next unlock
phase, and re-eligible after `unlock_phase` runs); the primary wake
effect through the real `attempt_block` call site (an ordinary,
stealth/intercept-subject block, not an unconditional success, while
`locked` stays `True`); [TOM 19951129] ("need not attempt to block...
merely an option" -- declining after waking); an already-`woken`
candidate is not re-offered (OQ-48's own flagged exclusion); the
deliberate scope decision not to target a locked ally (module
docstring).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.on_the_qui_vive import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import WAKE_LOCKED_MINION_HOOK, attempt_block
from vtesbot.engine.allies import recruit_ally
from vtesbot.engine.phases.unlock import unlock_phase

NAME = "On the Qui Vive"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _offer_wake(game, *, defender, actor="P1", pending=None, base_stealth=0):
    return hooks.offer(
        WAKE_LOCKED_MINION_HOOK,
        game.state,
        player=defender,
        actor=actor,
        defender=defender,
        acting_vampire=None,
        action=None,
        directed=None,
        base_stealth=base_stealth,
        pending=pending,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Only usable by a locked minion" ---------------------------------------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_not_offered_for_an_unlocked_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3)  # unlocked.
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_not_offered_for_a_torpid_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).torpid_vampire("D1", capacity=3)
    p2.hand.append(_card())
    game = builder.build()

    assert _offer_wake(game, defender="P2") == []


def test_offered_for_a_locked_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    game = builder.build()

    options = _offer_wake(game, defender="P2")
    assert {o.choice.value for o in options} == {"on_the_qui_vive:D1"}


# --- primary clause: the wake effect, through the real attempt_block site --


def test_waking_through_attempt_block_is_an_ordinary_contestable_block():
    """`base_stealth=0` succeeds only because intercept's own baseline is
    also 0 -- not an unconditional success, unlike Second Tradition:
    Domain/Organized Resistance's own `BLOCK_CANDIDATE_INJECTION_HOOK`
    shape."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("wake_locked_minion", "on_the_qui_vive:D1")
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


def test_waking_fails_to_block_against_higher_stealth_tom_ruling():
    """[TOM 19951129]: "The minion need not attempt to block nor play
    further reaction cards: that is merely an option." Waking D1 does not
    itself guarantee a successful block -- against `base_stealth=1`
    (intercept hardcoded 0) the attempt fails and the defender may simply
    decline further attempts."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    game = builder.build()

    defender = ScriptedAgent("P2")
    defender.expect("wake_locked_minion", "on_the_qui_vive:D1")
    defender.expect("block_attempt", "block_with:D1")
    # Retry: D1 is already woken, so the hook offers nothing (OQ-48's own
    # exclusion) and no second "wake_locked_minion" decision is raised.
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert game.vampire("D1").woken is True  # still woken: can play further reaction cards.
    defender.assert_exhausted()


def test_an_already_woken_vampire_is_not_reoffered():
    """OQ-48's own flagged exclusion: the engine does nothing to stop this
    hook being re-offered for an already-`woken` candidate on a retry --
    this module's own provider must guard it."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    game = builder.build()
    game.vampire("D1").woken = True

    assert _offer_wake(game, defender="P2") == []


# --- "A minion can play only one On the Qui Vive between their unlock
# phases" ---------------------------------------------------------------


def test_not_offered_again_by_the_same_vampire_this_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    p2.hand.append(_card())  # a second physical copy -- still the same vampire, though.
    game = builder.build()

    first = _offer_wake(game, defender="P2")
    first[0].apply(game.state)
    assert game.vampire("D1").qui_vive_played_since_unlock is True

    # clear_woken_vampires would normally run at the end of the action; model
    # that in isolation here to confirm the *between-unlock-phases* cap (not
    # merely the already-woken exclusion) is what blocks a second play.
    game.vampire("D1").woken = False
    game.vampire("D1").locked = True

    second = _offer_wake(game, defender="P2")
    assert second == []


def test_cap_persists_across_a_later_action_before_the_next_unlock_phase():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    _offer_wake(game, defender="P2")[0].apply(game.state)
    game.vampire("D1").woken = False  # a later, separate action's own clear_woken_vampires.
    game.vampire("D1").locked = True

    assert _offer_wake(game, defender="P2") == []  # still within the same unlock-phase window.


def test_cap_clears_on_the_vampires_own_controllers_next_unlock_phase():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, locked=True)
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    _offer_wake(game, defender="P2")[0].apply(game.state)
    game.vampire("D1").woken = False
    game.vampire("D1").locked = True
    assert _offer_wake(game, defender="P2") == []

    unlock_phase(game.state, "P2")
    assert game.vampire("D1").qui_vive_played_since_unlock is False
    # `unlock_phase` also unlocks D1 itself (it was ready) -- re-lock it here
    # (modeling a later action) to isolate the cap clearing from that
    # separate, expected "no longer locked" effect.
    game.vampire("D1").locked = True

    options = _offer_wake(game, defender="P2")
    assert {o.choice.value for o in options} == {"on_the_qui_vive:D1"}


def test_a_second_distinct_eligible_vampire_is_unaffected_by_the_cap():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = (
        builder.player("P2", pool=30)
        .ready_vampire("D1", capacity=3, locked=True)
        .ready_vampire("D2", capacity=3, locked=True)
    )
    p2.hand.append(_card())
    p2.hand.append(_card())
    game = builder.build()

    first = _offer_wake(game, defender="P2")
    next(o for o in first if o.choice.value == "on_the_qui_vive:D1").apply(game.state)

    second = _offer_wake(game, defender="P2")
    assert {o.choice.value for o in second} == {"on_the_qui_vive:D2"}


# --- ally footnote: deliberately out of scope (module docstring) -----------


def test_not_offered_for_a_locked_ally():
    """Allies are never offered as block candidates and never play reaction
    cards in this engine (OQ-46's own out-of-scope note) -- this module's
    own provider never targets one, a deliberate scope decision, not a
    silently dropped clause (see its own module docstring)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.hand.append(_card())
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=1, name="Some Ally", life=1)
    assert ally.locked is True

    assert _offer_wake(game, defender="P2") == []
