EXECUTIONER_KOLLOSIOS = {
    "id": "Kollosios",
    "display_name": "Kollosios",
    "role": "Executioner",
    # Faster than max survivor Shift-sprint (e.g. Sonic 183×1.32) and LMS+sprint (~256)
    "base_walk_speed": 260.0,
    "max_health": 220.0,
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
            "cooldown": 22.0,
            "range": 0.0,
            "server_behavior_key": "kollosios_grab_charge",
        },
        {"id": "shroud", "name": "Shroud", "cooldown": 26.0, "range": 180.0, "server_behavior_key": "killer_slow_aura"},
    ),
}
