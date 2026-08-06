"""
GitHub PR 및 GitLab MR 인라인 리뷰 코멘트 포맷터 모듈.
"""

from __future__ import annotations

from typing import Any
from app.core.models import Violation


class VCSCommenter:
    """VCS (GitHub PR / GitLab MR) 인라인 코멘트 데이터 생성기."""

    @classmethod
    def build_github_inline_comments(cls, violations: list[Any]) -> list[dict[str, Any]]:
        """
        GitHub PR REST API (POST /repos/{owner}/{repo}/pulls/{pull_number}/comments) 규격 인라인 페이로드 목록을 생성합니다.
        """
        comments = []
        for v in violations:
            file_path = str(getattr(v, "file_id", "") or getattr(v, "file_path", ""))
            line_no = int(getattr(v, "line_start", 0) or getattr(v, "line_number", 0) or 1)
            rule_id = str(getattr(v, "rule_id", ""))
            severity = str(getattr(v, "severity", "MEDIUM"))
            msg = str(getattr(v, "message", ""))
            ai_info = str(getattr(v, "ai_analysis", ""))

            body = f"**[{rule_id}] {severity} 위반 감지**\n\n{msg}"
            if ai_info:
                body += f"\n\n**AI 권고 사항:**\n{ai_info}"

            comments.append(
                {
                    "path": file_path,
                    "line": line_no,
                    "side": "RIGHT",
                    "body": body,
                }
            )

        return comments

    @classmethod
    def build_gitlab_inline_comments(cls, violations: list[Any]) -> list[dict[str, Any]]:
        """
        GitLab MR API (POST /projects/:id/merge_requests/:mr_id/discussions) 규격 인라인 페이로드 목록을 생성합니다.
        """
        discussions = []
        for v in violations:
            file_path = str(getattr(v, "file_id", "") or getattr(v, "file_path", ""))
            line_no = int(getattr(v, "line_start", 0) or getattr(v, "line_number", 0) or 1)
            rule_id = str(getattr(v, "rule_id", ""))
            severity = str(getattr(v, "severity", "MEDIUM"))
            msg = str(getattr(v, "message", ""))

            discussions.append(
                {
                    "position": {
                        "position_type": "text",
                        "new_path": file_path,
                        "new_line": line_no,
                    },
                    "body": f"[{rule_id}] ({severity}) {msg}",
                }
            )

        return discussions
