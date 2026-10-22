"""Kasim Bayar (crypt vampire ability). krcg id 201598.

Printed text (fetched via `krcg.load()` + `msgspec.json.encode()`, project's
`.venv` (krcg 5.14), 2026-10-21, matching the raw snapshot `data/cards/
201598.json`): "Camarilla Banu Haqim Justicar: Once each combat, Kasim can
discard a political action card [POLITICAL ACTION] before range is
determined to get +2 strength that combat. +1 bleed."

Rulings: none on file (`rulings == []`, confirmed in the raw snapshot).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Banu Haqim, group 6,
capacity 9, title Justicar, disciplines `("aus", "pot", "CEL", "OBF",
"THA")`. Legal since 2021-12-31; confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in the suggested 2P decklist
`data/decks/vekn-2p/banu-haqim.json` (2 copies).

Three clauses: (1) "Camarilla Banu Haqim Justicar" names sect/clan/title --
no card-specific code needed, the generic `TITLE_VOTES` machinery
(`engine/politics.py`) already handles a Justicar's vote value, same
reasoning as `cards/kevin_jackson.py`. (2) "Once each combat, Kasim can
discard a political action card ... before range is determined to get +2
strength that combat." (3) "+1 bleed" -- trivially implementable on its own
against the already-wired `bleed_amount_fixed_modifier` hook, same shape as
Queen Anne's/Diana Iadanza's own trailing "+1 bleed" clause.

Status: blocked overall on clause (2) -- CLAUDE.md "a card is implemented
only when ... each clause of the text" is covered; per that same precedent
(Queen Anne's own original stub, before OQ-6/`DIABLERIE_HOOK` existed), a
trivially-implementable trailing clause does not get wired ahead of the
card's primary ability.

Engine gap closed (updated 2026-10-22, follow-up to the rules-auditor review
of commit "feat(engine): thread combat_state into BEFORE_RANGE_HOOK/
COMBAT_STRENGTH_MODIFIER_HOOK"): `engine/combat.py` now exposes a shared
`hand_strike_strength(state, player, vampire, opponent, combat_state=None)`
helper -- the single computation every call site that needs "what a plain
hand strike deals right now" uses, instead of each re-deriving
`HAND_STRIKE_STRENGTH + hooks.sum_modifiers(COMBAT_STRENGTH_MODIFIER_HOOK,
...)` independently. `_strike_strength` (the engine's own plain-hand-strike
path) is now a thin wrapper over it, and `cards/dust_up.py`/`cards/slam.py`'s
own `_base_hand_strike_damage` and `cards/weighted_walking_stick.py`'s
`_provide_strike` all call it too, forwarding `combat_state` from their own
hook `context`. `_ask_strike` (`engine/combat.py`) also now threads
`combat_state` into `COMBAT_STRIKE_OPTION_HOOK`'s own context itself (it
previously carried only `player`/`vampire`/`opponent`), which those three
card modules' hook providers need in order to have anything to forward at
all. Proven by `tests/rules/test_combat_strength_before_range.py`'s added
cases (a fake once-per-combat `BEFORE_RANGE_HOOK`/`COMBAT_STRENGTH_
MODIFIER_HOOK` bonus, shaped like this card's clause (2), still applies when
the bonused vampire strikes via Dust Up/Slam/Weighted Walking Stick instead
of a plain hand strike).

Status remains `blocked`: clause (2) itself ("Once each combat, Kasim can
discard a political action card ... before range is determined to get +2
strength that combat") is not yet wired to this now-working primitive --
that is ordinary follow-up card-implementation work (a `BEFORE_RANGE_HOOK`
provider checking "discard a political action card from hand" plus a
`COMBAT_STRENGTH_MODIFIER_HOOK` provider reading the recorded flag, same
shape as this module's own `tests/rules/` fake pair), not an engine gap.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201598,
        name="Kasim Bayar",
        status=Status.BLOCKED,
        hooks=(Hook.BEFORE_RANGE, Hook.COMBAT_STRENGTH_MODIFIER, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
        blocked_reason=(
            "the combat_state plumbing gap is now closed (engine/combat.py::hand_strike_strength, "
            "a +2-that-combat bonus now applies through Dust Up/Slam/Weighted Walking Stick too) "
            "-- clause (2) itself (discard a political action card before range is determined for "
            "+2 strength that combat) still needs its own BEFORE_RANGE_HOOK/"
            "COMBAT_STRENGTH_MODIFIER_HOOK provider pair wired up; see card-implementer"
        ),
    )
)
