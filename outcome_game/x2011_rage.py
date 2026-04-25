"""2011X: rage after many stuns — speed/damage buff, shorter stuns, round timer pause."""

from __future__ import annotations

from outcome_game.constants import (
    ARENA_H,
    ARENA_W,
    KILLER_STUN_KNOCKBACK_DISTANCE,
    KILLER_STUN_IMMUNITY_SECONDS,
    X2011_RAGE_DAMAGE_MULT,
    X2011_RAGE_DURATION_SECONDS,
    X2011_RAGE_SPEED_MULT,
    X2011_RAGE_STUN_RECEIVED_MULT,
    X2011_RAGE_STUNS_TO_ACTIVATE,
)
from outcome_game.entities import Combatant
from outcome_game.last_man_standing import last_man_standing_combatant


def _apply_stun_knockback(killer: Combatant) -> None:
    """Push stunned killer slightly backward from their current facing."""
    d = KILLER_STUN_KNOCKBACK_DISTANCE
    killer.x -= killer.facing_x * d
    killer.y -= killer.facing_y * d
    killer.x = max(killer.radius, min(ARENA_W - killer.radius, killer.x))
    killer.y = max(killer.radius, min(ARENA_H - killer.radius, killer.y))


def _last_man_standing(combatants: list[Combatant] | None) -> bool:
    if not combatants:
        return False
    return last_man_standing_combatant(combatants) is not None


def rage_active(
    killer: Combatant,
    now: float,
    combatants: list[Combatant] | None = None,
) -> bool:
    """Rage is off during last-man-standing (one survivor left alive on the field)."""
    if killer.char_id != "X2011" or killer.x2011_rage_until <= now:
        return False
    if combatants is not None and _last_man_standing(combatants):
        return False
    return True


def rage_speed_multiplier(
    killer: Combatant,
    now: float,
    combatants: list[Combatant] | None = None,
) -> float:
    return X2011_RAGE_SPEED_MULT if rage_active(killer, now, combatants) else 1.0


def rage_damage_multiplier(
    killer: Combatant,
    now: float,
    combatants: list[Combatant] | None = None,
) -> float:
    return X2011_RAGE_DAMAGE_MULT if rage_active(killer, now, combatants) else 1.0


def _bump_stun_count_and_maybe_rage(
    killer: Combatant,
    now: float,
    combatants: list[Combatant] | None = None,
) -> None:
    if killer.char_id != "X2011":
        return
    if combatants is not None and _last_man_standing(combatants):
        return
    killer.x2011_stun_count += 1
    if killer.x2011_stun_count >= X2011_RAGE_STUNS_TO_ACTIVATE:
        killer.x2011_stun_count = 0
        if killer.x2011_rage_until <= now:
            killer.x2011_rage_until = now + X2011_RAGE_DURATION_SECONDS


def apply_executioner_stun_from_now(
    killer: Combatant,
    now: float,
    duration: float,
    combatants: list[Combatant] | None = None,
) -> None:
    """Stun killer for `duration` seconds from now; stacks onto any active stun time."""
    if duration <= 0 or killer.team != "Executioners":
        return
    if now < killer.stun_immunity_until:
        return
    d = duration
    if killer.char_id == "X2011" and rage_active(killer, now, combatants):
        d *= X2011_RAGE_STUN_RECEIVED_MULT
    killer.stunned_until = max(killer.stunned_until, now) + d
    # Any stun immediately breaks active executioner grabs/channels.
    if killer.char_id == "X2011" and killer.x2011_grab_victim is not None:
        victim = killer.x2011_grab_victim
        victim.grabbed_by = None
        victim.grab_break_progress = 0.0
        killer.x2011_grab_victim = None
        killer.x2011_grab_until = 0.0
        killer.x2011_grab_charge_until = 0.0
    if killer.char_id == "Kollosios":
        if killer.kollosios_basic_grab_victim is not None:
            victim = killer.kollosios_basic_grab_victim
            victim.held_by_kollosios_basic_grab = False
            killer.kollosios_basic_grab_victim = None
            killer.kollosios_basic_grab_until = 0.0
        if killer.kollosios_grabbed_survivors:
            for s in killer.kollosios_grabbed_survivors:
                s.held_by_kollosios_charge = False
            killer.kollosios_grabbed_survivors = []
        killer.kollosios_charge_until = 0.0
    _apply_stun_knockback(killer)
    killer.stun_splash_until = max(killer.stun_splash_until, now + 0.28)
    _bump_stun_count_and_maybe_rage(killer, now, combatants)


def extend_executioner_stun(
    killer: Combatant,
    now: float,
    additional_duration: float,
    combatants: list[Combatant] | None = None,
) -> None:
    """Stack time onto stun end (e.g. Tails beam): new_end = max(stunned_until, now) + add."""
    if additional_duration <= 0 or killer.team != "Executioners":
        return
    if now < killer.stun_immunity_until:
        return
    d = additional_duration
    if killer.char_id == "X2011" and rage_active(killer, now, combatants):
        d *= X2011_RAGE_STUN_RECEIVED_MULT
    killer.stunned_until = max(killer.stunned_until, now) + d
    # Extended stun should also cancel active executioner grabs/channels.
    if killer.char_id == "X2011" and killer.x2011_grab_victim is not None:
        victim = killer.x2011_grab_victim
        victim.grabbed_by = None
        victim.grab_break_progress = 0.0
        killer.x2011_grab_victim = None
        killer.x2011_grab_until = 0.0
        killer.x2011_grab_charge_until = 0.0
    if killer.char_id == "Kollosios":
        if killer.kollosios_basic_grab_victim is not None:
            victim = killer.kollosios_basic_grab_victim
            victim.held_by_kollosios_basic_grab = False
            killer.kollosios_basic_grab_victim = None
            killer.kollosios_basic_grab_until = 0.0
        if killer.kollosios_grabbed_survivors:
            for s in killer.kollosios_grabbed_survivors:
                s.held_by_kollosios_charge = False
            killer.kollosios_grabbed_survivors = []
        killer.kollosios_charge_until = 0.0
    _apply_stun_knockback(killer)
    killer.stun_splash_until = max(killer.stun_splash_until, now + 0.28)
    _bump_stun_count_and_maybe_rage(killer, now, combatants)


def update_killer_stun_immunity(killer: Combatant, now: float) -> None:
    """After a stun fully ends, grant brief stun immunity."""
    if killer.team != "Executioners":
        return
    stunned_now = killer.stunned_until > now
    if killer.stun_active_last_tick and not stunned_now:
        killer.stun_immunity_until = max(killer.stun_immunity_until, now + KILLER_STUN_IMMUNITY_SECONDS)
    killer.stun_active_last_tick = stunned_now
