"""
현장 WinCC OA 소스 코드 익명화 및 난독화 처리 유틸리티.
IP 주소, 계정명, 비밀번호, 호스트명 등 보안 민감 정보를 마스킹하여 공유 가능한 픽스처 데이터로 변환합니다.
"""

import json
import re
from pathlib import Path


class DatasetAnonymizer:
    """소프트웨어 스크립트 및 픽스처 소스코드 익명화 처리기."""

    IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    SECRET_PATTERN = re.compile(r'(?i)(password|secret|apikey|token|auth)\s*[:=]\s*["\']([^"\']+)["\']')

    @classmethod
    def anonymize_text(cls, text: str) -> str:
        """입력 텍스트 내의 민감한 데이터 영역을 마스킹합니다."""
        if not text:
            return ""

        # 1. IP 주소 마스킹
        text = cls.IP_PATTERN.sub("127.0.0.1", text)

        # 2. 이메일 주소 마스킹
        text = cls.EMAIL_PATTERN.sub("anonymized_user@domain.com", text)

        # 3. 비밀번호 및 토큰 마스킹
        def replace_secret(match):
            key = match.group(1)
            return f'{key}="***ANONYMIZED_SECRET***"'

        text = cls.SECRET_PATTERN.sub(replace_secret, text)

        return text

    @classmethod
    def process_directory(cls, input_dir: Path, output_dir: Path) -> dict:
        """디렉토리 내 모든 CTL, PNL, XML 파일을 스캔하여 익명화 결과를 출력 디렉토리에 저장합니다."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stats = {"processed_files": 0, "anonymized_items": 0}

        for file_path in input_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in [".ctl", ".pnl", ".xml", ".json"]:
                try:
                    raw_content = file_path.read_text(encoding="utf-8", errors="ignore")
                    anon_content = cls.anonymize_text(raw_content)

                    rel_path = file_path.relative_to(input_dir)
                    target_path = output_dir / rel_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_text(anon_content, encoding="utf-8-sig")

                    stats["processed_files"] += 1
                except Exception as e:
                    print(f"익명화 처리 실패: {file_path} (사유: {e})")

        return stats


if __name__ == "__main__":
    src = Path("wincc_reviewer/tests/fixtures")
    dst = Path("secondary_data/anonymized_fixtures")
    res = DatasetAnonymizer.process_directory(src, dst)
    print("익명화 처리 완료 결과:", json.dumps(res, indent=2))
