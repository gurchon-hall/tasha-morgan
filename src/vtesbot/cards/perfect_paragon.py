"""Perfect Paragon (Action Modifier). krcg id 101387.

Card text (fetched via krcg 5.14+, `krcg.load()[101387].text`, 2026-10-09):
    "[pre] Only usable during the polling step of a political action. This
    vampire gets +3 votes.
    [PRE] Allies and younger vampires get -1 intercept."

Rulings (verbatim, via krcg):
    - "[pre] Cannot be used during a referendum that is automatically
      passing." [PIB 20150105] [LSJ 19980107]
    - "[PRE] Can be played any time during the action before resolution; a
      block attempt is not required." [LSJ 20020612]

Status: blocked (OQ-6) for the basic [pre] clause -- "the polling step of a
political action" does not exist in the engine until OQ-6 (`docs/
OPEN_QUESTIONS.md`, `engine/politics.py`) is resolved, and the "referendum
that is automatically passing" state named by its own ruling is exactly the
unresolved procedural gap OQ-6 describes. The superior [PRE] clause (an
intercept-reduction action modifier, no polling step involved) does not
depend on OQ-6 and *is* implementable against the already-wired
`"intercept_modifier"` hook (`engine/hooks.py`, `engine/action.py`) once
`card-implementer` picks this card back up -- noted here, not built, since
this pass only scaffolds hooks and registers what's genuinely blocked.
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

register(
    CardRegistration(
        krcg_id=101387,
        name="Perfect Paragon",
        status=Status.BLOCKED,
        hooks=(Hook.POLLING_STEP, Hook.INTERCEPT_MODIFIER),
        source=__name__,
        blocked_reason="OQ-6",
    )
)
