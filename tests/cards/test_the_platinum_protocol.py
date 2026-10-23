"""The Platinum Protocol (krcg id 102232, `src/vtesbot/cards/the_platinum_protocol.py`).

Card text: "Requires an Anarch. More than one Discipline can be used to play
this card. Ⓓ Bleed.\n[obf] This is a +1 stealth action.\n[pre] The bleed is
with +1 bleed.\n[pro] Put 1 corruption counter on a minion controlled by the
target Methuselah if the bleed is successful (for 1 or more)." Rulings:
"[pro] The minion getting the corruption counter is chosen at action
resolution (not declaration)." [ANK 20240706] [LSJ 20080608]; "[pro] Putting
a corruption counter on a minion does not give you an opportunity to steal
it." [ANK 20200925] [ANK 20211105]; the generic multi-Discipline ruling
[LSJ 20011204-3] [PIB 20130704].

One assertion per clause/qualifier/ruling: the "Requires an Anarch" gate
(including unset sect); needing at least one of obf/pre/pro; card-in-hand
gate; `[obf]`'s +1 stealth; `[pre]`'s +1 bleed; `[pro]`'s corruption counter
only on success (amount >= 1), chosen at resolution (not declaration,
proven by decision ordering), auto-bound with one target vs. a `Decision`
with several, and fizzling with no eligible target or a reduced-to-0 bleed;
a vampire with every discipline sees one single combined option, not three
alternatives.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.registry import Status, get
from vtesbot.cards.the_platinum_protocol import KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "The Platinum Protocol"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Mirrors `test_line_brawl.py::_set_sect`/`test_dust_up.py::_set_sect`:
    neither `ready_vampire` nor `uncontrolled_vampire` has a `sect=`
    parameter, and `CryptCard` is frozen, so a fresh instance is swapped in,
    preserving every other field."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=old.clan,
        title=old.title,
        disciplines=old.disciplines,
        sect=sect,
    )


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- "Requires an Anarch" / discipline gates --------------------------------


def test_not_offered_for_a_non_anarch_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf", "pre", "pro")
    )
    _set_sect(p1, "V1", Sect.CAMARILLA)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_not_offered_when_sect_is_unset():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf", "pre", "pro")
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    assert game.vampire("V1").card.sect is None
    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_not_offered_without_any_of_obf_pre_pro():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("aus", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf", "pre", "pro")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_one_of_the_three_disciplines_is_enough_to_be_offered():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert len(options) == 1


def test_all_three_disciplines_still_offer_a_single_combined_option():
    """Unlike Line Brawl/Dust Up's alternative clauses, every bracket here
    modifies one base bleed -- a vampire with all three disciplines sees one
    option, not three."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf", "pre", "pro")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert len(options) == 1
    assert options[0].choice.value == "platinum_protocol"


# --- "[obf]"/"[pre]" bleed composition ---------------------------------------


def test_obf_grants_plus_one_stealth_and_no_bleed_bonus():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)

    assert spec.base_stealth == 1
    assert spec.directed is True


def test_pre_grants_plus_one_bleed_and_no_stealth_bonus():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    assert spec.base_stealth == 0

    spec.resolve({})

    assert game.pool_of("P2") == 28  # default bleed 1 + printed "+1 bleed".


def test_without_pre_the_bleed_is_the_plain_default_amount():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.pool_of("P2") == 29  # default bleed amount 1, no "pre" bonus.


# --- "[pro]" corruption counter ----------------------------------------------


def test_pro_places_a_corruption_counter_on_a_successful_bleed_single_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.vampire("W1").corruption_counters == {"P1": 1}


def test_pro_target_is_chosen_at_resolution_not_declaration():
    """Proven by decision ordering: the `platinum_protocol_target` decision
    is only raised *after* the block-attempt decline, inside `resolve()` --
    were the target bound at `apply()`/announce time instead, no such
    decision would appear here at all (it would already be fixed)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    p2.ready_vampire("W2", capacity=3)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)
    actor.expect("platinum_protocol_target", "platinum_protocol_target:W1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("W1").corruption_counters == {"P1": 1}
    assert game.vampire("W2").corruption_counters == {}
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pro_fizzles_with_no_eligible_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30)  # no vampire at all to place a counter on
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})  # must not raise despite "pro" being present.

    assert game.pool_of("P2") == 29


def test_pro_does_not_target_the_defenders_uncontrolled_vampires():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.uncontrolled_vampire("Secret-V", capacity=4)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.vampire("Secret-V").corruption_counters == {}


def test_pro_does_not_target_a_burned_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    game.vampire("W1").zone = "burned"

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})  # must not raise despite "pro" being present.

    assert game.vampire("W1").corruption_counters == {}


def test_pro_still_targets_a_torpid_vampire():
    """A torpor vampire is still "controlled", distinct from a face-down
    uncontrolled one (Sergio Bueno's own on-file ruling that an analogous
    corruption-counter ability "applies even if the vampire is in torpor")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("T1", capacity=3)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.vampire("T1").corruption_counters == {"P1": 1}


def test_pro_does_not_fire_when_the_bleed_amount_is_reduced_to_zero():
    """ "if the bleed is successful (for 1 or more)" -- a bleed reduced to 0
    by some other effect does not place a counter, even though the action
    itself still goes unblocked and its other clauses still apply."""

    def zero_out(state, context):
        del state, context
        return -10

    hooks.register("bleed_amount_fixed_modifier", zero_out)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=1, disciplines=("pro",)
        )
        _set_sect(p1, "V1", Sect.ANARCH)
        p1.hand.append(_card())
        builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
        game = builder.build()

        (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        spec = option.apply(game.state)
        spec.resolve({})

        assert game.pool_of("P2") == 30  # nothing lost: amount clamped to 0.
        assert game.vampire("W1").corruption_counters == {}
        assert game.state.edge_holder is None
    finally:
        hooks.unregister("bleed_amount_fixed_modifier", zero_out)


def test_pro_offers_a_decision_with_multiple_eligible_targets():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    p2.ready_vampire("W2", capacity=3)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)
    actor.expect("platinum_protocol_target", "platinum_protocol_target:W2")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("W2").corruption_counters == {"P1": 1}
    assert game.vampire("W1").corruption_counters == {}
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_pro_asks_no_target_once_the_bleed_ousts_the_defender():
    """Rulebook §5: an ousted Methuselah leaves the game, with nothing left to
    resolve against (ENG-052)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pro",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=1).ready_vampire("W1", capacity=3)
    p2.ready_vampire("W2", capacity=3)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)  # no platinum_protocol_target after
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.state.winner == "P1"
    assert game.vampire("W1").corruption_counters == {}
    assert game.vampire("W2").corruption_counters == {}
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- blocked attempt ---------------------------------------------------------


def test_blocked_action_never_resolves_and_the_card_is_still_consumed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("obf", "pre", "pro")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    def match_stealth(state, context):
        del state
        if context.get("action") != "bleed":
            return []
        from vtesbot.engine.decision import Choice as _Choice
        from vtesbot.engine.hooks import HookOption as _HookOption

        return [_HookOption(choice=_Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_stealth)
    try:
        (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", option.choice.value)
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.pool_of("P2") == 30  # unresolved: blocked.
        assert game.vampire("B1").corruption_counters == {}
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_stealth)
