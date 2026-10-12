"""Taste of Vitae (krcg id 101945, `src/vtesbot/cards/taste_of_vitae.py`).

Card text: "Only usable at the end of a round of combat. Not usable by a
vampire being burned or going to torpor. A vampire can play only one Taste
of Vitae each round.\nThis vampire gains blood equal to the amount of blood
lost by the opposing vampire to damage this round." Rulings: "Cannot be
played against an ally. [PIB 20121028]"; "Must be played after the presses
are handled and can be played if the round ends prematurely. [RTR 20001020]
[LSJ 20001024] [RTR 20030519]"; "Can be played before or after effects that
are played at the end of the round or 'when the combat would end' (eg. [AUS]
{Telepathic Tracking}). Can be played after [CEL] {Psyche!} [LSJ 20021113]
[ANK 20191219] [ANK 20180910-1]"; "Can be played if the opponent was burned.
[LSJ 20031201-2]".

One assertion per clause/qualifier: the window gate (only offered via
`END_OF_ROUND_HOOK`); the "card in hand" gate; the playing vampire's own
zone exclusion (burned/torpor -- never the opponent's own zone); the
round-scoped "only one per vampire per round" cap, distinct from the
cross-card "(limited)" additional-strike cap; correct `acting`/`blocking`
side resolution (which vampire is "this vampire" vs. "the opposing
vampire"); the gain amount read from `blood_lost_to_damage_this_round`
across mend-only, aggravated-only and mixed scenarios; a zero amount still
being playable (no effect, not a reason to withhold the option); surviving
the opposing vampire being burned afterward; and one full `run_combat`
integration proving the whole window end to end.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.combat import END_OF_ROUND_HOOK, ROUND_STATE_CONTEXT_KEY, run_combat
from vtesbot.engine.damage import record_blood_lost_to_damage

KRCG_ID = 101945
NAME = "Taste of Vitae"


def _tov_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _offer(game, *, player: str, round_state: dict | None = None):
    return hooks.offer(
        END_OF_ROUND_HOOK,
        game.state,
        player=player,
        acting_player="P1",
        acting_vampire="V1",
        blocking_player="P2",
        blocking_vampire="B1",
        **({ROUND_STATE_CONTEXT_KEY: round_state} if round_state is not None else {}),
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.END_OF_ROUND in reg.hooks


# --- Window/hand/zone gates ---------------------------------------------------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    assert _offer(game, player="P1") == []


def test_not_offered_to_a_vampire_being_burned():
    """ "Not usable by a vampire being burned or going to torpor" -- the
    *playing* vampire's own zone, not the opponent's."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    game.vampire("V1").zone = "burned"

    assert _offer(game, player="P1") == []


def test_not_offered_to_a_vampire_going_to_torpor():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    game.vampire("V1").zone = "torpor"

    assert _offer(game, player="P1") == []


def test_offered_normally_when_ready_with_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    values = {o.choice.value for o in _offer(game, player="P1", round_state={})}
    assert values == {"taste_of_vitae"}


def test_playing_vampires_own_burned_opponent_does_not_block_the_offer():
    """The opponent's own zone is never checked -- only the playing
    vampire's. (The opponent being burned is covered separately, below, for
    the blood-loss-record-survives-burn case; this test only confirms the
    offer itself is unaffected by the opponent's zone.)"""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    game.vampire("B1").zone = "burned"

    values = {o.choice.value for o in _offer(game, player="P1", round_state={})}
    assert values == {"taste_of_vitae"}


# --- "A vampire can play only one Taste of Vitae each round." --------------


def test_not_offered_again_in_the_same_round_after_being_played():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    round_state: dict = {}
    first = _offer(game, player="P1", round_state=round_state)
    assert {o.choice.value for o in first} == {"taste_of_vitae"}
    first[0].apply(game.state)

    second = _offer(game, player="P1", round_state=round_state)
    assert second == []
    assert len(game.state.players["P1"].hand) == 1  # the second copy stayed unused


def test_offered_again_in_a_fresh_round_state():
    """The cap is round-scoped, not forever: a fresh `round_state` (a new
    round) offers it again."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    used_round: dict = {}
    _offer(game, player="P1", round_state=used_round)[0].apply(game.state)

    fresh_round: dict = {}
    values = {o.choice.value for o in _offer(game, player="P1", round_state=fresh_round)}
    assert values == {"taste_of_vitae"}


def test_the_cap_is_per_vampire_not_shared_across_the_two_combatants():
    """The same `round_state` is shared by both combatants' own offers (it is
    one object for the whole round), but the "already played" flag is keyed
    per playing-vampire id -- P1 using their own copy must not block P2's
    own, independent copy the same round."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    p2 = builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    p2.hand.append(_tov_card())
    game = builder.build()

    round_state: dict = {}
    _offer(game, player="P1", round_state=round_state)[0].apply(game.state)

    values = {o.choice.value for o in _offer(game, player="P2", round_state=round_state)}
    assert values == {"taste_of_vitae"}


