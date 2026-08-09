"""
build_golden_set_v3_manifest.py

골든셋 v3 사전 봉인(Pre-registration) 매니페스트 생성 및 SHA256 검증 스크립트.
데이터셋 수정 시 봉인 해시가 일치하지 않으면 평가를 즉시 중단시킵니다.
"""

import hashlib
import json
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
v3_dataset_file = base_dir / "intermediate_results" / "golden_set_v3" / "golden_set_v3_samples.json"
manifest_file = base_dir / "intermediate_results" / "golden_set_v3_manifest.json"


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def create_manifest() -> str:
    if not v3_dataset_file.exists():
        print(f"오류: 골든셋 v3 샘플 데이터셋 파일이 존재하지 않습니다: {v3_dataset_file}")
        sys.exit(1)

    sha256_hash = compute_sha256(v3_dataset_file)
    manifest_data = {
        "pre_registration_metadata": {
            "seal_timestamp": "2026-08-09T09:30:00Z",
            "version": "v3.0.0",
            "status": "SEALED",
            "sha256_hash": sha256_hash,
            "target_file": "intermediate_results/golden_set_v3/golden_set_v3_samples.json"
        }
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print(f"골든셋 v3 사전 봉인 완수 (SHA256: {sha256_hash[:16]}...): {manifest_file}")
    return sha256_hash


def verify_manifest() -> bool:
    if not manifest_file.exists() or not v3_dataset_file.exists():
        print("오류: 매니페스트 또는 데이터셋 파일이 존재하지 않습니다.")
        return False

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    expected_hash = manifest.get("pre_registration_metadata", {}).get("sha256_hash")
    actual_hash = compute_sha256(v3_dataset_file)

    if expected_hash != actual_hash:
        print(f"오류: 골든셋 v3 사전 봉인 해시 불일치 (봉인값: {expected_hash[:16]}..., 실측값: {actual_hash[:16]}...) — 평가 무효!")
        return False

    print("성공: 사전 봉인(Pre-registration) 무결성 검증 통과!")
    return True


if __name__ == "__main__":
    create_manifest()
    verify_manifest()
