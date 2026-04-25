"""Last-man-standing music per survivor (local files; pygame cannot stream YouTube).

Sonic — export to: assets/lms_sonic.ogg | .mp3 | .wav
  Source: https://www.youtube.com/watch?v=v9mpurIWUaE

Knuckles — export to: assets/lms_knuckles.ogg | .mp3 | .wav
  Source: https://www.youtube.com/watch?v=EOQt4tQFf_A
"""

from __future__ import annotations

from pathlib import Path

import pygame

from outcome_game.constants import DEFAULT_ROUND_SECONDS
from outcome_game.entities import Combatant

LMS_SONIC_SOURCE_URL = "https://www.youtube.com/watch?v=v9mpurIWUaE"
LMS_KNUCKLES_SOURCE_URL = "https://www.youtube.com/watch?v=EOQt4tQFf_A"

_SONIC_NAMES = ("lms_sonic.ogg", "lms_sonic.mp3", "lms_sonic.wav")
_KNUCKLES_NAMES = ("lms_knuckles.ogg", "lms_knuckles.mp3", "lms_knuckles.wav")

_prev_lms_track_key: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_sonic_lms_track() -> Path | None:
    root = _project_root()
    for name in _SONIC_NAMES:
        p = root / "assets" / name
        if p.is_file():
            return p
    return None


def find_knuckles_lms_track() -> Path | None:
    root = _project_root()
    for name in _KNUCKLES_NAMES:
        p = root / "assets" / name
        if p.is_file():
            return p
    return None


def _ensure_mixer() -> None:
    if pygame.mixer.get_init() is None:
        pygame.mixer.init()


def _sound_length_seconds(path: Path) -> float:
    _ensure_mixer()
    sound = pygame.mixer.Sound(str(path))
    return max(1.0, float(sound.get_length()))


def get_round_duration_seconds(combatants: list[Combatant]) -> float:
    """
    Round length: if Sonic or Knuckles is in the roster and their LMS file exists, use the
    max of those track lengths; otherwise DEFAULT_ROUND_SECONDS (3:00).
    """
    survivors = [c for c in combatants if c.team == "Survivors"]
    ids = {c.char_id for c in survivors}
    lengths: list[float] = []
    if "Sonic" in ids:
        p = find_sonic_lms_track()
        if p is not None:
            try:
                lengths.append(_sound_length_seconds(p))
            except Exception:
                pass
    if "Knuckles" in ids:
        p = find_knuckles_lms_track()
        if p is not None:
            try:
                lengths.append(_sound_length_seconds(p))
            except Exception:
                pass
    if lengths:
        return max(lengths)
    return float(DEFAULT_ROUND_SECONDS)


def reset_lms_music_state() -> None:
    global _prev_lms_track_key
    _prev_lms_track_key = None
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


def tick_lms_music(combatants: list[Combatant]) -> None:
    """Play the matching LMS track when Sonic or Knuckles is sole survivor; stop otherwise."""
    global _prev_lms_track_key

    from outcome_game.last_man_standing import last_man_standing_combatant

    lms = last_man_standing_combatant(combatants)
    desired: str | None = None
    if lms is not None:
        if lms.char_id == "Sonic" and find_sonic_lms_track():
            desired = "sonic"
        elif lms.char_id == "Knuckles" and find_knuckles_lms_track():
            desired = "knuckles"

    _ensure_mixer()

    if desired == _prev_lms_track_key:
        return

    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

    if desired == "sonic":
        p = find_sonic_lms_track()
        if p:
            try:
                pygame.mixer.music.load(str(p))
                pygame.mixer.music.play(-1)
            except Exception:
                pass
    elif desired == "knuckles":
        p = find_knuckles_lms_track()
        if p:
            try:
                pygame.mixer.music.load(str(p))
                pygame.mixer.music.play(-1)
            except Exception:
                pass

    _prev_lms_track_key = desired
