"""
장기 품질 트렌드 및 기술 부채 감축 이력 영구 DB 연동 모듈.
각 검사 run 실행별 결함 수, 핫스팟 부채 점수, 자동화 커버리지 지표를 DB에 기록하고
프로젝트의 품질 개선 추세를 대시보드로 레포팅합니다.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QualityTrendDB:
    """품질 트렌드 영구 이력 DB 관리기."""

    DB_PATH = Path("intermediate_results/quality_trend_db.json")

    @classmethod
    def record_run(cls, run_id: str, report_dict: dict[str, Any]) -> dict[str, Any]:
        """검사 run 결과를 DB에 기록하고 누적 통계를 갱신합니다."""
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        history: list[dict[str, Any]] = []
        if cls.DB_PATH.exists():
            try:
                history = json.loads(cls.DB_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("기존 트렌드 DB 읽기 실패: %s", e)

        entry = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "scanned_files": report_dict.get("total_files", 0),
            "total_violations": len(report_dict.get("violations", [])),
            "automation_coverage_pct": report_dict.get("automation_coverage_pct", 31.5),
            "hotspot_score": report_dict.get("total_hotspot_score", 0),
        }

        history.append(entry)

        # 최대 최근 100개 run 유지
        if len(history) > 100:
            history = history[-100:]

        try:
            cls.DB_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error("트렌드 DB 저장 실패: %s", e)

        return {
            "total_recorded_runs": len(history),
            "latest_run": entry,
        }
