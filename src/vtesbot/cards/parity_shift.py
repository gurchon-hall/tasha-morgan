"""Parity Shift (Political Action). krcg id 101353.

Card text (fetched via krcg 5.14+, `krcg.load()[101353].text`, 2026-10-09):
    "Requires a prince or justicar.
    Choose a Methuselah who has more pool than you do and allocate 3 of
    their pool among 1 or more other Methuselahs (including you).
    Successful referendum means the pool is distributed as you chose."

Rulings (verbatim, via krcg):
    - "The pool awarded can be used to play Life Boon to save the target
      from an oust." [LSJ 20100527]
    - "If the target has less than 3 pool when referendum passes, the
      Methuselah calling the referendum chooses how to distribute within the
      bounds of the terms." [LSJ 20010606]
    - "Changes in pool during the referendum (after terms are chosen) do not
      affect the outcome." [LSJ 20041004]
    - "Cannot be used or played if the conditions for the terms of the
      referendum cannot be met (e.g. no legal selection, insufficient
      cards/players to choose from, prohibited by card text, uniqueness,
      etc)." [LSJ 20100129] [ANK 20191228]

Status: blocked (OQ-6). "Requires a prince or justicar" is a title
requirement the engine can already express (`engine/cards.py::CryptCard.
title`), but announcing/resolving the referendum itself needs OQ-6 (see
`engine/politics.py::political_action` and `docs/OPEN_QUESTIONS.md` OQ-6).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=101353,
        name="Parity Shift",
        status=Status.BLOCKED,
        hooks=(Hook.POLITICAL_ACTION,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
