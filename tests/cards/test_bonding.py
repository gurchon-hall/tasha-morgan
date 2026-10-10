"""Bonding (krcg id 100236, `src/vtesbot/cards/bonding.py`).

Card text: "Only usable during a bleed action.\n[dom] +1 bleed
(limited).\n[DOM] +1 stealth and +1 bleed (limited)." Rulings: "[DOM] Cannot
be used if you do not need the stealth at the time you play it." [TOM
19951109]; "[DOM] Cannot be used to increase the stealth of a non-bleed
action." [LSJ 19980824] [RTR 19941109].

One assertion per clause/ruling: the basic clause (`"bleed_amount_modifier"`
hook) and its own hook-selection-based "only usable during a bleed action"
restriction; the superior clause (`"stealth_modifier"` hook) and its explicit
`action` gate (the ruling about non-bleed actions) plus the engine's own
structural "only when needed" ping-pong (the ruling about not needing the
stealth); the single-play "+1 stealth and +1 bleed" delivered together via
the `pending` scratch container (OQ-11), proven end-to-end through
`_perform_bleed`'s own clamp, reproducing OQ-11's own worked example; the
Rulebook SS3 "may opt to use either effect" interplay between the two
clauses; the "(limited)" keyword, both as Bonding's own self-exclusion across
the two hook windows and as a cross-card exclusion against Threats (the
`vtesbot.cards._shared.bleed_bookkeeping` refactor this pass closes a latent
gap between these two already-implemented cards).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.bonding import KRCG_ID
from vtesbot.cards.telepathic_counter import KRCG_ID as TELEPATHIC_COUNTER_KRCG_ID
from vtesbot.cards.threats import KRCG_ID as THREATS_KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_BLEED, ACTION_HUNT, ACTION_POLITICAL, attempt_block
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import minion_phase


def _bonding_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Bonding", card_type="modifier")


def _threats_card() -> LibraryCard:
    return LibraryCard(krcg_id=THREATS_KRCG_ID, name="Threats", card_type="modifier")


def _telepathic_counter_card() -> LibraryCard:
    return LibraryCard(
        krcg_id=TELEPATHIC_COUNTER_KRCG_ID, name="Telepathic Counter", card_type="reaction"
    )


def _decline_defender() -> ScriptedAgent:
    return ScriptedAgent("P2").expect("block_attempt", "decline")


def test_registered_as_implemented_against_both_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Bonding"


# --- Basic clause: "[dom] +1 bleed (limited)" ------------------------------


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("dom",))
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_not_offered_without_dominate():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_level_adds_one_bleed_alone():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "bonding:basic")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + 1
    assert game.state.edge_holder == "P1"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Bonding"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_bleed_bonus_shares_the_clamp_with_a_later_reduction():
    """The basic clause's own `amount_box[0] += 1` and Telepathic Counter's
    own `amount_box[0] -= 2` (same later window) combine under one clamp."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_bonding_card())
    p2 = builder.player("P2", pool=30).ready_vampire(
        "V2", capacity=3, blood=0, disciplines=("AUS",)
    )
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "bonding:basic")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:superior:V2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # max(0, 1 + 1 - 2) == 0 lost
    assert game.state.edge_holder is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_never_offered_to_the_defender():
    """ "The acting minion can play these cards" (SS2 Action modifier cards):
    never offered to the defending Methuselah, regardless of their own
    discipline/hand."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30).ready_vampire("V2", capacity=3, disciplines=("DOM",))
    p2.hand.append(_bonding_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed only; Bonding never offered to P2
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_limited_keyword_forbids_a_second_copy_in_the_same_action():
    """SS8 glossary "Limited"; SS2 "a minion cannot play the same action
    modifier card more than once during a single action"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_bonding_card())
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "bonding:basic")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # only +1, not +2: the second copy is unused
    assert len(game.state.players["P1"].hand) == 1
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Superior clause: "[DOM] +1 stealth and +1 bleed (limited)" ------------


