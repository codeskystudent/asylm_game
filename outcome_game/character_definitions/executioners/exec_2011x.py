EXECUTIONER_X2011 = {
    "id": "X2011",
    "display_name": "2011X",
    "role": "Executioner",
    "base_walk_speed": 268.0,
    "max_health": 200.0,
    "abilities": (
        {
            "id": "basic_hit",
            "name": "Basic Hit",
            "cooldown": 0.85,
            "range": 55.0,
            "server_behavior_key": "killer_basic_hit",
        },
        {
            "id": "grab_charge",
            "name": "Grab Charge",
            "cooldown": 24.0,
            "range": 0.0,
            "server_behavior_key": "x2011_grab_charge",
        },
        {"id": "scream", "name": "Dread Scream", "cooldown": 22.0, "range": 200.0, "server_behavior_key": "killer_slow_aura"},
    ),
}
