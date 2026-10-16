"""Perfectionist (krcg id 101388, `src/vtesbot/cards/perfectionist.py`).

Card text: "Archetype.\nPut this card on a vampire you control. Once each
turn, this vampire can gain 1 blood after performing a successful action
during which no reaction cards were played. A vampire can have only one
archetype."

One assertion per clause/ruling: the attach clause's card-in-hand gate,
its "a vampire you control" pool (ready and torpid eligible, uncontrolled
is not), "a vampire can have only one archetype" (no re-attach), and that
it is not "Unique" (two copies attach to two different vampires freely);
the blood-gain clause's "this vampire carries Perfectionist" gate, the
controller's own choice ([ANK 20210309-3], both "gain" and "decline"),
the once-per-turn cap ([ANK 20180719-4]) and a decline leaving the
opportunity open for a later action the same turn, the "no reaction cards
were played" gate ([LSJ 20070330]), and the political-action case
(unblocked, referendum then fails -- "successful action" means unblocked,
independent of the referendum's own pass/fail outcome).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.perfectionist import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL, perform_minion_action
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.master import MASTER_PHASE_PLAY_HOOK
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum

NAME = "Perfectionist"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="master")


def _offer_attach(game, *, player):
    return hooks.offer(MASTER_PHASE_PLAY_HOOK, game.state, player=player)


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert set(reg.hooks) == {registry.Hook.MASTER_PHASE_PLAY, registry.Hook.ACTION_SUCCEEDED}


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- Attach clause: "Put this card on a vampire you control..." -----------


def test_attach_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer_attach(game, player="P1") == []


def test_attach_offered_for_a_ready_vampire_and_attaches():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer_attach(game, player="P1")
    assert {o.choice.value for o in options} == {"perfectionist:V1"}

    result = options[0].apply(game.state)

    assert result is False  # not a trifle: no extra master phase action.
    v1 = game.vampire("V1")
    assert any(a.krcg_id == KRCG_ID and a.zone == "attached" for a in v1.attachments)
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_attach_offered_for_a_torpid_vampire():
    """ "A vampire you control" carries no zone qualifier -- a torpid
    vampire is eligible (Rulebook §8 glossary "Target")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("V1", capacity=3)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer_attach(game, player="P1")
    assert {o.choice.value for o in options} == {"perfectionist:V1"}


def test_attach_not_offered_for_an_uncontrolled_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("V1", capacity=3)
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer_attach(game, player="P1")
    assert options == []


def test_attach_not_offered_when_the_vampire_already_carries_one():
    """ "A vampire can have only one archetype" -- no re-attach."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_card())
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME)

    options = _offer_attach(game, player="P1")
    assert options == []


def test_attach_is_not_unique_two_copies_attach_to_two_different_vampires():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3)
    p1.ready_vampire("V2", capacity=3)
    p1.hand.append(_card())
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()

    first = _offer_attach(game, player="P1")
    next(o for o in first if o.choice.value == "perfectionist:V1").apply(game.state)

    second = _offer_attach(game, player="P1")
    assert {o.choice.value for o in second} == {"perfectionist:V2"}


# --- Blood-gain clause ------------------------------------------------------


def test_blood_gain_not_offered_without_a_perfectionist_attached():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    acting = game.vampire("V1")
    game.state.agents["P1"] = ScriptedAgent("P1")  # fails loudly if asked anything.
    game.state.agents["P2"] = ScriptedAgent("P2")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert game.blood_of("V1") == 0


def test_blood_gain_offered_and_gaining_adds_one_blood():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    acting = game.vampire("V1")
    attach_card(game.state, acting, controller="P1", krcg_id=KRCG_ID, name=NAME)
    actor = ScriptedAgent("P1").expect("perfectionist_gain_blood", "gain")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

    assert game.blood_of("V1") == 1
    actor.assert_exhausted()


def test_blood_gain_decline_leaves_the_opportunity_open_for_a_later_action_same_turn():
    """[ANK 20210309-3]: the controller's choice. Declining does not mark
    the once-per-turn cap -- a later successful action the same turn may
    still offer it."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    acting = game.vampire("V1")
    attach_card(game.state, acting, controller="P1", krcg_id=KRCG_ID, name=NAME)
    actor = ScriptedAgent("P1")
    actor.expect("perfectionist_gain_blood", "decline")
    actor.expect("perfectionist_gain_blood", "gain")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)
    assert game.blood_of("V1") == 0

    acting.locked = False  # a second, later successful action this same turn.
    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)
    assert game.blood_of("V1") == 1
    actor.assert_exhausted()


def test_blood_gain_not_offered_a_second_time_this_turn_once_already_gained():
    """ "'Once each turn' means once during each player's turn."
    [ANK 20180719-4]."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    acting = game.vampire("V1")
    attach_card(game.state, acting, controller="P1", krcg_id=KRCG_ID, name=NAME)
    actor = ScriptedAgent("P1").expect("perfectionist_gain_blood", "gain")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    def resolve(pending):
        del pending

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)
    assert game.blood_of("V1") == 1

    acting.locked = False
    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)
    assert game.blood_of("V1") == 1  # unchanged: already used this turn, not offered again.
    actor.assert_exhausted()


def test_blood_gain_not_offered_when_a_reaction_card_was_played_during_the_action():
    """ "No blood can be gained if a reaction card is played and canceled
    as it is played: it has still been played." [LSJ 20070330]."""

    def reaction_provider(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("use_reaction", "+5 stealth"),
                apply=lambda s: 5,
                played_card_type="Reaction",
            )
        ]

    hooks.register("stealth_modifier", reaction_provider)
    try:
        builder = ScenarioBuilder(seed=1)
        builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
        game = builder.build()
        acting = game.vampire("V1")
        attach_card(game.state, acting, controller="P1", krcg_id=KRCG_ID, name=NAME)
        actor = ScriptedAgent("P1").expect("stealth_modifier", "use_reaction")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("block_attempt", "decline")  # intercept 0 never catches stealth 5.
        game.state.agents["P2"] = defender

        def resolve(pending):
            del pending

        perform_minion_action(game.state, "P1", "P2", acting, base_stealth=0, resolve=resolve)

        assert game.blood_of("V1") == 0  # no blood at all this action.
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("stealth_modifier", reaction_provider)


def test_political_action_unblocked_referendum_fails_still_offers_the_gain():
    """A political action's "successful action" means unblocked,
    independent of the referendum's own pass/fail outcome (module
    docstring, Rulebook §4). The referendum here ties 0-0 (both sides
    decline) and so fails, yet the gain is still offered."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    acting = game.vampire("V1")
    attach_card(game.state, acting, controller="P1", krcg_id=KRCG_ID, name=NAME)

    def resolve(pending):
        votes_for, votes_against, _casts = resolve_referendum(
            game.state, "P1", "P2", acting, action_pending=pending
        )
        assert votes_for <= votes_against  # tied: the referendum itself fails.

    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "pass")
    actor.expect("perfectionist_gain_blood", "gain")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    perform_minion_action(
        game.state,
        "P1",
        "P2",
        acting,
        base_stealth=POLITICAL_ACTION_STEALTH,
        resolve=resolve,
        action=ACTION_POLITICAL,
    )

    assert game.blood_of("V1") == 1
    actor.assert_exhausted()
