"""
verify_raw_sample_provenance.py

WinCC OA 원본 소스 샘플의 출처 및 무결성 CI 게이트 검증 스크립트.
존재성, 매니페스트 출처 등록 여부, 라이선스 화이트리스트 검합성,
SHA256 일치 여부 및 단일 출처 40% 이하 분포 조건을 자동 검사합니다.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = BASE_DIR / "intermediate_results" / "raw_samples_manifest.json"
SAMPLES_DIR = BASE_DIR / "primary_data" / "raw_web_samples"

LICENSE_WHITELIST = {
    "MIT",
    "Apache_2.0",
    "BSD_2_Clause",
    "BSD_3_Clause",
    "GPLv2",
    "GPLv3",
    "CC_BY_4.0",
    "CC_BY"
}


def compute_sha256_file(file_path: Path) -> str:
    """파일의 SHA256 해시를 계산합니다."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_provenance() -> bool:
    """출처 및 존재성 무결성을 검증합니다."""
    print("=== 원본 소스 무결성 및 출처 검증 게이트 시작 ===")

    # 1. 매니페스트 존재 유무 확인
    if not MANIFEST_PATH.exists():
        print(f"FAIL: 매니페스트 파일이 존재하지 않습니다: {MANIFEST_PATH}")
        return False

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    if not entries:
        print("FAIL: 매니페스트 내 등록된 엔트리가 존재하지 않습니다.")
        return False

    total_count = len(entries)
    repo_counts = {}
    is_all_passed = True

    print(f"등록된 총 원본 샘플 건수: {total_count}개")

    for idx, entry in enumerate(entries, 1):
        basename = entry.get("source_file_basename")
        rel_path = entry.get("relative_path")
        license_type = entry.get("license")
        expected_sha256 = entry.get("sha256")
        origin_repo = entry.get("origin_repo")
        synthetic = entry.get("synthetic", False)

        # 2. 합성 데이터 혼입 검사
        if synthetic:
            print(f"FAIL: 엔트리 #{idx} ({basename}) 에 synthetic: true 혼입 감지!")
            is_all_passed = False

        # 3. 로컬 파일 존재성 검사
        target_file = BASE_DIR / rel_path if rel_path else SAMPLES_DIR / basename
        if not target_file.exists():
            print(f"FAIL: 엔트리 #{idx} ({basename}) 로컬 실제 파일 미존재: {target_file}")
            is_all_passed = False
            continue

        # 4. 라이선스 화이트리스트 검사
        if not license_type or license_type not in LICENSE_WHITELIST:
            print(f"FAIL: 엔트리 #{idx} ({basename}) 무효 라이선스: {license_type}")
            is_all_passed = False

        # 5. SHA256 변조 검사
        actual_sha256 = compute_sha256_file(target_file)
        if actual_sha256 != expected_sha256:
            print(f"FAIL: 엔트리 #{idx} ({basename}) SHA256 불일치! (기록: {expected_sha256}, 실제: {actual_sha256})")
            is_all_passed = False

        if origin_repo:
            repo_counts[origin_repo] = repo_counts.get(origin_repo, 0) + 1

    # 6. 단일 출처 비중 40% 이하 분포 조건 검사
    for repo, count in repo_counts.items():
        ratio = count / total_count
        if ratio > 0.40:
            print(f"FAIL: 단일 출처 비중 40% 초과 위반: {repo} -> {count}/{total_count} ({ratio * 100:.1f}%)")
            is_all_passed = False

    if is_all_passed:
        print("PASS: 모든 원본 파일 존재성, 라이선스, SHA256, 출처 분포 검증 완료!")
        return True
    else:
        print("FAIL: 원본 소스 무결성 검증 실패 항목이 존재합니다.")
        return False


def main():
    success = verify_provenance()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
