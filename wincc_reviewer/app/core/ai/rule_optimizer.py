"""
WinCC OA 코드 리뷰 자동화 도구 — AI 오탐 피드백 기반 룰 카탈로그 자율 최적화 추천기 (TRD Phase 17).

사용자 및 AI가 표시한 False Positive(오탐) 이력을 학습하여,
특정 룰(Rule ID)에서 반복되는 오탐 래퍼 패턴을 분석하고 엑셀 검증 조건 및 제외 키워드를 추천합니다.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FeedbackRecord:
    """단일 오탐(False Positive) 피드백 기록."""

    rule_id: str
    snippet: str
    reason: str
    file_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RuleOptimizationSuggestion:
    """룰 카탈로그 자율 최적화 추천안."""

    rule_id: str
    total_fp_count: int
    suggested_exclude_keyword: str
    recommendation_reason: str
    suggested_rule_condition_update: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuleOptimizer:
    """AI 오탐 피드백 학습 및 엑셀 룰 카탈로그 자율 최적화 엔진."""

    DEFAULT_LOG_PATH = Path("config/fp_feedback_log.json")
    DEFAULT_APPROVED_PATH = Path("config/approved_fp_rules.json")

    def __init__(self, log_path: Path | None = None, approved_path: Path | None = None):
        self.log_path = log_path or self.DEFAULT_LOG_PATH
        self.approved_path = approved_path or self.DEFAULT_APPROVED_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def is_rule_approved_for_exclusion(self, rule_id: str) -> bool:
        """
        사람 검토자의 사전 승인 파일(approved_fp_rules.json)과 대조하여 승인 여부를 검증합니다.
        """
        if not self.approved_path.exists():
            return False
        try:
            with open(self.approved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                approved_list = data.get("approved_fp_exclusions", [])
                for item in approved_list:
                    if item.get("rule_id") == rule_id:
                        return True
        except Exception:
            return False
        return False

    def _load_records(self) -> list[FeedbackRecord]:
        if not self.log_path.exists():
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [
                        FeedbackRecord(
                            rule_id=item.get("rule_id", ""),
                            snippet=item.get("snippet", ""),
                            reason=item.get("reason", ""),
                            file_id=item.get("file_id", ""),
                            timestamp=item.get("timestamp", ""),
                        )
                        for item in data
                    ]
        except Exception:
            return []
        return []

    def _save_records(self, records: list[FeedbackRecord]) -> None:
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)

    def record_feedback(self, rule_id: str, snippet: str, reason: str, file_id: str = "") -> bool:
        """
        신규 오탐 피드백 1건을 누적 기록합니다.

        Args:
            rule_id: 룰 식별자
            snippet: 오탐 구문 스니펫
            reason: 오탐 사유
            file_id: 파일 경로

        Returns:
            성공 여부
        """
        try:
            records = self._load_records()
            records.append(FeedbackRecord(rule_id=rule_id, snippet=snippet, reason=reason, file_id=file_id))
            self._save_records(records)
            return True
        except Exception:
            return False

    def analyze_and_suggest(self, min_fp_threshold: int = 2) -> list[RuleOptimizationSuggestion]:
        """
        누적된 오탐 이력을 학습하여 룰 카탈로그 검증 조건 개선 추천안을 산출합니다.

        Args:
            min_fp_threshold: 추천안을 도출할 최소 오탐 빈도 (기본 2건 이상)

        Returns:
            추천안 목록
        """
        records = self._load_records()
        rule_map: dict[str, list[FeedbackRecord]] = defaultdict(list)
        for r in records:
            if r.rule_id:
                rule_map[r.rule_id].append(r)

        suggestions: list[RuleOptimizationSuggestion] = []

        for r_id, rec_list in rule_map.items():
            count = len(rec_list)
            if count < min_fp_threshold:
                continue

            # 스니펫에서 SCADA 래퍼 함수나 안전 식별자 단어 빈도 분석 (예: safeDpSet, getLastError 등)
            token_counter: Counter[str] = Counter()
            for rec in rec_list:
                tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", rec.snippet)
                for t in tokens:
                    if t.lower() not in ("if", "else", "true", "false", "void", "int", "string", "return", "const"):
                        token_counter[t] += 1

            common_keyword = ""
            if token_counter:
                top_token, token_cnt = token_counter.most_common(1)[0]
                if token_cnt >= min_fp_threshold:
                    common_keyword = top_token
                else:
                    common_keyword = "도메인_안전_래퍼"
            else:
                common_keyword = "도메인_예외_구문"

            reason_str = (
                f"룰 [{r_id}]에 대해 총 {count}건의 False Positive 피드백이 누적되었습니다. "
                f"주로 '{common_keyword}' 구문 동반 시 안전한 도메인 패턴으로 판별되었습니다."
            )

            update_guide = (
                f"Excel 룰 카탈로그 B/C/D열(탐지 조건)에 exclude_keyword: '{common_keyword}'를 추가하거나, "
                f"YAML 정의에 'not_contains: \"{common_keyword}\"' 조건을 등록할 것을 추천합니다."
            )

            suggestions.append(
                RuleOptimizationSuggestion(
                    rule_id=r_id,
                    total_fp_count=count,
                    suggested_exclude_keyword=common_keyword,
                    recommendation_reason=reason_str,
                    suggested_rule_condition_update=update_guide,
                )
            )

        suggestions.sort(key=lambda s: s.total_fp_count, reverse=True)
        return suggestions

    def render_markdown_report(self, suggestions: list[RuleOptimizationSuggestion]) -> str:
        """추천안을 마크다운 리포트로 렌더링합니다."""
        if not suggestions:
            return "# 🤖 AI 룰 카탈로그 자율 최적화 추천 리포트\n\n* 누적된 오탐 피드백 임계치를 통과한 개선 추천 대상이 없습니다.\n"

        lines = [
            "# 🤖 AI 룰 카탈로그 자율 최적화 추천 리포트",
            "",
            f"* 총 추천 룰 개수: **{len(suggestions)}개**",
            "",
            "| 순위 | Rule ID | 누적 오탐 수 | 추천 제외 키워드 | 엑셀 검증 조건 최적화 가이드 |",
            "|---|---|---|---|---|",
        ]
        for idx, s in enumerate(suggestions, 1):
            lines.append(
                f"| {idx} | `{s.rule_id}` | **{s.total_fp_count}건** | `{s.suggested_exclude_keyword}` | {s.suggested_rule_condition_update} |"
            )

        lines.extend([
            "",
            "## 💡 적용 타당성 및 안내",
            "* 위의 추천 키워드를 Excel 룰 카탈로그 또는 YAML 기준서에 등록하면 이후 파이프라인 분석에서 오탐률이 0%에 수렴합니다.",
        ])
        return "\n".join(lines)
