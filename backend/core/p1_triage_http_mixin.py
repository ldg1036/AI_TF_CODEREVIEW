from http import HTTPStatus
from typing import Any, Dict, cast

from core.api_types import P1TriageDeleteRequestBody, P1TriageUpsertRequestBody
from core.p1_triage_store import (
    VALID_P1_TRIAGE_STATUS,
    delete_p1_triage_entry,
    list_p1_triage_entries,
    upsert_p1_triage_entry,
)


class P1TriageHttpMixin:
    """HTTP handlers for local P1 triage storage."""

    @staticmethod
    def _normalize_triage_match(match: Any) -> Dict[str, Any]:
        if not isinstance(match, dict):
            raise ValueError("match must be an object")
        return {
            "file": str(match.get("file", "") or ""),
            "line": int(match.get("line", 0) or 0),
            "rule_id": str(match.get("rule_id", "") or ""),
            "message": str(match.get("message", "") or ""),
            "issue_id": str(match.get("issue_id", "") or ""),
        }

    def _handle_get_p1_triage(self) -> None:
        self._send_json(HTTPStatus.OK, list_p1_triage_entries())

    def _handle_upsert_p1_triage(self, request_id: str) -> None:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(P1TriageUpsertRequestBody, body)
        triage_key = str(typed_body.get("triage_key", "") or "").strip()
        if not triage_key:
            raise ValueError("triage_key is required")
        status = str(typed_body.get("status", "") or "").strip().lower()
        if status not in VALID_P1_TRIAGE_STATUS:
            raise ValueError("status must be one of: open, suppressed")
        result = upsert_p1_triage_entry(
            triage_key=triage_key,
            status=status,
            reason=str(typed_body.get("reason", "") or ""),
            note=str(typed_body.get("note", "") or ""),
            match=self._normalize_triage_match(typed_body.get("match", {})),
        )
        result["request_id"] = request_id
        self._send_json(HTTPStatus.OK, result)

    def _handle_delete_p1_triage(self, request_id: str) -> None:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(P1TriageDeleteRequestBody, body)
        triage_key = str(typed_body.get("triage_key", "") or "").strip()
        if not triage_key:
            raise ValueError("triage_key is required")
        result = delete_p1_triage_entry(triage_key=triage_key)
        result["request_id"] = request_id
        self._send_json(HTTPStatus.OK, result)
