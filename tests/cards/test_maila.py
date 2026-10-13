"""Maila (krcg id 201633, `src/vtesbot/cards/maila.py`).

Card text: "Camarilla primogen: If Maila is ready during your turn, you can
discard a political action card to give a minion you control +1 stealth
for the current action." Ruling: "Her ability can only be used once during
each of your turns. [RBK wording-templates] [ANK 20230122]."

One assertion per clause/ruling: the registry entry; the +1 stealth effect
proven end-to-end through the real stealth/intercept ping-pong
(`minion_phase`/`attempt_block`), including the political-action-card
discard cost; the "ready" gate (offered even while locked -- Rulebook SS3
"locked/unlocked has no impact", same convention already used for titled-
vampire voting -- but never while in torpor); the "political action card in
hand" gate; and the once-per-turn cap (Rulebook SS3 "During X, do Y"), both
within one turn across two different actions and again on a later turn.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.maila import ABILITY_KEY, KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard, hooks
from vtesbot.engine.action import ACTION_BLEED, ACTION_HUNT
from vtesbot.engine.phases.minion import minion_phase

NAME = "Maila"
STEALTH_MODIFIER_HOOK = "stealth_modifier"


def _make_maila(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Maila's real printed
    identity (`CryptCard` is frozen, mirrors `test_diana_iadanza.py::
    _make_diana`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=6,
        clan="Toreador",
        title="Primogen",
        disciplines=("cel", "AUS", "PRE"),
    )


def _political_action_card() -> LibraryCard:
    return LibraryCard(krcg_id=900201, name="Fake Political Action", card_type="Political Action")


def _offer(game, *, acting_vampire="Maila1", action=ACTION_BLEED, blocking_vampire="B1"):
    return hooks.offer(
        STEALTH_MODIFIER_HOOK,
        game.state,
        player="P1",
        stealth=0,
        intercept=0,
        actor="P1",
        defender="P2",
        acting_vampire=acting_vampire,
        blocking_vampire=blocking_vampire,
        action=action,
        directed=True,
        pending={},
    )


def test_registered_as_implemented_against_stealth_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == (registry.Hook.STEALTH_MODIFIER,)
    assert reg.blocked_reason is None


# --- "If Maila is ready during your turn, you can discard a political ----
# --- action card ... to give a minion you control +1 stealth for the -----
# --- current action." ------------------------------------------------------


def test_end_to_end_through_a_bleed_action_defeats_a_too_slow_blocker():
    """Real `minion_phase`/`attempt_block` scenario: the +1 stealth makes an
    otherwise-successful block fail, exactly like `bonding.py`'s own
    superior-clause end-to-end test."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.ready_vampire("Maila1", capacity=6, blood=1)  # blood=1: not forced to hunt first
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "maila_discard_for_stealth:Maila1")
    actor.expect("minion_phase_choice", "end_minion_phase")  # Maila1 never acts herself
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0): attempt failed
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 lost; block failed thanks to +1 stealth
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Political Action"]
    assert game.vampire("Maila1").ability_used_turn[ABILITY_KEY] == game.state.turn_number
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_offers_the_option_and_apply_discards_exactly_one_card():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game)

    assert len(options) == 1
    assert options[0].choice.value == "maila_discard_for_stealth:Maila1"
    assert options[0].apply(game.state) == 1
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Political Action"]


def test_not_offered_without_a_political_action_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p1, "Maila1")
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer(game) == []


def test_not_offered_when_maila_is_not_controlled_by_the_acting_player():
    """`context["player"]` is always the acting Methuselah (module
    docstring) -- a Maila controlled by the *other* Methuselah must not be
    found by this provider at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30).ready_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p2, "Maila1")
    p2.hand.append(_political_action_card())
    game = builder.build()

    assert _offer(game) == []


# --- "If Maila is **ready** ..." -------------------------------------------


def test_offered_even_while_locked_ready_is_the_only_zone_gate():
    """ "Ready" (the `zone` axis) is independent of "locked" (the separate
    locked/unlocked axis) -- a Maila who has already acted this turn
    (locked, but still `zone == "ready"`) still offers her ability, mirroring
    the already-established "locked/unlocked has no impact" convention for
    titled-vampire voting (`engine/politics.py::TITLE_VOTES` docstring)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("Maila1", capacity=6, blood=0, locked=True)
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    assert len(_offer(game)) == 1


def test_not_offered_when_maila_is_in_torpor():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer(game) == []


# --- "Her ability can only be used once during each of your turns." -------


def test_not_offered_again_within_the_same_turn_even_for_a_different_action():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    first = _offer(game, action=ACTION_BLEED, blocking_vampire="B1")
    assert len(first) == 1
    first[0].apply(game.state)
    assert len(game.state.players["P1"].hand) == 1  # one political action card left in hand

    second = _offer(game, action=ACTION_HUNT, blocking_vampire="B2")
    assert second == []  # once-per-turn cap already spent, even for a different action


def test_offered_again_on_a_later_turn():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("Maila1", capacity=6, blood=0)
    _make_maila(p1, "Maila1")
    p1.hand.append(_political_action_card())
    p1.hand.append(_political_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    first = _offer(game)
    first[0].apply(game.state)
    assert _offer(game) == []  # same turn: cap spent

    game.state.turn_number += 1
    later = _offer(game)
    assert len(later) == 1
