"""
Standalone game client for this project: Python + pygame only.

All gameplay, UI, AI, and abilities live under `outcome_game/`. This is not a
Roblox experience — run this file to launch the desktop client:

    python client.py
"""

from __future__ import annotations


def main() -> None:
    from outcome_game.main import main as run_game

    run_game()


if __name__ == "__main__":
    main()
