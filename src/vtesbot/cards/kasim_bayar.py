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
(Queen Anne's own original stub, before RUL-005/`DIABLERIE_HOOK` existed), a
trivially-implementable trailing clause does not get wired ahead of the
card's primary ability.

Engine support for clause (2) exists (ENG-046): `combat_state` reaches
`BEFORE_RANGE_HOOK`/`COMBAT_STRENGTH_MODIFIER_HOOK` and every strike path
via `engine/combat.py::hand_strike_strength`. What remains is card work: a
`BEFORE_RANGE_HOOK` provider discarding a political action card from hand,
plus a `COMBAT_STRENGTH_MODIFIER_HOOK` provider reading the recorded flag.
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
            "not yet implemented: clause (2) needs its BEFORE_RANGE_HOOK/"
            "COMBAT_STRENGTH_MODIFIER_HOOK provider pair; engine support exists (ENG-046)"
        ),
    )
)
