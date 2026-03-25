#!/usr/bin/env python3
"""JoPhi's Disc Clouder — Launcher."""

import os
import sys

# Auto-restart in conda env if not already there
ENV_NAME = "disc_clouder"
if os.environ.get("CONDA_DEFAULT_ENV") != ENV_NAME:
    os.execvp("conda", ["conda", "run", "--no-capture-output", "-n", ENV_NAME, "python", *sys.argv])


def main():
    print("=== JoPhi's Disc Clouder ===")
    print()
    print("  [1] Blu-ray")
    print("  [2] DVD")
    print()
    choice = input("Choose disc type (1/2): ").strip()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    if choice == "1":
        script = os.path.join(script_dir, "BLURAY-ONLY.py")
    elif choice == "2":
        script = os.path.join(script_dir, "DVD-ONLY.py")
    else:
        print("Invalid choice.")
        sys.exit(1)

    if not os.path.exists(script):
        print(f"Not found: {script}")
        sys.exit(1)

    os.execvp(sys.executable, [sys.executable, script] + sys.argv[1:])


if __name__ == "__main__":
    main()
