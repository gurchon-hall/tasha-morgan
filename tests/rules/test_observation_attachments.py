"""`VampireView.attachments`/`ash_heap` deduplication (ENG-038):
`engine/observation.py::build_observation` now exposes every live
`CardAttachment` on a vampire via `AttachmentView`, and no longer double-lists
the same physical card in the player's own `ash_heap` once it has also become a
live attachment (CLAUDE.md §5: attachments are always public once played --
Rulebook §3 "Playing a Card": "showing the card" -- so no hidden-identity gate
applies beyond the host vampire's own `visible_identity`, already proven for
`name`/`blood`/`capacity`).

Exercised against the three real attachment-playing cards already in this
pool (Perfectionist krcg 101388, Pulled Fangs krcg 101515, Weighted
Walking Stick krcg 102169) via each card's own real hook provider, not a
synthetic stand-in -- plus one fully synthetic test proving the
count-based (not identity-based) filter in `_visible_ash_heap` leaves a
genuinely separate, already-burned ash-heap copy of the same `krcg_id`
visible."""

from helpers import ScenarioBuilder
from vtesbot.cards.perfectionist import KRCG_ID as PERFECTIONIST_ID
from vtesbot.cards.pulled_fangs import KRCG_ID as PULLED_FANGS_ID
from vtesbot.cards.pulled_fangs import NAME as PULLED_FANGS_NAME
from vtesbot.cards.weighted_walking_stick import KRCG_ID as WWS_ID
from vtesbot.cards.weighted_walking_stick import NAME as WWS_NAME
from vtesbot.engine import LibraryCard, build_observation, hooks
from vtesbot.engine.combat import (
    BEFORE_RANGE_HOOK,
    CLOSE_RANGE,
    END_OF_ROUND_HOOK,
    ROUND_STATE_CONTEXT_KEY,
)
from vtesbot.engine.damage import record_damage_successfully_inflicted
from vtesbot.engine.phases.master import MASTER_PHASE_PLAY_HOOK

PERFECTIONIST_NAME = "Perfectionist"


def _perfectionist_card() -> LibraryCard:
    return LibraryCard(krcg_id=PERFECTIONIST_ID, name=PERFECTIONIST_NAME, card_type="master")


def _pulled_fangs_card() -> LibraryCard:
    return LibraryCard(krcg_id=PULLED_FANGS_ID, name=PULLED_FANGS_NAME, card_type="combat")


def _wws_card() -> LibraryCard:
    return LibraryCard(krcg_id=WWS_ID, name=WWS_NAME, card_type="combat")


def test_perfectionist_attachment_is_visible_and_not_duplicated_in_ash_heap():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_perfectionist_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(MASTER_PHASE_PLAY_HOOK, game.state, player="P1")
    next(o for o in options if o.choice.value == "perfectionist:V1").apply(game.state)

    obs = build_observation(game.state, "P1")
    view = next(v for v in obs.vampires if v.instance_id == "V1")
    assert [a.name for a in view.attachments] == [PERFECTIONIST_NAME]
    assert view.attachments[0].krcg_id == PERFECTIONIST_ID
    assert PERFECTIONIST_NAME not in obs.ash_heap["P1"]

    # Visible from the opponent's side too (ENG-038's own "always public" claim).
    obs_opponent = build_observation(game.state, "P2")
    opp_view = next(v for v in obs_opponent.vampires if v.instance_id == "V1")
    assert [a.name for a in opp_view.attachments] == [PERFECTIONIST_NAME]


def test_pulled_fangs_attachment_is_visible_and_not_duplicated_in_ash_heap():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_pulled_fangs_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.state.combat_range = CLOSE_RANGE
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 3)

    options = hooks.offer(
        END_OF_ROUND_HOOK,
        game.state,
        player="P1",
        acting_player="P1",
        acting_vampire="V1",
        blocking_player="P2",
        blocking_vampire="B1",
        **{ROUND_STATE_CONTEXT_KEY: round_state},
    )
    next(o for o in options if o.choice.value == "pulled_fangs").apply(game.state)

    obs = build_observation(game.state, "P2")
    victim_view = next(v for v in obs.vampires if v.instance_id == "B1")
    assert [a.name for a in victim_view.attachments] == [PULLED_FANGS_NAME]
    assert victim_view.attachments[0].controller == "P1"  # the playing Methuselah, not B1's own.
    # The card was played from P1's own hand (`_shared.play_from_hand`), so
    # P1's own ash heap is the one that would otherwise double-list it.
    assert PULLED_FANGS_NAME not in obs.ash_heap["P1"]


def test_weighted_walking_stick_attachment_is_visible_and_not_duplicated_in_ash_heap():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        player="P1",
        acting_player="P1",
        acting_vampire="V1",
        blocking_player="P2",
        blocking_vampire="B1",
        combat_state={},
    )
    next(o for o in options if o.choice.value == "weighted_walking_stick:attach:V1").apply(
        game.state
    )

    obs = build_observation(game.state, "P1")
    view = next(v for v in obs.vampires if v.instance_id == "V1")
    assert [a.name for a in view.attachments] == [WWS_NAME]
    assert view.attachments[0].counters == 5
    assert view.attachments[0].is_equipment is True
    assert WWS_NAME not in obs.ash_heap["P1"]


def test_ash_heap_filter_is_count_based_not_identity_based():
    """A genuinely separate, already-burned ash-heap copy of the same
    `krcg_id` (e.g. an earlier Weighted Walking Stick burned out of
    counters in an earlier combat) must stay visible even while a second,
    currently-live copy is attached elsewhere -- `_visible_ash_heap` hides
    at most as many entries as there are live attachments, never every
    entry sharing that `krcg_id`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30)
    game = builder.build()
    # A second, already-burned copy sitting in the ash heap from an earlier turn.
    game.state.players["P1"].ash_heap.append(_wws_card())

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        player="P1",
        acting_player="P1",
        acting_vampire="V1",
        blocking_player="P2",
        blocking_vampire="B1",
        combat_state={},
    )
    next(o for o in options if o.choice.value == "weighted_walking_stick:attach:V1").apply(
        game.state
    )

    obs = build_observation(game.state, "P1")
    # The attach option's own `play_from_hand` appended a *second* ash-heap
    # entry (immediately filtered back out, since it is the one now live);
    # the pre-seeded one must remain.
    assert obs.ash_heap["P1"].count(WWS_NAME) == 1
