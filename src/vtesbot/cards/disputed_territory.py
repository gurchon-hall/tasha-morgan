"""Disputed Territory (Political Action). krcg id 100557.

Card text (fetched via krcg 5.14+, `krcg.load()[100557].text`, 2026-10-09):
    "Choose a location and a Methuselah. Successful referendum means the
    chosen Methuselah takes control of the chosen location."

Rulings (verbatim, via krcg):
    - "Requirements do not apply when taking control of a card already in
      play." [TOM 19960226-1]
    - "If used to steal an equipment representing a location, it can be
      placed on any minion controlled by the new controller." [RTR 19960112]
    - "If used to 'change' the control of a location or equipment
      representing a location to the same Methuselah, the location cannot
      be moved to another minion controlled by the same Methuselah."
      [LSJ 19971002]
    - "Changing the controller of a location has no other effect, unless
      specified by card text. Exception: A location 'on' another controlled
      card is moved onto an appropriate card controlled by the new
      controller of the location." [RTR 19980623]
    - "Cannot be used or played if the conditions for the terms of the
      referendum cannot be met (e.g. no legal selection, insufficient
      cards/players to choose from, prohibited by card text, uniqueness,
      etc)." [LSJ 20100129] [ANK 20191228]

Status: blocked (OQ-6). This is a Political Action card: announcing it and
attempting to block it is implemented generically by
`engine/politics.py::political_action` (no card-specific engine work
needed for that part), but resolving its referendum requires the
polling-step/vote-tally/pass-fail procedure that `docs/OPEN_QUESTIONS.md`
OQ-6 leaves open, and the card additionally needs a "location" entity
concept the engine does not model at all yet (no card in the 2P pool this
pass needs a location *without* also needing OQ-6 resolved first, so that
gap is noted here rather than built speculatively).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=100557,
        name="Disputed Territory",
        status=Status.BLOCKED,
        hooks=(Hook.POLITICAL_ACTION,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
