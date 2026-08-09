"""
16_verify_raw_sample_provenance.py

verify_raw_sample_provenance.py 메인 파이프라인 래퍼 스크립트.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util

script_path = BASE_DIR / "verify_raw_sample_provenance.py"
spec = importlib.util.spec_from_file_location("verify_provenance_mod", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == "__main__":
    module.main()
