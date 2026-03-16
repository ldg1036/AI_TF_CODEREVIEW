import logging
import os
import time
import uuid
from http import HTTPStatus
from typing import Any, Dict, cast
from urllib.parse import parse_qs

from core.api_types import RuleDeleteRequestBody, RuleImportRequestBody, RuleRecordRequestBody, RuleUpdateRequestBody
from core.errors import ReviewerError
from main import AutoFixApplyError

logger = logging.getLogger(__name__)


class ApiDispatchMixin:
    """Route dispatch helpers extracted from backend/server.py."""

    def _dispatch_get_request(self, parsed: Any) -> bool:
        if parsed.path == "/api/health/deps":
            self._send_json(HTTPStatus.OK, self._build_dependency_health_payload())
            return True

        if parsed.path == "/api/rules/health":
            self._send_json(HTTPStatus.OK, self._build_rules_health_payload())
            return True

        if parsed.path == "/api/rules/list":
            self._send_json(HTTPStatus.OK, self._build_rules_list_payload())
            return True

        if parsed.path == "/api/rules/export":
            self._send_json(HTTPStatus.OK, self._export_rules_payload())
            return True

        if parsed.path == "/api/verification/latest":
            try:
                self._send_json(HTTPStatus.OK, self._resolve_latest_verification_summary())
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return True

        if parsed.path == "/api/operations/latest":
            self._send_json(HTTPStatus.OK, self._resolve_latest_operational_results())
            return True

        if parsed.path == "/api/analysis-diff/latest":
            try:
                self._send_json(HTTPStatus.OK, self._resolve_latest_analysis_diff())
            except RuntimeError as exc:
                self._send_json(
                    HTTPStatus.OK,
                    {"available": False, "message": str(exc), "latest": None, "previous": None, "delta": {"summary": {}}, "file_diffs": []},
                )
            return True

        if parsed.path == "/api/analysis-diff/runs":
            self._send_json(HTTPStatus.OK, self._resolve_analysis_diff_runs())
            return True

        if parsed.path == "/api/analysis-diff/compare":
            query = parse_qs(parsed.query)
            latest_key = str(query.get("latest", [""])[0] or "")
            previous_key = str(query.get("previous", [""])[0] or "")
            try:
                self._send_json(HTTPStatus.OK, self._resolve_selected_analysis_diff(latest_key, previous_key))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(
                    HTTPStatus.OK,
                    {"available": False, "message": str(exc), "latest": None, "previous": None, "delta": {"summary": {}}, "file_diffs": []},
                )
            return True

        if parsed.path == "/api/analyze/status":
            try:
                self._handle_analyze_status()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return True

        if parsed.path == "/api/files":
            query = parse_qs(parsed.query)
            allow_raw_txt = str(query.get("allow_raw_txt", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            payload = {"files": self.app.list_available_files(allow_raw_txt=allow_raw_txt)}
            self._send_json(HTTPStatus.OK, payload)
            return True

        if parsed.path == "/api/ai/models":
            self._send_json(HTTPStatus.OK, self.app.list_ai_models())
            return True

        if parsed.path == "/api/report/excel/download":
            query = parse_qs(parsed.query)
            output_dir = str(query.get("output_dir", [""])[0] or "")
            name = str(query.get("name", [""])[0] or "")
            try:
                report_path = self._resolve_excel_download_path(output_dir, name)
                self._send_download_file(
                    report_path,
                    os.path.basename(report_path),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return True

        if parsed.path == "/api/file-content":
            query = parse_qs(parsed.query)
            name = str(query.get("name", [""])[0] or "")
            prefer_source = str(query.get("prefer_source", ["false"])[0]).lower() in ("1", "true", "yes", "on")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            try:
                payload = self.app.get_viewer_content(name, prefer_source=prefer_source, output_dir=output_dir or None)
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return True

        if parsed.path == "/api/autofix/file-diff":
            query = parse_qs(parsed.query)
            name = str(query.get("file", [""])[0] or "")
            session_id = str(query.get("session_id", [""])[0] or "")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            proposal_id = str(query.get("proposal_id", [""])[0] or "")
            try:
                payload = self.app.get_autofix_file_diff(
                    file_name=name,
                    session_id=session_id or None,
                    output_dir=output_dir or None,
                    proposal_id=proposal_id or "",
                )
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
            return True

        if parsed.path == "/api/autofix/stats":
            query = parse_qs(parsed.query)
            session_id = str(query.get("session_id", [""])[0] or "")
            output_dir = str(query.get("output_dir", [""])[0] or "")
            try:
                payload = self.app.get_autofix_stats(session_id=session_id or None, output_dir=output_dir or None)
                self._send_json(HTTPStatus.OK, payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
            return True

        if parsed.path == "/":
            self.path = "/index.html"
        return False

    def _dispatch_post_request(self, parsed: Any, request_started: float) -> bool:
        if parsed.path == "/api/input-sources/stage":
            request_id = uuid.uuid4().hex
            try:
                payload = self._read_multipart_files()
                result = self.app.stage_input_files(payload.get("files", []), mode=str(payload.get("mode", "files") or "files"))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Input source stage done id=%s status=400 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Input source stage done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/ai-review/apply":
            request_id = uuid.uuid4().hex
            try:
                self._handle_apply_ai_review(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc)})
                logger.warning("AI apply request done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                logger.error("AI apply request done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/ai-review/generate":
            request_id = uuid.uuid4().hex
            try:
                self._handle_generate_ai_review(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=404 error=%s", request_id, exc)
            except ReviewerError as exc:
                self._send_json(HTTPStatus.OK, {"available": False, "message": str(exc), "request_id": request_id})
                logger.warning("AI generate request done id=%s status=200 fail-soft error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("AI generate request done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/autofix/prepare":
            request_id = uuid.uuid4().hex
            try:
                self._handle_autofix_prepare(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Autofix prepare done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Autofix prepare done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/autofix/apply":
            request_id = uuid.uuid4().hex
            try:
                self._handle_autofix_apply(request_id)
            except AutoFixApplyError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), self._autofix_error_payload(exc, request_id))
                logger.warning(
                    "Autofix apply done id=%s status=409 error_code=%s error=%s",
                    request_id,
                    getattr(exc, "error_code", ""),
                    exc,
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), self._autofix_error_payload(exc, request_id))
                logger.warning("Autofix apply done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Autofix apply done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/report/excel":
            request_id = uuid.uuid4().hex
            try:
                self._handle_excel_report_flush(request_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Excel report flush done id=%s status=400 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Excel report flush done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Excel report flush done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/rules/update":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleUpdateRequestBody, body)
                result = self._update_rules_enabled_state(list(typed_body.get("updates", []) or []))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules update done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules update done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/rules/create":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleRecordRequestBody, body)
                result = self._create_rule(cast(Dict[str, Any], typed_body.get("rule", {})))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules create done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules create done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/rules/replace":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleRecordRequestBody, body)
                result = self._replace_rule(cast(Dict[str, Any], typed_body.get("rule", {})))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules replace done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules replace done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/rules/delete":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleDeleteRequestBody, body)
                result = self._delete_rule(str(typed_body.get("id", "") or ""))
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules delete done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules delete done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path == "/api/rules/import":
            request_id = uuid.uuid4().hex
            try:
                body = self._read_json_body()
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                typed_body = cast(RuleImportRequestBody, body)
                result = self._import_rules_payload(
                    list(typed_body.get("rules", []) or []),
                    mode=str(typed_body.get("mode", "replace") or "replace"),
                )
                result["request_id"] = request_id
                self._send_json(HTTPStatus.OK, result)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=400 error=%s", request_id, exc)
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=404 error=%s", request_id, exc)
            except RuntimeError as exc:
                self._send_json(getattr(HTTPStatus, "CONFLICT", 409), {"error": str(exc), "request_id": request_id})
                logger.warning("Rules import done id=%s status=409 error=%s", request_id, exc)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc), "request_id": request_id})
                logger.error("Rules import done id=%s status=500 error=%s", request_id, exc)
            return True

        if parsed.path in ("/api/analyze/start", "/api/analyze"):
            return False

        return False
