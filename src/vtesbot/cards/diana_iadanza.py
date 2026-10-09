"""Diana Iadanza (crypt vampire ability). krcg id 201694.

Printed text (fetched via krcg 5.14+, `krcg.load()[201694].text`,
2026-10-09): "Camarilla Toreador Justicar: During a referendum she calls,
Diana can burn 1 blood to cancel a reaction card as it is played (cost is
still paid). +1 bleed." Clan Toreador, title Justicar, group 7, capacity 9.

Two separate printed clauses (period-separated):
1. "During a referendum she calls, Diana can burn 1 blood to cancel a
   reaction card as it is played (cost is still paid)." -- doubly gated:
   (a) needs the referendum mechanism itself (OQ-6) plus a way to track
   *which* vampire called the current referendum (not modeled yet); (b) the
   reflex-cancellation mechanic ("cancel a card as it is played", Rulebook
   SS2) has no engine hook yet either -- no other card in this pool's
   classification needs it, so it is noted here rather than built
   speculatively.
2. "+1 bleed" -- a flat, unconditional bonus whenever Diana bleeds; this
   clause alone *would* be implementable next against the already-wired,
   mandatory `"bleed_amount_fixed_modifier"` hook (`engine/hooks.py`,
   `engine/phases/minion.py`), with no OQ-6 dependency.

The whole card is registered `blocked` because a single registry entry
carries one status for the whole effect module (`src/vtesbot/cards/
registry.py`); splitting one printed ability across two registry entries
would misrepresent "one card = one registration" (CLAUDE.md SS6). A future
`card-implementer` pass may choose to implement clause 2 now and leave
clause 1 raising `UnresolvedRulingError("OQ-6")`, re-registering this module
as `implemented` once both clauses are covered by tests.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201694,
        name="Diana Iadanza",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP, Hook.CANCEL_AS_PLAYED, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
