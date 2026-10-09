"""Voter Captivation (Action Modifier). krcg id 102131.

Card text (fetched via krcg 5.14+, `krcg.load()[102131].text`, 2026-10-09):
    "Only usable after resolution of a political action whose referendum
    passed.
    [pre] This vampire gains 1 blood for each vote by which the referendum
    passed.
    [PRE] As above, but move up to 2 of those blood to your pool instead of
    this vampire."

Rulings (verbatim, via krcg):
    - "Is played after resolution, after all combats (if any) are handled,
      but still during the action. Action modifiers and effects that can be
      played 'after resolution' can be played before or after it."
      [PIB 20150915] [LSJ 19981028] [ANK 20190425]
    - "Is played after the referendum is resolved. If the effect of the
      referendum ousts the acting Methuselah, there is no time to play it to
      prevent the ousting." [RTR 19951110]
    - "Can be used after a referendum that is automatically passing, but the
      vote is considered to have passed by 0 votes." [LSJ 19980107]
      [PIB 20150105]

Status: blocked (OQ-6). Its trigger ("a political action whose referendum
passed", "by N votes") and the "automatically passing ... by 0 votes" ruling
both require the referendum pass/fail and vote-margin procedure OQ-6 leaves
open (`docs/OPEN_QUESTIONS.md`, `engine/politics.py`).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=102131,
        name="Voter Captivation",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
