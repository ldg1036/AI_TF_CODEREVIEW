"""
collect_raw_samples_web.py

16_collect_raw_samples_web.py 모듈 래퍼 스크립트.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util

script_16_path = BASE_DIR / "16_collect_raw_samples_web.py"
spec = importlib.util.spec_from_file_location("collect_16", script_16_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.main()
