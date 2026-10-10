"""Enchant Kindred (Action). krcg id 100640.

Card text (verbatim, via the installed `krcg` package,
`VTES['Enchant Kindred'].card_text`, and cross-checked against the live
`https://api.krcg.org/card/100640`, 2026-10-10; raw snapshot
`data/cards/100640.json`):
    "[pre] Ⓓ Bleed with +1 bleed.
    [PRE] +1 stealth action. Add 2 blood to a younger vampire in your
    uncontrolled region."

Rulings: none on file -- `rulings == []` both via the installed `krcg`
package and the live API (checked 2026-10-10).

Card type: Action (`types == ["Action"]`, *not* "Action Modifier").
`discipline_requirement == {"type": "Mono", "disciplines": ["pre"]}` (basic
Presence required to play the card at all; superior Presence, printed
uppercase "PRE" on a `CryptCard`, additionally unlocks the second clause --
Rulebook SS3 "Discipline symbol within a diamond ... may opt to use either
the basic (plain text) or the superior (bold) effect ... but not both").
`clan_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`.

"Ⓓ" (basic clause): the rulebook glossary's own "Directed Action" entry
(`data/sources/rulebook/2026-10-09/8-glossaries.md:59`) -- the basic clause
is a *directed* bleed, amount 2 (the default 1, +1 printed) instead of the
usual undecorated 1. The superior clause ("+1 stealth action. Add 2 blood to
a younger vampire in your uncontrolled region") carries no "Ⓓ" marker and
names no target Methuselah at all -- an *undirected* action per the
glossary's adjacent "Undirected Action" entry (same file, line 197); its
only effect touches the acting player's own uncontrolled region. Both
shapes already collapse to the engine's existing single-opponent
block-attempt model for a 2P duel (`engine/action.py`'s own module
docstring; not OQ-1, which is scoped to unsettled card wording, not this
already-settled structural collapse), so neither clause raises a fresh
prey/predator question.

"a younger vampire" (superior clause): names no explicit comparison target.
See `docs/OPEN_QUESTIONS.md` OQ-17's own note -- flagged there as a
textual-convention point for whoever unblocks this card next (not itself
the reason this card is blocked).

Status: blocked (OQ-17, `docs/OPEN_QUESTIONS.md`). `types == ["Action"]`
means the card itself is the acting vampire's one minion action for the
turn, not a modifier layered onto an already-chosen default action. The
engine has no generic entry point letting a library card inject a new,
self-contained minion action alongside the built-in "Bleed"/"Hunt" choices
at `engine/phases/minion.py::_choose_and_perform_action` -- the only such
splice point today, `"recruit_ally_play"` (OQ-12), is Ally-specific (its
`apply()` contract returns an `engine/allies.py::RecruitAllySpec`, not a
bleed/undirected-action shape). Misusing `"bleed_amount_modifier"`/
`"bleed_amount_fixed_modifier"` to fake this card as an Action Modifier
atop a separately-chosen, free default Bleed would both mis-type the card
and (for the basic clause) wrongly let a player bleed for free and
*additionally* get Enchant Kindred's bonus, when the real text is itself
the only bleed the vampire's action performs. Building a new top-level
choice/call site inside this module by reaching into
`engine/phases/minion.py` directly would be exactly the "hack around a
missing engine mechanism inside the card module" CLAUDE.md forbids. Per
CLAUDE.md §6 (a card is implemented or blocked as a whole, never partially),
both clauses stay blocked together pending OQ-17's `"action_card_play"`
hook (`Hook.ACTION_CARD_PLAY`, `src/vtesbot/cards/registry.py` -- named for
classification only; no engine wiring exists yet).
"""

from vtesbot.cards.registry import CardRegistration, Hook, Status, register

KRCG_ID = 100640

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Enchant Kindred",
        status=Status.BLOCKED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
        blocked_reason="OQ-17",
    )
)