def test_superior_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("DOM",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(
        "stealth_modifier",
        game.state,
        player="P1",
        stealth=0,
        intercept=0,
        actor="P1",
        defender="P2",
        acting_vampire="V1",
        blocking_vampire="B1",
        action=ACTION_BLEED,
        pending={},
    )

    assert options == []


def test_superior_requires_superior_dominate_not_just_basic():
    """Only "DOM" (superior) unlocks the bold-text effect; a vampire with
    only basic "dom" gets nothing from the stealth_modifier hook (the basic
    clause, requiring only "dom", remains available later -- see
    `test_basic_level_adds_one_bleed_alone`)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(
        "stealth_modifier",
        game.state,
        player="P1",
        stealth=0,
        intercept=0,
        actor="P1",
        defender="P2",
        acting_vampire="V1",
        blocking_vampire="B1",
        action=ACTION_BLEED,
        pending={},
    )

    assert options == []


def test_superior_adds_stealth_and_stashes_bleed_reproducing_oq11_worked_example():
    """Reproduces OQ-11's own worked example end-to-end through the real
    `minion_phase`/`_perform_bleed` call site: base bleed 1, Bonding superior
    +1 stealth/+1 bleed (stashed via `pending`), a block attempt that fails
    because of the stealth bump, then Telepathic Counter's superior -2 in the
    later `"bleed_amount_modifier"` window -- `max(0, 1 + 1 - 2) == 0` lost,
    no Edge transfer (not the 1-pool overcharge the rejected "apply
    immediately" alternative OQ-11 describes would have produced)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_bonding_card())
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=1, disciplines=("AUS",)
    )
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "bonding:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0): attempt failed
    defender.expect("bleed_amount_modifier", "telepathic_counter:superior:B1")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # max(0, 1 + 1 - 2) == 0 lost, not 1 (overcharge)
    assert game.state.edge_holder is None
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Bonding"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_vampire_may_opt_to_use_the_basic_effect_instead_when_no_block_is_attempted():
    """Rulebook SS3 "may opt to use either the basic or the superior effect
    ... but not both". With no defending vampire able to attempt a block at
    all, the superior clause's stealth half is never even reachable (the
    ruling's own "cannot be used if you do not need the stealth" -- there is
    nothing to escape), so a superior-Dominate vampire ends up using only the
    basic clause, in the later window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30)  # no ready vampire: no block attempt is even possible
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "bonding:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # never asked anything: no candidates at all

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + 1 (basic only, despite superior Dominate)
    actor.assert_exhausted()
    game.state.agents["P2"].assert_exhausted()


def test_superior_then_basic_blocked_by_the_shared_limited_flag_across_windows():
    """Bonding's own "(limited)": once the superior clause has been played
    (stealth window), a second copy is not offered again, even in the later
    `"bleed_amount_modifier"` window -- `pending`-based bookkeeping (this
    pass's fix to `vtesbot.cards._shared.bleed_bookkeeping`) spans the whole
    action, not just one hook window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_bonding_card())
    p1.hand.append(_bonding_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "bonding:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + stashed 1 = 2; the 2nd copy never fires
    assert game.state.edge_holder == "P1"
    assert len(game.state.players["P1"].hand) == 1  # one copy unused
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_bonding_superior_blocks_a_later_threats_play_via_the_shared_limited_flag():
    """Cross-card "(limited)" (SS8 glossary): once Bonding's superior clause
    has increased the bleed (from the earlier stealth window), Threats --
    which can only ever act in the later `"bleed_amount_modifier"` window --
    must not also add to it. Proves the `_shared.py` `bleed_bookkeeping`
    refactor (keyed off `pending`, spanning the whole action, rather than the
    later window's own `amount_box`) actually closes this gap: before the
    refactor, Threats' own bookkeeping dict would have started fresh in
    `resolve()`, unaware of Bonding's earlier play, and could have added its
    own +1/+2 on top."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_bonding_card())
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_modifier", "bonding:superior")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + stashed 1 = 2; Threats never fires
    assert game.state.edge_holder == "P1"
    assert len(game.state.players["P1"].hand) == 1  # Threats sits unused in hand
    assert game.state.players["P1"].hand[0].krcg_id == THREATS_KRCG_ID
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- "Only usable during a bleed action" (superior clause's explicit gate) -


def test_superior_clause_not_offered_during_a_hunt_even_when_it_is_the_actors_turn():
    """A fake `"intercept_modifier"` provider pushes intercept to meet hunt's
    own +1 baseline stealth, flipping the ping-pong to the actor's turn --
    proving Bonding's own `context["action"] != ACTION_BLEED` gate, not
    merely hook timing, is what excludes it here (unlike the basic clause,
    whose own hook simply never opens during a hunt at all)."""

    def match_hunt_stealth(state, context):
        if context.get("action") != ACTION_HUNT:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_hunt_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=1, disciplines=("DOM",)
        )
        p1.hand.append(_bonding_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")  # must not be asked anything at all
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        blocker = attempt_block(
            game.state,
            "P1",
            "P2",
            base_stealth=1,
            acting_vampire=game.vampire("V1"),
            action=ACTION_HUNT,
            pending={},
        )

        assert blocker is not None  # intercept(1) >= stealth(1): blocked, Bonding never helped
        assert len(game.state.players["P1"].hand) == 1  # Bonding never touched
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_hunt_stealth)


def test_superior_clause_not_offered_during_a_political_action_even_when_actors_turn():
    def match_political_stealth(state, context):
        if context.get("action") != ACTION_POLITICAL:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_political_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=1, disciplines=("DOM",)
        )
        p1.hand.append(_bonding_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        blocker = attempt_block(
            game.state,
            "P1",
            "P2",
            base_stealth=1,
            acting_vampire=game.vampire("V1"),
            action=ACTION_POLITICAL,
            pending={},
        )

        assert blocker is not None
        assert len(game.state.players["P1"].hand) == 1
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_political_stealth)


# --- "Cannot be used if you do not need the stealth at the time you play it"


def test_superior_clause_not_offered_once_stealth_is_no_longer_needed():
    """A fake `"stealth_modifier"` stand-in for some other stealth source
    pushes stealth to 1 first; the next ping-pong iteration then offers
    `"intercept_modifier"` to the defender, never `"stealth_modifier"` to the
    actor again -- Bonding, registered only against `"stealth_modifier"`, is
    simply never queried for the rest of this block attempt, confirming the
    module docstring's claim that this ruling needs no code of its own."""

    def other_stealth_source(state, context):
        if context.get("action") != ACTION_BLEED:
            return []
        return [HookOption(choice=Choice("other", "+1 stealth (not Bonding)"), apply=lambda s: 1)]

    hooks.register("stealth_modifier", other_stealth_source)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=1, disciplines=("DOM",)
        )
        p1.hand.append(_bonding_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1").expect("stealth_modifier", "other")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("block_attempt", "decline")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        blocker = attempt_block(
            game.state,
            "P1",
            "P2",
            base_stealth=0,
            acting_vampire=game.vampire("V1"),
            action=ACTION_BLEED,
            pending={},
        )

        assert blocker is None  # stealth(1) > intercept(0): unblocked, Bonding never offered again
        assert len(game.state.players["P1"].hand) == 1  # Bonding untouched
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("stealth_modifier", other_stealth_source)
