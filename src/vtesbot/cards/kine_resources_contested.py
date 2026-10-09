"""Kine Resources Contested (Political Action). krcg id 101056.

Card text (fetched via krcg 5.14+, `krcg.load()[101056].text`, 2026-10-09):
    "Allocate 4 points among two or more Methuselahs. Successful referendum
    means each Methuselah burns 1 pool for each point allocated."

Rulings (verbatim, via krcg):
    - "Cannot allocate 4 points to a single Methuselah, but you can allocate
      points to yourself." [LSJ 20000622]
    - "If multiple ousts happen, players whose prey gets ousted get a
      victory point, even if they are being ousted themselves. Only the
      surviving ones get 6 pool from the oust of their prey (not of their
      grand-prey)." [LSJ 20000309]
    - "Can allocate more points than a Methuselah has pool." [LSJ 20020819]

2P note: "Allocate 4 points among two or more Methuselahs" presumes at
least two possible allocation targets; in a duel there are only ever two
Methuselahs total, which may interact with OQ-6 (how exactly a referendum
resolves between exactly two Methuselahs) -- flagged, not guessed.

Status: blocked (OQ-6). Announcing/blocking is the generic
`engine/politics.py::political_action` path (no card-specific engine work
needed there); resolving the referendum needs OQ-6.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=101056,
        name="Kine Resources Contested",
        status=Status.BLOCKED,
        hooks=(Hook.POLITICAL_ACTION,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
