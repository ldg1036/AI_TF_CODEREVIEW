#!/usr/bin/env python
"""Compatibility wrapper. Actual implementation moved to tools/ctrlpp/ctrlppcheck_wrapper.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "ctrlpp" / "ctrlppcheck_wrapper.py"
    runpy.run_path(str(target), run_name="__main__")
