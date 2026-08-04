"""
WinCC OA 코드 리뷰 자동화 도구 — 체크리스트 적용성 매퍼 (Applicability Mapper).

설계 문서 요구사항 (06_구현기준_추적성_검증기준.md §1 & §5):
- 체크리스트의 각 항목(source_key)과 실행 룰(rule_id) 간의 적용성 매핑을 검증하고,
- Client 15/15, Server 20/20 커버리지를 검증하여 ApplicabilityReport를 산출합니다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ApplicabilityItem:
    """단일 체크리스트 항목 적용성 정보."""

    source_key: str
    rule_ids: list[str] = field(default_factory=list)
    automation_mode: str = "manual"  # 'automated' | 'manual'
    status: str = "mapped"  # 'mapped' | 'unmapped' | 'manual_review'
    notes: str = ""


@dataclass
class ApplicabilityReport:
    """체크리스트 매핑 프로파일 적용성 분석 보고서."""

    profile_name: str
    total_items: int
    mapped_items: int
    manual_items: int
    items: list[ApplicabilityItem] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        """매핑 비율 (0.0 ~ 1.0)을 반환합니다."""
        if self.total_items == 0:
            return 0.0
        return (self.mapped_items + self.manual_items) / self.total_items


class ApplicabilityMapper:
    """체크리스트 적용성 매핑 검증기."""

    @classmethod
    def map_profile(cls, profile_path: Path, rule_ids_in_excel: set[str] | None = None) -> ApplicabilityReport:
        """
        yaml 매핑 프로파일을 분석하여 적용성 보고서를 생성합니다.

        Args:
            profile_path: client.yaml 또는 server.yaml 경로
            rule_ids_in_excel: Excel 파일에 실제로 존재하는 rule_id 집합 (옵션)

        Returns:
            ApplicabilityReport 객체
        """
        if not profile_path.exists():
            raise FileNotFoundError(f"매핑 프로파일 파일을 찾을 수 없습니다: {profile_path}")

        with open(profile_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        profile_name = str(data.get("profile", profile_path.stem))
        entries = data.get("entries", data.get("mappings", []))
        if isinstance(entries, dict):
            entry_list = [{"source_key": k, **v} for k, v in entries.items()]
        else:
            entry_list = entries

        items: list[ApplicabilityItem] = []
        mapped_count = 0
        manual_count = 0

        for meta in entry_list:
            source_key = meta.get("source_key", "")
            rule_ids = meta.get("rule_ids", [])
            automation_mode = meta.get("automation_mode", "manual")
            notes = meta.get("notes", meta.get("condition_summary", ""))

            status = "mapped"
            if automation_mode == "manual" or not rule_ids:
                status = "manual_review"
                manual_count += 1
            else:
                if rule_ids_in_excel is not None:
                    # 엑셀 내 룰 존재 여부 검사
                    if all(rid in rule_ids_in_excel for rid in rule_ids):
                        status = "mapped"
                        mapped_count += 1
                    else:
                        status = "unmapped"
                else:
                    status = "mapped"
                    mapped_count += 1

            item = ApplicabilityItem(
                source_key=source_key,
                rule_ids=list(rule_ids),
                automation_mode=automation_mode,
                status=status,
                notes=str(notes),
            )
            items.append(item)

        total_items = len(items)
        logger.info("적용성 매핑 분석 완료 [%s]: 총 %d항목 (매핑:%d, 수동:%d)", profile_name, total_items, mapped_count, manual_count)
        return ApplicabilityReport(
            profile_name=profile_name,
            total_items=total_items,
            mapped_items=mapped_count,
            manual_items=manual_count,
            items=items,
        )

    @classmethod
    def verify_coverage(cls, report: ApplicabilityReport, expected_total: int) -> bool:
        """
        적용성 보고서의 항목 수 및 커버리지가 계약 조건을 만족하는지 검증합니다.

        Args:
            report: 검증할 적용성 보고서
            expected_total: 기대 항목 수 (Client: 15, Server: 20)

        Returns:
            검증 성공 여부 (bool)
        """
        if report.total_items != expected_total:
            logger.error("적용성 매핑 수 불일치 [%s]: expected=%d, actual=%d", report.profile_name, expected_total, report.total_items)
            return False

        if report.coverage_ratio < 1.0:
            logger.error("적용성 매핑 커버리지 미달 [%s]: %.2f%%", report.profile_name, report.coverage_ratio * 100)
            return False

        return True

    @classmethod
    def to_checklist_applicability(
        cls, report: ApplicabilityReport, rule_ids_in_excel: set[str] | None = None
    ) -> list[Any]:
        """
        ApplicabilityReport를 모델 계약의 ChecklistApplicability 목록으로 변환합니다.

        Args:
            report: 적용성 분석 보고서
            rule_ids_in_excel: Excel 내 존재하는 룰 ID 집합 (옵션)

        Returns:
            list[ChecklistApplicability]
        """
        from app.core.models import AutomationMode, ChecklistApplicability

        results: list[ChecklistApplicability] = []
        for item in report.items:
            mode_map = {
                "automated": AutomationMode.AUTO_FULL,
                "manual": AutomationMode.MANUAL,
            }
            mode = mode_map.get(item.automation_mode.lower(), AutomationMode.AUTO_VIOLATION_ONLY)

            resolved: list[str] = []
            missing: list[str] = []
            if rule_ids_in_excel is not None:
                for rid in item.rule_ids:
                    if rid in rule_ids_in_excel:
                        resolved.append(rid)
                    else:
                        missing.append(rid)
            else:
                resolved = list(item.rule_ids)

            status_map = {
                "mapped": "resolved",
                "unmapped": "mapping_incomplete",
                "manual_review": "manual_review",
            }
            st = status_map.get(item.status, item.status)

            ca = ChecklistApplicability(
                checklist_item=item.source_key,
                automation_mode=mode,
                required_rule_ids=list(item.rule_ids),
                resolved_rule_ids=resolved,
                missing_rule_ids=missing,
                status=st,
            )
            results.append(ca)
        return results

