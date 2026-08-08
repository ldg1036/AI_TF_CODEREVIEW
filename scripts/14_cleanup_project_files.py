"""
프로젝트 불필요 파일, 캐시 및 빈 디렉토리 안전 정리 스크립트.
"""

import logging
import os
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProjectCleanup")

base_dir = Path(__file__).resolve().parent.parent


def cleanup_project() -> None:
    """불필요 파일 및 디렉토리 안전 삭제 실행"""
    logger.info("1. 프로젝트 정리 작업 시작: %s", base_dir)

    # 1. 빈 디렉토리 및 중복 잔재 파일 정리
    empty_config_dir = base_dir / "wincc_reviewer" / "config"
    if empty_config_dir.exists() and empty_config_dir.is_dir():
        try:
            empty_config_dir.rmdir()
            logger.info("빈 디렉토리 삭제 완료: %s", empty_config_dir)
        except Exception as e:
            logger.warning("빈 디렉토리 삭제 실패: %s", e)

    dup_json = base_dir / "wincc_reviewer" / "intermediate_results" / "quality_trend_db.json"
    if dup_json.exists():
        try:
            dup_json.unlink()
            logger.info("중복 잔재 파일 삭제 완료: %s", dup_json)
        except Exception as e:
            logger.warning("중복 잔재 파일 삭제 실패: %s", e)

    # 2. 캐시 디렉토리 (.pytest_cache, __pycache__) 정리
    for root, dirs, files in os.walk(base_dir):
        root_path = Path(root)
        if ".git" in root_path.parts or "venv" in root_path.parts:
            continue

        for d in list(dirs):
            if d in (".pytest_cache", "__pycache__"):
                dir_to_remove = root_path / d
                try:
                    shutil.rmtree(dir_to_remove)
                    logger.info("캐시 디렉토리 정리 완료: %s", dir_to_remove)
                except Exception as e:
                    logger.warning("캐시 디렉토리 정리 실패: %s", e)

    # 3. output/ 디렉토리 내 임시 누적 run 리포트 파일 정리 (logs 폴더는 유지)
    output_dir = base_dir / "output"
    if output_dir.exists():
        cleaned_file_count = 0
        for item in output_dir.iterdir():
            if item.is_file() and (item.name.endswith(".html") or item.name.endswith(".json")):
                try:
                    item.unlink()
                    cleaned_file_count += 1
                except Exception as e:
                    logger.warning("임시 리포트 삭제 실패: %s", e)
        logger.info("output 디렉토리 임시 누적 리포트 %d개 정리 완료", cleaned_file_count)

    logger.info("프로젝트 안전 정리 작업 완료.")


if __name__ == "__main__":
    cleanup_project()
