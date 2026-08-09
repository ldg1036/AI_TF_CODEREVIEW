"""
GitHub PR 및 GitLab MR 인라인 리뷰 코멘트 포맷터 모듈.
"""

from __future__ import annotations

from typing import Any


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

    @classmethod
    def post_github_comments(
        cls,
        comments: list[dict[str, Any]],
        repo: str,
        pr_number: int | str,
        token: str | None = None,
        commit_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        GitHub REST API (POST /repos/{owner}/{repo}/pulls/{pull_number}/comments)를 호출하여 PR에 실제 인라인 코멘트를 게시합니다.
        인증 토큰은 GITHUB_TOKEN 환경변수 또는 파라미터로 주입받습니다.
        """
        import os
        import urllib.request
        import json
        import logging

        logger = logging.getLogger(__name__)
        auth_token = token or os.environ.get("GITHUB_TOKEN")
        if not auth_token:
            logger.warning("GITHUB_TOKEN 이 주입되지 않아 실제 GitHub 코멘트 게시를 스킵합니다.")
            return [{"status": "skipped", "reason": "missing_token"}]

        posted_results = []
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"

        for comment in comments:
            payload = dict(comment)
            if commit_id and "commit_id" not in payload:
                payload["commit_id"] = commit_id

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"token {auth_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                    "User-Agent": "WinCC-OA-Code-Reviewer",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    res_body["status_code"] = resp.status
                    posted_results.append(res_body)
            except Exception as e:
                logger.error(f"GitHub PR 코멘트 게시 실패: {e}")
                posted_results.append({"status": "error", "error": str(e)})

        return posted_results

    @classmethod
    def post_gitlab_discussions(
        cls,
        discussions: list[dict[str, Any]],
        project_id: str | int,
        mr_id: str | int,
        token: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        GitLab REST API (POST /projects/:id/merge_requests/:mr_id/discussions)를 호출하여 MR에 실제 코멘트를 게시합니다.
        인증 토큰은 GITLAB_TOKEN 환경변수 또는 파라미터로 주입받습니다.
        """
        import os
        import urllib.request
        import json
        import logging

        logger = logging.getLogger(__name__)
        auth_token = token or os.environ.get("GITLAB_TOKEN")
        if not auth_token:
            logger.warning("GITLAB_TOKEN 이 주입되지 않아 실제 GitLab discussions 게시를 스킵합니다.")
            return [{"status": "skipped", "reason": "missing_token"}]

        posted_results = []
        url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_id}/discussions"

        for discussion in discussions:
            data = json.dumps(discussion).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "PRIVATE-TOKEN": auth_token,
                    "Content-Type": "application/json",
                    "User-Agent": "WinCC-OA-Code-Reviewer",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    res_body["status_code"] = resp.status
                    posted_results.append(res_body)
            except Exception as e:
                logger.error(f"GitLab MR discussion 게시 실패: {e}")
                posted_results.append({"status": "error", "error": str(e)})

        return posted_results
