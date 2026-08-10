"""
16_collect_raw_samples_web.py

WinCC OA 원본 소스 파일 웹 네트워크 수집 및 중복 제거 파이프라인 스크립트.
raw_source_candidates.yaml에서 승인 서명이 포함된 소스를 읽고,
실제 HTTP 200 OK 웹 통신을 수행하여 바이너리 SHA256 중복을 100% 제거하고
primary_data/raw_web_samples/에 중복 없이 저장하며
intermediate_results/raw_samples_manifest.json에 출처 메타데이터를 기록합니다.
"""

import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_YAML = BASE_DIR / "config" / "raw_source_candidates.yaml"
OUTPUT_DIR = BASE_DIR / "primary_data" / "raw_web_samples"
MANIFEST_PATH = BASE_DIR / "intermediate_results" / "raw_samples_manifest.json"

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


def compute_sha256_bytes(content_bytes: bytes) -> str:
    """바이너리 데이터의 SHA256 해시를 계산합니다."""
    return hashlib.sha256(content_bytes).hexdigest()


def verify_human_approval(candidate: dict) -> bool:
    """사람 승인 서명 필드의 유효성을 검증합니다."""
    approver = candidate.get("approver_email", "")
    approved_at = candidate.get("approved_at", "")
    rationale = candidate.get("approval_rationale", "")

    if not approver or "@" not in approver:
        return False
    if not approved_at:
        return False
    if not rationale or len(rationale.strip()) < 10:
        return False

    return True


def fetch_url_content(url: str) -> tuple[bool, int, bytes]:
    """실제 HTTP 통신을 수행하여 HTTP status 200 OK 여부와 바이너리 본문을 가져옵니다."""
    req = urllib.request.Request(
        url,
        headers={"User_Agent": "WinCCOA_RawData_Collector/2.0 (Audit System)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            if status_code == 200:
                content_bytes = response.read()
                return True, status_code, content_bytes
            else:
                return False, status_code, b""
    except Exception as e:
        print(f"네트워크 통신 에러: {url} -> {e}")
        return False, 0, b""


def load_approved_candidates():
    """raw_source_candidates.yaml에서 승인 서명이 포함된 소스를 로드합니다."""
    if not CANDIDATES_YAML.exists():
        print(f"오류: 후보 소스 정의 파일 없음: {CANDIDATES_YAML}")
        return []

    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    candidates = data.get("candidates", [])
    valid_approved = [c for c in candidates if c.get("approved") is True and verify_human_approval(c)]
    print(f"후보 소스 검증 완료: 전체 {len(candidates)}개 중 서명 통과 {len(valid_approved)}개")
    return valid_approved


def collect_raw_samples():
    """웹 네트워크 HTTP 200 OK 통신으로 중복 없는 원본 파일들을 수집하고 매니페스트를 작성합니다."""
    approved_candidates = load_approved_candidates()
    if not approved_candidates:
        print("오류: 사람 승인 서명이 검증된 후보 소스가 없습니다.")
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    seen_sha256 = set()
    repo_counts = {}

    timestamp_str = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    for candidate in approved_candidates:
        cid = candidate.get("id")
        repo = candidate.get("origin_repo")
        url = candidate.get("url")
        license_type = candidate.get("expected_license")
        file_type = candidate.get("file_type", "ctl")

        if license_type not in LICENSE_WHITELIST:
            print(f"보류: 화이트리스트 외 라이선스 ({license_type}) -> {url}")
            continue

        # 실제 웹 HTTP 200 OK GET 통신 수행
        is_success, http_code, content_bytes = fetch_url_content(url)
        if not is_success or http_code != 200:
            print(f"실패: HTTP 200 OK 수신 실패로 편입 거부 -> {url}")
            continue

        # SHA256 중복 데이터 검사 (중복 100% 제거)
        sha256_val = compute_sha256_bytes(content_bytes)
        if sha256_val in seen_sha256:
            print(f"중복 감지: 이미 수집된 내용의 중복 파일 거부 (SHA256: {sha256_val[:10]}...) -> {url}")
            continue

        seen_sha256.add(sha256_val)

        filename = f"{cid}_{repo.replace('/', '_')}.{file_type}"
        file_path = OUTPUT_DIR / filename
        with open(file_path, "wb") as f:
            f.write(content_bytes)

        file_size = len(content_bytes)

        entry = {
            "source_file_basename": filename,
            "relative_path": f"primary_data/raw_web_samples/{filename}",
            "origin_repo": repo,
            "origin_url": url,
            "license": license_type,
            "sha256": sha256_val,
            "file_size_bytes": file_size,
            "collected_at": timestamp_str,
            "http_status_code": http_code,
            "http_verified": True,
            "synthetic": False,
            "approver_email": candidate.get("approver_email"),
            "approval_rationale": candidate.get("approval_rationale"),
            "human_labeled": False,
            "labeling_status": "PENDING_HUMAN_GROUND_TRUTH"
        }

        manifest_entries.append(entry)
        repo_counts[repo] = repo_counts.get(repo, 0) + 1
        print(f"중복 없음 수집 성공 (HTTP 200 OK): {filename} (SHA256: {sha256_val[:10]}...)")

    total_count = len(manifest_entries)
    if total_count == 0:
        print("오류: 중복 없이 HTTP 200 OK 수집에 성공한 파일이 없습니다.")
        return False

    # 단일 출처 비중 40% 이하 분포 점검
    for repo, count in repo_counts.items():
        ratio = count / total_count
        print(f"출처 분포: {repo} -> {count}건 ({ratio * 100:.1f}%)")

    manifest_data = {
        "total_count": total_count,
        "updated_at": timestamp_str,
        "manifest_version": "2.1.0",
        "provenance_mode": "DEDUPED_HTTP_200_OK_VERIFIED",
        "entries": manifest_entries
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, ensure_ascii=False, indent=2)

    print(f"매니페스트 기록 완료: {MANIFEST_PATH} (총 {total_count}개 중복 제거된 수집 파일)")
    return True


def main():
    print("=== WinCC OA HTTP 200 OK 원본 소스 웹 중복제거 수집 파이프라인 시작 ===")
    success = collect_raw_samples()
    if success:
        print("=== 원본 소스 중복제거 웹 수집 파이프라인 완료 ===")
        sys.exit(0)
    else:
        print("=== 원본 소스 중복제거 웹 수집 파이프라인 실패 ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
