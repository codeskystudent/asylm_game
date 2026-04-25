"""When exactly one survivor is left alive on the field, they get a small speed buff and damage reduction."""

from __future__ import annotations

from outcome_game.constants import LAST_MAN_STANDING_SPEED_MULT
from outcome_game.entities import Combatant


def last_man_standing_combatant(combatants: list[Combatant]) -> Combatant | None:
    """The single survivor who is alive and not escaped, or None."""
    active = [c for c in combatants if c.team == "Survivors" and c.alive() and not c.escaped]
    if len(active) == 1:
        return active[0]
    return None


def last_man_standing_speed_mult(actor: Combatant, combatants: list[Combatant]) -> float:
    """Walk-speed multiplier; tuned with executioner base speeds so LMS does not outpace the killer."""
    if actor.team != "Survivors":
        return 1.0
    lms = last_man_standing_combatant(combatants)
    if lms is not actor:
        return 1.0
    return LAST_MAN_STANDING_SPEED_MULT


def last_man_incoming_damage_multiplier(victim: Combatant, combatants: list[Combatant]) -> float:
    """
    Extra multiplier on damage taken from the killer when last survivor.
    Sonic: no extra reduction (1.0). Metal Sonic: 50% reduction (0.5× damage).
    Others: 25% reduction (0.75× damage).
    """
    if victim.team != "Survivors":
        return 1.0
    lms = last_man_standing_combatant(combatants)
    if lms is not victim:
        return 1.0
    if victim.char_id == "Sonic":
        return 1.0
    if victim.char_id == "MetalSonic":
        return 0.5
    return 0.75
