"""Cross-card "(limited)" additional-strike cap -- Dust Up (100597) + Side
Strike (101778), two real, already-implemented cards (resolves
`docs/OPEN_QUESTIONS.md` OQ-19).

SS8 glossary / `engine/combat.py` module docstring: "A minion cannot use
more than one card or effect to gain additional strikes per round of
combat" is a *cross-card* cap. Before this pass, `cards/dust_up.py` and
`cards/side_strike.py` each tracked their own clause's "(limited)" use in a
private, per-card, per-vampire-*instance* dict -- nothing stopped a single
vampire holding both cards from using *both* cards' "(limited)" grants in
the same round, a real illegal-play gap. This file proves the fix with the
two real cards together, not fakes (a generic, fake-provider version of the
same mechanism lives in
`tests/rules/test_combat_dodge_and_additional_strike.py::
test_additional_strike_limit_is_shared_across_two_unrelated_providers`), and
in both play orders (Dust Up then Side Strike, and the reverse), since the
cap gates symmetrically regardless of which card is played first. This is
the within-one-vampire case specifically; the cap must *not* extend across
two different vampires each holding their own, unrelated "(limited)" card
(`test_additional_strike_limit_is_independent_per_combatant`, same test
module as above -- a `rules-auditor` regression finding on this fix's first
landing).
"""

from helpers import ScenarioBuilder
from vtesbot.cards.dust_up import KRCG_ID as DUST_UP_ID
from vtesbot.cards.side_strike import KRCG_ID as SIDE_STRIKE_ID
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.combat import COMBAT_ADDITIONAL_STRIKE_HOOK, COMBAT_DODGE_OPTION_HOOK


def _dust_up_card() -> LibraryCard:
    return LibraryCard(krcg_id=DUST_UP_ID, name="Dust Up", card_type="combat")


def _side_strike_card() -> LibraryCard:
    return LibraryCard(krcg_id=SIDE_STRIKE_ID, name="Side Strike", card_type="combat")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Mirrors `test_dust_up.py::_set_sect` (neither `ready_vampire`/
    `uncontrolled_vampire` has a `sect=` parameter, and `CryptCard` is
    frozen, so a fresh instance is swapped in, preserving every other
    field)."""
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


def test_dust_up_cel_grant_blocks_side_strike_cel_additional_strike_in_the_same_round():
    """V1 holds both cards and has superior Celerity (satisfies Dust Up's
    basic-or-superior `[cel]` check and Side Strike's superior-only `[CEL]`
    check) and is an Anarch (Dust Up's own "Requires an Anarch" gate). Dust
    Up's `[cel]` dodge-bundled grant is played first (the normal strike);
    Side Strike's own, otherwise entirely independent, `[CEL]` grant must
    then be unavailable for the rest of this round -- even though Side
    Strike's own clause has never itself been played or consulted."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    round_state: dict = {}

    # Before Dust Up's grant is played, Side Strike's own "(limited)" clause
    # is legal on its own (sanity check that the two cards are independently
    # wired correctly, before proving the interaction).
    before = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=dict(round_state),
    )
    assert {o.choice.value for o in before} == {"side_strike:additional_strike"}

    dodge_options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    dust_up_cel = next(o for o in dodge_options if o.choice.value == "dust_up:cel")
    dust_up_cel.apply(game.state)  # Dust Up's [cel]: dodge + grant, marks the shared limit used.

    after = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    values = {o.choice.value for o in after}

    assert "dust_up:cel_additional_strike" in values  # claiming Dust Up's own recorded grant
    assert "side_strike:additional_strike" not in values  # Side Strike's grant is now blocked
    assert len(game.state.players["P1"].hand) == 1  # Side Strike's own copy stayed unused in hand


def test_side_strike_cel_grant_blocks_dust_up_cel_grant_in_the_same_round():
    """Reverse order of the test above (`rules-auditor`-flagged minor gap,
    same OQ-19 pass): the cap must gate symmetrically, regardless of which
    card is played first -- Side Strike's own `[CEL]` grant, played first,
    must block Dust Up's own dodge-bundled `[cel]` grant for the rest of the
    round too."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    p1.hand.append(_side_strike_card())
    p1.hand.append(_side_strike_card())  # a second copy: one is consumed by the [CEL] play below,
    # leaving one still in hand so the dodge clause's own "card in hand" gate (unrelated to this
    # test) does not itself explain a later absence of `side_strike:dodge`.
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    round_state: dict = {}

    # Before Side Strike's grant is played, Dust Up's own [cel] clause is
    # legal on its own (sanity check). Side Strike's own plain `[cel]` dodge
    # (unrelated to the "(limited)" additional-strike cap) is also offered
    # here, since superior Celerity satisfies its basic-or-superior check.
    before = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=dict(round_state),
    )
    assert {o.choice.value for o in before} == {"dust_up:cel", "side_strike:dodge"}

    extra_options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    side_strike_extra = next(
        o for o in extra_options if o.choice.value == "side_strike:additional_strike"
    )
    side_strike_extra.apply(game.state)  # Side Strike's [CEL]: marks the shared limit used.

    after = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    values = {o.choice.value for o in after}

    assert "dust_up:cel" not in values  # Dust Up's grant is now blocked by Side Strike's play
    assert "side_strike:dodge" in values  # unaffected: not a "(limited)" additional-strike clause
    assert len(game.state.players["P1"].hand) == 2  # Dust Up's copy + the 2nd Side Strike copy
