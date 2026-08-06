"""
WinCC OA 코드 리뷰 자동화 도구 — 데이터 모델.

09_구현착수_패키지_계약.md §4 데이터 모델 최소 계약에 따른 정의.
필수 필드와 enum은 변경하지 않습니다.
추가 필드는 하위 호환 가능하게 추가합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


# ────────────────────────────────────────────
# Enum 정의
# ────────────────────────────────────────────


class CheckerType(StrEnum):
    """checker_type enum (09_구현착수 §4)."""

    BUILTIN = "builtin"
    REGEX = "regex"
    MANUAL = "manual"


class ViolationStatus(StrEnum):
    """Violation status enum (09_구현착수 §4)."""

    FAIL = "FAIL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ERROR = "ERROR"
    ACCEPTED_RISK = "ACCEPTED_RISK"



class SeverityLevel(StrEnum):
    """severity enum (09_구현착수 §4)."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class ParseStatusType(StrEnum):
    """ParseStatus status enum (09_구현착수 §4)."""

    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    UNSUPPORTED = "unsupported"


class AutomationMode(StrEnum):
    """automation_mode enum (TRD §5.2)."""

    AUTO_FULL = "auto_full"
    AUTO_VIOLATION_ONLY = "auto_violation_only"
    MANUAL = "manual"


class StageStatusType(StrEnum):
    """파이프라인 단계 상태 (TRD §11.1)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ────────────────────────────────────────────
# 데이터 클래스 정의
# ────────────────────────────────────────────


@dataclass
class RuleDefinition:
    """
    룰 정의 (09_구현착수 §4).

    required: rule_id, source_key, file_types, checker_type, enabled, rule_version
    """

    rule_id: str
    source_key: str
    file_types: list[str]
    checker_type: CheckerType
    enabled: bool
    rule_version: str
    # 선택 필드
    category: str = ""
    subcategory: str = ""
    check_item: str = ""
    condition: str = ""
    severity: SeverityLevel = SeverityLevel.INFO
    checker_key: str = ""
    pattern: str = ""
    message: str = ""
    fix_hint: str = ""
    autofix_allowed: bool = False


@dataclass
class Violation:
    """
    위반 사항 (09_구현착수 §4).

    required: violation_id, rule_id, file_id, status, severity, message
    """

    violation_id: str
    rule_id: str
    file_id: str
    status: ViolationStatus
    severity: SeverityLevel
    message: str
    # 선택 필드
    line_start: int | None = None
    line_end: int | None = None
    snippet: str = ""
    ai_analysis: str = ""
    confidence_score: float | None = None  # 0.0 ~ 1.0 (정밀 신뢰도 점수)
    false_positive_probability: float | None = None  # 0.0 ~ 1.0 (허위 경보 확률)
    is_false_positive: bool = False  # AI 검증에 따른 오탐(False Positive) 여부
    ai_verification_reason: str = ""  # AI 검증 근거 설명



@dataclass
class ParseStatus:
    """
    파싱 상태 (09_구현착수 §4).

    required: status
    """

    status: ParseStatusType
    file: str = ""
    error_message: str | None = None


@dataclass
class StageStatus:
    """파이프라인 단계 상태 (TRD §11.1)."""

    status: StageStatusType = StageStatusType.PENDING
    error_code: str | None = None
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class ChecklistApplicability:
    """체크리스트 적용성 매핑 (TRD §6)."""

    checklist_item: str
    automation_mode: AutomationMode
    required_rule_ids: list[str] = field(default_factory=list)
    resolved_rule_ids: list[str] = field(default_factory=list)
    missing_rule_ids: list[str] = field(default_factory=list)
    status: str = "manual_review"  # resolved | mapping_incomplete | manual_review


@dataclass
class Metrics:
    """실행 지표 (TRD §6)."""

    timings_ms: dict[str, int] = field(default_factory=dict)
    cache_hits: dict[str, int] = field(default_factory=dict)
    cache_misses: dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    violation_count: int = 0
    optional_dependencies: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewReport:
    """
    리뷰 리포트 (09_구현착수 §4).

    required: schema_version, run_id, rule_source, files, violations, errors, metrics
    """

    schema_version: str
    run_id: str
    rule_source: str
    files: list[str]
    violations: list[Violation]
    errors: list[ParseStatus]
    metrics: Metrics
    # 선택 필드
    ruleset_version: str = ""
    ruleset_source_sha256: str = ""
    app_version: str = ""
    generated_at: datetime | None = None
    checklist_applicability: list[ChecklistApplicability] = field(default_factory=list)
    stage_status: dict[str, StageStatus] = field(default_factory=dict)
    trend_summary: dict[str, Any] | None = None

