#!/usr/bin/env python
"""Compatibility wrapper. Actual implementation moved to tools/ctrlpp/run_ctrlpp_integration_smoke.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "ctrlpp" / "run_ctrlpp_integration_smoke.py"
    runpy.run_path(str(target), run_name="__main__")
