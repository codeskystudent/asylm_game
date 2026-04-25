from __future__ import annotations

from outcome_game.constants import (
    SURVIVOR_HIT_SPEED_BOOST_MULT,
    SURVIVOR_HIT_SPEED_BOOST_SECONDS,
)
from outcome_game.entities import Combatant


def apply_survivor_hit_speed_boost(victim: Combatant, now: float) -> None:
    """Give survivors a brief strong speed burst after taking damage."""
    if victim.team != "Survivors" or not victim.alive() or victim.escaped:
        return
    victim.speed_mult_until = max(victim.speed_mult_until, now + SURVIVOR_HIT_SPEED_BOOST_SECONDS)
    victim.speed_mult = max(victim.speed_mult, SURVIVOR_HIT_SPEED_BOOST_MULT)
