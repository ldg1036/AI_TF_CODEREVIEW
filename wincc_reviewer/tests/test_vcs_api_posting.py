"""
VCS REST API 인라인 코멘트 게시 유닛 테스트 모듈.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from app.core.models import SeverityLevel, Violation, ViolationStatus
from app.core.vcs_commenter import VCSCommenter


def test_post_github_comments_mock():
    violation = Violation(
        violation_id="v1",
        rule_id="ctl.loop_delay",
        severity=SeverityLevel.HIGH,
        status=ViolationStatus.FAIL,
        message="무한 루프 내 delay 미비",
        file_id="scripts/test.ctl",
        line_start=10,
    )
    comments = VCSCommenter.build_github_inline_comments([violation])
    assert len(comments) == 1
    assert comments[0]["path"] == "scripts/test.ctl"

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"id": 101, "status": "created"}).encode("utf-8")
    mock_resp.status = 201
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = VCSCommenter.post_github_comments(
            comments,
            repo="ldg1036/AI_TF_CODEREVIEW",
            pr_number=1,
            token="ghp_dummy_token_for_testing",
            commit_id="70de099",
        )
        assert len(res) == 1
        assert res[0]["status_code"] == 201
        assert res[0]["id"] == 101


def test_post_gitlab_discussions_mock():
    violation = Violation(
        violation_id="v2",
        rule_id="ctl.dp_connect_pair",
        severity=SeverityLevel.CRITICAL,
        status=ViolationStatus.FAIL,
        message="dpConnect 미해제 위험",
        file_id="scripts/main.ctl",
        line_start=25,
    )
    discussions = VCSCommenter.build_gitlab_inline_comments([violation])
    assert len(discussions) == 1

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"id": "discussion_202", "status": "created"}).encode("utf-8")
    mock_resp.status = 201
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = VCSCommenter.post_gitlab_discussions(
            discussions,
            project_id=999,
            mr_id=5,
            token="glpat_dummy_token",
        )
        assert len(res) == 1
        assert res[0]["status_code"] == 201
        assert res[0]["id"] == "discussion_202"
