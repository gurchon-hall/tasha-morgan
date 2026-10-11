"""Protection Racket (krcg id 101501, `src/vtesbot/cards/protection_racket.py`).

Card text: "Requires an Anarch.\n+1 intercept, with an additional +1
intercept if the acting minion is titled." Ruling: "The additional intercept
is gained or lost if the acting vampire changes sect during the action (eg.
with {The Red Question} or {Mask of a Thousand Faces})." [ANK 20190416].

One assertion per clause/qualifier/ruling: the "Requires an Anarch" gate on
the *reacting* (playing) vampire, independent of the acting minion's own
sect; the base "+1 intercept"; the additional "+1 intercept" only when the
acting minion is titled, recomputed live rather than cached; the card-in-hand
gate; the "cannot play the same reaction card twice in one action" per-minion
restriction (a second, distinct eligible vampire is unaffected); that playing
the card never locks the playing vampire.
"""

from helpers import ScenarioBuilder
from vtesbot.cards import registry
from vtesbot.cards.protection_racket import KRCG_ID, USED_BY_KEY
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK

NAME = "Protection Racket"


def _protection_racket_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="reaction")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `sect`
    (mirrors `test_dust_up.py::_set_sect`: `ready_vampire` has no `sect=`
    parameter and `CryptCard` is frozen, so a fresh instance is swapped in,
    preserving every other field)."""
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


def _offer(game, *, defender: str, actor: str, acting_vampire: str, pending: dict | None = None):
    return hooks.offer(
        INTERCEPT_MODIFIER_HOOK,
        game.state,
        player=defender,
        actor=actor,
        acting_vampire=acting_vampire,
        pending=pending,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Requires an Anarch" -- gates the reacting (playing) vampire ----------


def test_not_offered_for_a_non_anarch_reacting_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.CAMARILLA)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_not_offered_when_reacting_vampires_sect_is_unset():
    """`CryptCard.sect` defaults to `None`; a card gating on sect must treat
    that as "does not qualify," never guess a default sect."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    assert game.vampire("D1").card.sect is None
    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


def test_offered_for_an_anarch_reacting_vampire_even_when_acting_minion_is_also_non_anarch():
    """The sect gate is on the reacting vampire; the acting minion's own
    sect (here unset) is irrelevant to the "Requires an Anarch" clause."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    assert {o.choice.value for o in options} == {"protection_racket:D1"}


# --- card-in-hand gate -------------------------------------------------------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    game = builder.build()

    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    assert options == []


# --- "+1 intercept" / "additional +1 intercept if the acting minion is titled"


def test_base_bonus_is_one_intercept_when_acting_minion_is_untitled():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    assert game.vampire("A1").card.title is None
    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    option = next(o for o in options if o.choice.value == "protection_racket:D1")
    delta = option.apply(game.state)

    assert delta == 1
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]


def test_additional_bonus_is_two_intercept_when_acting_minion_is_titled():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=0, title="Prince"
    )
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    option = next(o for o in options if o.choice.value == "protection_racket:D1")
    delta = option.apply(game.state)

    assert delta == 2


def test_bonus_is_recomputed_live_per_offer_not_cached():
    """[ANK 20190416]: "The additional intercept is gained or lost if the
    acting vampire changes sect during the action" -- the engine has no
    sect-mutation mechanism yet (neither The Red Question nor Mask of a
    Thousand Faces is implemented; `CryptCard.sect`/`title` are frozen
    identity fields, module docstring), so this is checked the only way
    currently reachable: the bonus must be derived fresh on every single
    `offer()` call from whichever acting vampire is passed in that call's own
    context, not memoized once per card/provider."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0).ready_vampire(
        "A2", capacity=5, blood=0, title="Prince"
    )
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    untitled_options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    titled_options = _offer(game, defender="P2", actor="P1", acting_vampire="A2")

    untitled_delta = next(
        o for o in untitled_options if o.choice.value == "protection_racket:D1"
    ).apply(game.state)
    titled_delta = next(
        o for o in titled_options if o.choice.value == "protection_racket:D1"
    ).apply(game.state)

    assert untitled_delta == 1
    assert titled_delta == 2


# --- "A minion cannot play the same reaction card more than once during a
# single action (even if using a different Discipline level)" --------------


def test_same_reacting_vampire_not_offered_twice_in_the_same_action():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    pending: dict = {}
    first = _offer(game, defender="P2", actor="P1", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in first} == {"protection_racket:D1"}
    next(o for o in first if o.choice.value == "protection_racket:D1").apply(game.state)

    assert "D1" in pending[USED_BY_KEY]
    second = _offer(game, defender="P2", actor="P1", acting_vampire="A1", pending=pending)
    assert second == []  # D1 already played this card once this action.


def test_a_different_eligible_vampire_is_still_offered_after_the_first_is_used():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0).ready_vampire(
        "D2", capacity=3, blood=0
    )
    _set_sect(p2, "D1", Sect.ANARCH)
    _set_sect(p2, "D2", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    pending: dict = {}
    first = _offer(game, defender="P2", actor="P1", acting_vampire="A1", pending=pending)
    next(o for o in first if o.choice.value == "protection_racket:D1").apply(game.state)

    second = _offer(game, defender="P2", actor="P1", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in second} == {"protection_racket:D2"}


# --- "A reaction card does not lock the minion playing it." ----------------


def test_playing_the_card_does_not_lock_the_reacting_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("D1", capacity=3, blood=0)
    _set_sect(p2, "D1", Sect.ANARCH)
    p2.hand.append(_protection_racket_card())
    game = builder.build()

    options = _offer(game, defender="P2", actor="P1", acting_vampire="A1")
    next(o for o in options if o.choice.value == "protection_racket:D1").apply(game.state)

    assert game.vampire("D1").locked is False
