#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(command):
    print(f"[local-quality-gate] {' '.join(command)}")
    result = subprocess.run(command, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    run_step([sys.executable, "tools/release_gate.py", "--profile", "ci"])
    run_step(["node", "--check", "frontend/renderer.js"])
    run_step(["node", "--check", "frontend/renderer/app-shell.js"])
    run_step(["node", "--check", "frontend/renderer/app-state.js"])
    run_step(["node", "--check", "frontend/renderer/rules-manage.js"])
    run_step(["node", "--check", "frontend/renderer/rules-manage-helpers.js"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
