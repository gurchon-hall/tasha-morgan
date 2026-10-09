"""The card implementation registry (`src/vtesbot/cards/registry.py`,
CLAUDE.md SS6 scaffolding pass). Mechanism-only tests with trivial fake
registrations; real card registrations and their own tests are
`card-implementer`'s next pass.
"""

import pytest

from vtesbot.cards import registry

_FAKE_ID_FLOOR = 900_000
"""Same synthetic-id convention `tests/helpers.py` already reserves
(`_next_crypt_id`/`_next_lib_id`, 900_000+/800_000+) for test-only cards, so
this fixture can tell a fake registration apart from a real one without
tracking a before/after diff."""


@pytest.fixture(autouse=True)
def _isolate_fake_registrations():
    """Remove only the fake (>= 900_000) registrations a test adds, so a
    real card registration (e.g. from importing `vtesbot.cards`) is never
    wiped out -- this registry is static, process-wide state
    (`docs/DECISIONS.md` D-5), not per-test state."""
    yield
    for reg in registry.all_registrations():
        if reg.krcg_id >= _FAKE_ID_FLOOR:
            registry.remove(reg.krcg_id)


def test_register_then_get_round_trips():
    reg = registry.CardRegistration(
        krcg_id=999001,
        name="Fake Implemented Card",
        status=registry.Status.IMPLEMENTED,
        hooks=(registry.Hook.MASTER_PHASE_PLAY,),
        source="tests.cards.test_registry",
    )
    registry.register(reg)

    assert registry.get(999001) is reg
    assert 999001 in registry.implemented_ids()
    assert 999001 not in registry.blocked_ids()


def test_registering_the_same_krcg_id_twice_is_an_error():
    reg = registry.CardRegistration(
        krcg_id=999002,
        name="Fake Card",
        status=registry.Status.IMPLEMENTED,
        hooks=(),
        source="tests.cards.test_registry",
    )
    registry.register(reg)

    with pytest.raises(ValueError):
        registry.register(reg)


def test_a_blocked_card_must_carry_a_blocked_reason():
    with pytest.raises(ValueError):
        registry.register(
            registry.CardRegistration(
                krcg_id=999003,
                name="Fake Blocked Card",
                status=registry.Status.BLOCKED,
                hooks=(registry.Hook.POLITICAL_ACTION,),
                source="tests.cards.test_registry",
                # blocked_reason intentionally omitted
            )
        )


def test_blocked_card_is_registered_but_not_counted_as_implemented():
    registry.register(
        registry.CardRegistration(
            krcg_id=999004,
            name="Fake Blocked Card",
            status=registry.Status.BLOCKED,
            hooks=(registry.Hook.POLITICAL_ACTION,),
            source="tests.cards.test_registry",
            blocked_reason="OQ-6",
        )
    )

    assert 999004 in registry.blocked_ids()
    assert 999004 not in registry.implemented_ids()
    assert registry.get(999004).blocked_reason == "OQ-6"


def test_get_returns_none_for_an_unregistered_card():
    assert registry.get(1234567) is None


def test_all_registrations_includes_every_registered_card():
    registry.register(
        registry.CardRegistration(
            krcg_id=999005,
            name="Fake Card A",
            status=registry.Status.IMPLEMENTED,
            hooks=(),
            source="tests.cards.test_registry",
        )
    )
    registry.register(
        registry.CardRegistration(
            krcg_id=999006,
            name="Fake Card B",
            status=registry.Status.BLOCKED,
            hooks=(),
            source="tests.cards.test_registry",
            blocked_reason="OQ-6",
        )
    )

    ids = {reg.krcg_id for reg in registry.all_registrations()}
    assert {999005, 999006} <= ids


def test_the_real_card_modules_import_without_error_and_register_once_each():
    """Importing `vtesbot.cards` must not raise (every module's top-level
    `register(...)` call must succeed) and must not register the same krcg
    id twice across modules."""
    import vtesbot.cards  # noqa: F401 -- import for its registration side effect

    # Every OQ-6-blocked card documented in the rules-engineer milestone-3
    # scaffolding report is actually registered, as blocked, with a reason.
    for krcg_id in (
        100557,  # Disputed Territory
        101056,  # Kine Resources Contested
        101353,  # Parity Shift
        101341,  # Oxford University, England
        101387,  # Perfect Paragon
        101686,  # Scalpel Tongue
        102131,  # Voter Captivation
        201529,  # Alexa Draper
        201694,  # Diana Iadanza
        201616,  # Fiorenza Savona
        201702,  # Marcos Belegrad
        201703,  # Modius
        201647,  # Queen Anne
    ):
        reg = registry.get(krcg_id)
        assert reg is not None, f"expected a registry entry for krcg_id {krcg_id}"
        assert reg.status is registry.Status.BLOCKED
        assert reg.blocked_reason == "OQ-6"
