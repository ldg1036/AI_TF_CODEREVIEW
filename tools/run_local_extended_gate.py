#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(command):
    print(f"[local-extended-gate] {' '.join(command)}")
    result = subprocess.run(command, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    run_step([sys.executable, "tools/run_local_quality_gate.py"])
    run_step([sys.executable, "tools/release_gate.py", "--profile", "local", "--include-ui", "--include-ctrlpp"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
