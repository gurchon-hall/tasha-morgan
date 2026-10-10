"""Marcos Belegrad (crypt vampire ability). krcg id 201702.

Printed text (fetched via krcg 5.14+, `krcg.load()[201702].text`,
2026-10-09): "Camarilla Prince of Bogota: Methuselahs casting (including
controlling a minion casting) votes or ballots against a referendum called
by Marcos burn 1 pool once results are tallied." Clan Toreador, title
Prince, group 7, capacity 8.

Status: blocked (OQ-6). The referendum/vote-tally mechanism itself is now
built (`engine/politics.py::resolve_referendum`/`_cast_votes`), and a
mandatory, non-chosen "burn 1 pool once results are tallied" reaction now
has a real dispatch site to register against:
`engine/politics.py::REFERENDUM_TALLIED_HOOK`
(`cards/registry.py::Hook.REFERENDUM_TALLIED`), fired via `hooks.
run_effects` immediately after `_cast_votes` returns, before the
referendum's own pass/fail effects take place -- matching this card's own
"once results are tallied" timing, and distinct from Voter Captivation's own
`Hook.REFERENDUM_RESOLVED` (fully post-resolution, materially later). A
provider would inspect `context["casts"]` for entries cast "against" and
`context["caller_vampire"]` to confirm the referendum was specifically
called by *this* Marcos instance (not just by this card's controller, who
might also control some other titled vampire), then call `lose_pool` on
each such caster directly (no `Decision`: the pool loss is mandatory per the
card's own text). Still blocked only because no provider has been wired for
this card itself yet -- that remains `card-implementer`'s job.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=201702,
        name="Marcos Belegrad",
        status=Status.BLOCKED,
        hooks=(Hook.REFERENDUM_TALLIED,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