# --- Correct acting/blocking side resolution ---------------------------------


def test_acting_side_gains_blood_lost_by_the_blocking_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "B1", 3)
    record_blood_lost_to_damage(round_state, "V1", 99)  # this vampire's own loss is irrelevant

    options = _offer(game, player="P1", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 3 blood"
    options[0].apply(game.state)
    assert game.vampire("V1").blood == 4  # 1 + 3, capacity 5 not exceeded


def test_blocking_side_gains_blood_lost_by_the_acting_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    p2.hand.append(_tov_card())
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "V1", 2)
    record_blood_lost_to_damage(round_state, "B1", 99)  # this vampire's own loss is irrelevant

    options = _offer(game, player="P2", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 2 blood"
    options[0].apply(game.state)
    assert game.vampire("B1").blood == 3  # 1 + 2


# --- Amount calculation across mend/aggravated-burn/mixed scenarios --------


def test_amount_reflects_mend_only_loss():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=2)
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "B1", 2)  # 2 blood spent mending

    values = {o.choice.value for o in _offer(game, player="P1", round_state=round_state)}
    assert values == {"taste_of_vitae"}
    options = _offer(game, player="P1", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 2 blood"


def test_amount_reflects_aggravated_burn_only_loss():
    """An already-wounded vampire's aggravated-burn blood loss is recorded
    the same way as a mend-step loss -- the provider does not care which
    branch produced the total, only the combined running sum."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=3)
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "B1", 1)  # 1 aggravated-burn point

    options = _offer(game, player="P1", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 1 blood"


def test_amount_reflects_mixed_mend_and_aggravated_burn_loss_summed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=4)
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "B1", 2)  # mend step
    record_blood_lost_to_damage(round_state, "B1", 1)  # aggravated-burn step, same round, summed

    options = _offer(game, player="P1", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 3 blood"


def test_zero_amount_is_still_offered_and_playable():
    """The card text does not condition playability on a nonzero amount --
    the opponent having lost no blood to damage this round is not itself a
    reason to withhold the option; it is still offered and simply has no
    effect (gains 0 blood) when played."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    round_state: dict = {}  # nothing recorded: the opponent lost no blood to damage this round.
    options = _offer(game, player="P1", round_state=round_state)
    assert {o.choice.value for o in options} == {"taste_of_vitae"}
    assert options[0].choice.label == "Taste of Vitae: gain 0 blood"
    options[0].apply(game.state)
    assert game.vampire("V1").blood == 1  # unchanged


def test_survives_the_opposing_vampire_being_burned():
    """ "Can be played if the opponent was burned" [LSJ 20031201-2]: the
    blood-loss record is a plain dict entry, untouched by the opponent's own
    zone transition."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    round_state: dict = {}
    record_blood_lost_to_damage(round_state, "B1", 4)
    game.vampire("B1").zone = "burned"  # the opponent was burned after taking damage this round.

    options = _offer(game, player="P1", round_state=round_state)
    assert options[0].choice.label == "Taste of Vitae: gain 4 blood"
    options[0].apply(game.state)
    assert game.vampire("V1").blood == 4


# --- Full `run_combat` integration ------------------------------------------


def test_full_round_hand_strike_then_taste_of_vitae_end_to_end():
    """V1 lands a plain hand strike on B1; B1's controller chooses to mend 1
    of it; V1 then plays Taste of Vitae at the end-of-round window and gains
    exactly that 1 blood. Proves the whole chain: `_resolve_strike_pair` ->
    `apply_damage(..., round_state=...)` -> `record_blood_lost_to_damage` ->
    `_ask_end_of_round` -> this provider -> `blood_lost_to_damage_this_round`
    -> `add_blood`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=2)
    p1.hand.append(_tov_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=3)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    actor.expect("end_of_round", "taste_of_vitae")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").blood == 2  # 3 - 1 mended
    assert game.vampire("B1").wounded is False  # fully mended, never wounded
    assert game.vampire("V1").blood == 3  # 2 + 1 (gained from Taste of Vitae)
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()
