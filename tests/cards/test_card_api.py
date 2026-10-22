"""`cards/card.py::Card`: registration, derived hooks, blocking, options."""

import pytest

from vtesbot.cards import registry
from vtesbot.cards.card import Card
from vtesbot.engine import hooks
from vtesbot.engine.hooks import Hook

FAKE_ID = 999_001


@pytest.fixture(autouse=True)
def _drop_fake_card():
    yield
    registry.remove(FAKE_ID)


def test_registers_itself_with_the_defining_module_as_source():
    card = Card(FAKE_ID, "Fake", "Master")
    assert registry.get(FAKE_ID) is card
    assert card.status is registry.Status.IMPLEMENTED
    assert card.source == __name__


def test_hooks_are_derived_from_on_in_first_use_order():
    card = Card(FAKE_ID, "Fake")

    @card.on(Hook.CAPACITY_MODIFIER)
    def _a(state, ctx):
        return 1

    @card.on(Hook.MASTER_PHASE_PLAY)
    def _b(state, ctx):
        return []

    @card.on(Hook.CAPACITY_MODIFIER)
    def _c(state, ctx):
        return 2

    assert card.hooks == (Hook.CAPACITY_MODIFIER, Hook.MASTER_PHASE_PLAY)
    providers = hooks.snapshot()[Hook.CAPACITY_MODIFIER]
    assert providers[-2:] == [_a, _c]


def test_unwired_hook_cannot_be_registered_but_can_be_declared():
    card = Card(FAKE_ID, "Fake", also_uses=(Hook.LOCATION_ENTITY,))
    assert card.hooks == (Hook.LOCATION_ENTITY,)
    with pytest.raises(ValueError, match="no engine dispatch site"):
        card.on(Hook.RANGED_STRIKE)


def test_block_requires_a_reason():
    card = Card(FAKE_ID, "Fake")
    with pytest.raises(ValueError):
        card.block("")
    card.block("ENG-046")
    assert card.status is registry.Status.BLOCKED
    assert FAKE_ID in registry.blocked_ids()


def test_option_stamps_card_type_unless_overridden():
    card = Card(FAKE_ID, "Fake", "Combat")
    played = card.option("fake:a", "A", lambda s: None)
    claimed = card.option("fake:b", "B", lambda s: None, played_card_type=None)
    assert played.choice.value == "fake:a"
    assert played.played_card_type == "Combat"
    assert claimed.played_card_type is None


def test_duplicate_krcg_id_is_rejected():
    Card(FAKE_ID, "Fake")
    with pytest.raises(ValueError, match="already registered"):
        Card(FAKE_ID, "Fake again")


def test_library_card_requires_card_type():
    with pytest.raises(ValueError, match="card_type"):
        Card(100_001, "Library card without type")
    assert registry.get(100_001) is None


def test_also_uses_rejects_wired_hooks():
    with pytest.raises(ValueError, match="unwired hooks only"):
        Card(FAKE_ID, "Fake", also_uses=(Hook.MASTER_PHASE_PLAY,))


def test_block_refuses_a_card_with_wired_providers():
    card = Card(FAKE_ID, "Fake")

    @card.on(Hook.CAPACITY_MODIFIER)
    def _a(state, ctx):
        return 1

    with pytest.raises(ValueError, match="stay playable"):
        card.block("ENG-046")


def test_blocked_card_records_planned_hooks_and_cannot_wire():
    card = Card(FAKE_ID, "Fake")
    card.block("ENG-046", planned_hooks=(Hook.BEFORE_RANGE, Hook.COMBAT_STRENGTH_MODIFIER))
    assert card.hooks == (Hook.BEFORE_RANGE, Hook.COMBAT_STRENGTH_MODIFIER)
    with pytest.raises(ValueError, match="must not wire"):
        card.on(Hook.BEFORE_RANGE)


def test_explicit_source_overrides_the_caller_module():
    assert Card(FAKE_ID, "Fake", source="vtesbot.cards.factory").source == "vtesbot.cards.factory"
