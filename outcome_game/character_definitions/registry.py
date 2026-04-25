from __future__ import annotations

from outcome_game.character_definitions.executioners.kollosios import EXECUTIONER_KOLLOSIOS
from outcome_game.character_definitions.executioners.exec_2011x import EXECUTIONER_X2011
from outcome_game.character_definitions.survivors.amy import SURVIVOR_AMY
from outcome_game.character_definitions.survivors.eggman import SURVIVOR_EGGMAN
from outcome_game.character_definitions.survivors.knuckles import SURVIVOR_KNUCKLES
from outcome_game.character_definitions.survivors.metal_sonic import SURVIVOR_METAL_SONIC
from outcome_game.character_definitions.survivors.sonic import SURVIVOR_SONIC
from outcome_game.character_definitions.survivors.tails import SURVIVOR_TAILS
from outcome_game.character_definitions.survivors.cream import SURVIVOR_CREAM

_CACHE: dict[str, dict] = {}


def _load() -> None:
    if _CACHE:
        return
    for d in (
        SURVIVOR_SONIC,
        SURVIVOR_TAILS,
        SURVIVOR_KNUCKLES,
        SURVIVOR_AMY,
        SURVIVOR_EGGMAN,
        SURVIVOR_METAL_SONIC,
        SURVIVOR_CREAM,
        EXECUTIONER_X2011,
        EXECUTIONER_KOLLOSIOS,
    ):
        _CACHE[d["id"]] = d


def get_definition(char_id: str) -> dict | None:
    _load()
    return _CACHE.get(char_id)


def get_all_survivor_ids() -> list[str]:
    _load()
    return sorted([k for k, v in _CACHE.items() if v["role"] == "Survivor"])


def get_all_executioner_ids() -> list[str]:
    _load()
    return sorted([k for k, v in _CACHE.items() if v["role"] == "Executioner"])
