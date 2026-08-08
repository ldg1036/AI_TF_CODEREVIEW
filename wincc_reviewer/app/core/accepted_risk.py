"""
ACCEPTED_RISK (위험 수용/오탐 승인) 감사 추적 관리 모듈.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.models import Violation, ViolationStatus


@dataclass
class AcceptedRiskEntry:
    """승인된 위험 수용 항목 정보."""

    rule_id: str
    file_path: str
    line_number: int
    approver: str
    reason: str
    approved_date: str


class AcceptedRiskManager:
    """ACCEPTED_RISK 승인 감사 추적 이력을 관리하는 클래스."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or Path("accepted_risks.json")
        self.entries: list[AcceptedRiskEntry] = []
        self.load()

    def load(self) -> None:
        """저장소 파일에서 승인 이력을 읽어옵니다."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf_8_sig") as f:
                    data = json.load(f)
                    self.entries = [AcceptedRiskEntry(**item) for item in data]
            except Exception:
                self.entries = []

    def save(self) -> None:
        """승인 이력을 파일에 저장합니다."""
        data = [asdict(e) for e in self.entries]
        with open(self.storage_path, "w", encoding="utf_8_sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_accepted_risk(self, entry: AcceptedRiskEntry) -> None:
        """신규 위험 수용 항목을 추가합니다."""
        self.entries.append(entry)
        self.save()

    def apply_accepted_risks(self, violations: list[Violation]) -> None:
        """
        위반 목록에 승인 이력을 대조하여 조건 부합 시 ViolationStatus.ACCEPTED_RISK 상태로 갱신합니다.
        """
        for v in violations:
            file_id_str = getattr(v, "file_id", "") or getattr(v, "file_path", "")
            line_no = getattr(v, "line_start", 0) or getattr(v, "line_number", 0)
            for entry in self.entries:
                if v.rule_id == entry.rule_id and (entry.file_path in str(file_id_str) or str(file_id_str) in entry.file_path) and (line_no == entry.line_number or line_no == 0):
                    v.status = ViolationStatus.ACCEPTED_RISK
                    v.ai_analysis = f"[ACCEPTED_RISK] 승인자: {entry.approver}, 사유: {entry.reason} (승인일자: {entry.approved_date})"
                    break

