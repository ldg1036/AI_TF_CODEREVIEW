"""
WinCC OA 코드 리뷰 자동화 도구 — 기술 부채 핫스팟 히트맵 계산기 (TRD Phase 16).

파일/모듈별 위반 빈도와 심각도 가중치를 종합하여 기술 부채 핫스팟 점수(Hotspot Score)를 산출합니다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.core.models import SeverityLevel, Violation


@dataclass
class FileHotspot:
    """단일 파일의 기술 부채 핫스팟 지표."""

    file_id: str
    hotspot_score: float
    total_violations: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    top_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "hotspot_score": self.hotspot_score,
            "total_violations": self.total_violations,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "top_rules": self.top_rules,
        }


@dataclass
class HotspotSummary:
    """프로젝트 전체 기술 부채 핫스팟 요약."""

    total_score: float
    top_hotspots: list[FileHotspot]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "top_hotspots": [h.to_dict() for h in self.top_hotspots],
        }


class HotspotCalculator:
    """심각도 가중치 기반 기술 부채 핫스팟 점수 산출기."""

    SEVERITY_WEIGHTS = {
        SeverityLevel.CRITICAL: 10.0,
        SeverityLevel.HIGH: 5.0,
        SeverityLevel.MEDIUM: 2.0,
        SeverityLevel.LOW: 1.0,
        SeverityLevel.INFO: 0.5,
    }


    @classmethod
    def get_severity_weight(cls, sev: Any) -> float:
        """심각도 Enum 또는 문자열에 대한 가중치 산출."""
        if isinstance(sev, SeverityLevel):
            return cls.SEVERITY_WEIGHTS.get(sev, 1.0)
        sev_str = str(sev).upper()
        for level, weight in cls.SEVERITY_WEIGHTS.items():
            if level.value == sev_str:
                return weight
        return 1.0

    @classmethod
    def calculate(cls, violations: list[Violation], limit: int = 10) -> HotspotSummary:
        """
        전체 위반 사항 목록에서 파일별 핫스팟 점수 및 순위를 산출합니다.

        Args:
            violations: 검출된 위반 사항 목록
            limit: 반환할 최대 상위 고위험 파일 수

        Returns:
            HotspotSummary
        """
        file_map: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "score": 0.0,
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
                "rules": defaultdict(int),
            }
        )

        total_project_score = 0.0

        for v in violations:
            f_id = v.file_id or "unknown"
            weight = cls.get_severity_weight(v.severity)
            data = file_map[f_id]

            data["score"] += weight
            data["total"] += 1
            total_project_score += weight
            data["rules"][v.rule_id] += 1

            sev_val = str(v.severity.value if isinstance(v.severity, SeverityLevel) else v.severity).upper()
            if sev_val == "CRITICAL":
                data["critical"] += 1
            elif sev_val == "HIGH":
                data["high"] += 1
            elif sev_val == "MEDIUM":
                data["medium"] += 1
            elif sev_val == "LOW":
                data["low"] += 1
            else:
                data["info"] += 1


        hotspots: list[FileHotspot] = []
        for f_id, data in file_map.items():
            # 빈도 상위 룰 3개 추출
            sorted_rules = sorted(data["rules"].items(), key=lambda item: item[1], reverse=True)
            top_rule_ids = [r[0] for r in sorted_rules[:3]]

            hotspots.append(
                FileHotspot(
                    file_id=f_id,
                    hotspot_score=round(data["score"], 2),
                    total_violations=data["total"],
                    critical_count=data["critical"],
                    high_count=data["high"],
                    medium_count=data["medium"],
                    low_count=data["low"],
                    info_count=data["info"],
                    top_rules=top_rule_ids,
                )
            )

        # 핫스팟 점수 내림차순 정렬
        hotspots.sort(key=lambda h: (h.hotspot_score, h.total_violations), reverse=True)

        return HotspotSummary(
            total_score=round(total_project_score, 2),
            top_hotspots=hotspots[:limit],
        )
