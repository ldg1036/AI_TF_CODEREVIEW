"""
Precision/Recall 평가기 및 VCS 인라인 코멘트 생성기 유닛 테스트.
"""

from pathlib import Path
import pytest

from app.core.vcs_commenter import VCSCommenter
from app.core.models import Violation, SeverityLevel, ViolationStatus


def test_vcs_commenter_github():
    """GitHub 인라인 주석 페이로드 생성 테스트."""
    v = Violation(
        violation_id="V01",
        rule_id="RULE01",
        file_id="main.ctl",
        status=ViolationStatus.FAIL,
        severity=SeverityLevel.HIGH,
        message="테스트 메시지",
        line_start=15,
        ai_analysis="AI 2차 가이드",
    )
    comments = VCSCommenter.build_github_inline_comments([v])
    assert len(comments) == 1
    assert comments[0]["path"] == "main.ctl"
    assert comments[0]["line"] == 15
    assert "RULE01" in comments[0]["body"]
    assert "AI 2차 가이드" in comments[0]["body"]


def test_vcs_commenter_gitlab():
    """GitLab 인라인 디스커션 페이로드 생성 테스트."""
    v = Violation(
        violation_id="V02",
        rule_id="RULE02",
        file_id="app.ctl",
        status=ViolationStatus.FAIL,
        severity=SeverityLevel.CRITICAL,
        message="위험 결함",
        line_start=20,
    )
    discussions = VCSCommenter.build_gitlab_inline_comments([v])
    assert len(discussions) == 1
    assert discussions[0]["position"]["new_path"] == "app.ctl"
    assert discussions[0]["position"]["new_line"] == 20
    assert "RULE02" in discussions[0]["body"]
