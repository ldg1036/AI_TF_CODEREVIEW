"""RequestValidationMixin – Request parsing and input validation extracted from server.py."""

import json
import logging
import os
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from typing import Any, Dict, List, cast

from main import DEFAULT_MODE, AutoFixApplyError

logger = logging.getLogger(__name__)


class RequestValidationMixin:
    """Handles JSON body parsing, file/input source validation, and multipart uploads."""

    def _parse_analyze_request_body(self, *, validate_selected_files: bool) -> Dict[str, Any]:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = body
        mode = typed_body.get("mode", DEFAULT_MODE)
        selected_files = typed_body.get("selected_files", [])
        input_sources = typed_body.get("input_sources", [])
        if not isinstance(selected_files, list):
            raise ValueError("selected_files must be a list")

        allow_raw_txt = typed_body.get("allow_raw_txt", False)
        if not isinstance(allow_raw_txt, bool):
            raise ValueError("allow_raw_txt must be a boolean")
        enable_ctrlppcheck = typed_body.get("enable_ctrlppcheck", None)
        enable_live_ai = typed_body.get("enable_live_ai", None)
        ai_model_name = typed_body.get("ai_model_name", None)
        ai_with_context = typed_body.get("ai_with_context", False)
        defer_excel_reports = typed_body.get("defer_excel_reports", None)
        if enable_ctrlppcheck is not None and not isinstance(enable_ctrlppcheck, bool):
            raise ValueError("enable_ctrlppcheck must be a boolean")
        if enable_live_ai is not None and not isinstance(enable_live_ai, bool):
            raise ValueError("enable_live_ai must be a boolean")
        if not isinstance(ai_with_context, bool):
            raise ValueError("ai_with_context must be a boolean")
        if ai_model_name is not None and not isinstance(ai_model_name, str):
            raise ValueError("ai_model_name must be a string when provided")
        if defer_excel_reports is not None and not isinstance(defer_excel_reports, bool):
            raise ValueError("defer_excel_reports must be a boolean when provided")
        if validate_selected_files:
            self._validate_selected_files(selected_files, allow_raw_txt=allow_raw_txt)
        validated_input_sources = self._validate_input_sources(input_sources, allow_raw_txt=allow_raw_txt)

        return {
            "mode": mode,
            "selected_files": selected_files,
            "input_sources": validated_input_sources,
            "allow_raw_txt": allow_raw_txt,
            "enable_ctrlppcheck": enable_ctrlppcheck,
            "enable_live_ai": enable_live_ai,
            "ai_model_name": str(ai_model_name or "").strip() or None,
            "ai_with_context": ai_with_context,
            "defer_excel_reports": defer_excel_reports,
        }

    def _analysis_response_status(self, result: Any):
        if not isinstance(result, dict):
            return HTTPStatus.OK
        summary = result.get("summary", {})
        if not isinstance(summary, dict):
            return HTTPStatus.OK
        failed_count = self._safe_int(summary.get("failed_file_count", 0), 0)
        success_count = self._safe_int(summary.get("successful_file_count", 0), 0)
        if failed_count <= 0:
            return HTTPStatus.OK
        if success_count > 0:
            return getattr(HTTPStatus, "MULTI_STATUS", 207)
        return HTTPStatus.INTERNAL_SERVER_ERROR

    @staticmethod
    def _autofix_error_payload(exc: Exception, request_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"error": str(exc), "request_id": request_id}
        error_code = ""
        quality_metrics: Dict[str, Any] = {}
        if isinstance(exc, AutoFixApplyError):
            error_code = str(getattr(exc, "error_code", "") or "")
            maybe_qm = getattr(exc, "quality_metrics", {}) or {}
            if isinstance(maybe_qm, dict):
                quality_metrics = maybe_qm
        if not error_code:
            msg = str(exc or "")
            if "base hash mismatch" in msg.lower():
                error_code = "BASE_HASH_MISMATCH"
            elif "anchor mismatch" in msg.lower():
                error_code = "ANCHOR_MISMATCH"
            elif "semantic guard blocked" in msg.lower():
                error_code = "SEMANTIC_GUARD_BLOCKED"
            elif "source changed since prepare" in msg.lower() or "prepared patch expired or source changed" in msg.lower():
                error_code = "SOURCE_CHANGED_SINCE_PREPARE"
            elif "prepared proposal missing" in msg.lower():
                error_code = "PREPARED_PROPOSAL_MISSING"
            elif "cache expired" in msg.lower() or "prepared patch expired or cache expired" in msg.lower():
                error_code = "CACHE_EXPIRED"
            elif "supported only for .ctl" in msg.lower():
                error_code = "UNSUPPORTED_FILE_TYPE"
            elif "syntax precheck failed" in msg.lower():
                error_code = "SYNTAX_PRECHECK_FAILED"
            elif "regression" in msg.lower():
                error_code = "REGRESSION_BLOCKED"
        if error_code:
            payload["error_code"] = error_code
        if quality_metrics:
            payload["quality_metrics"] = quality_metrics
        return payload

    def _read_json_body(self) -> Any:
        length_header = self.headers.get("Content-Length", "0")
        try:
            length = int(length_header)
        except ValueError:
            raise ValueError("Invalid Content-Length")

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON body: {exc}") from exc

    @staticmethod
    def _is_txt(name):
        return isinstance(name, str) and name.lower().endswith(".txt")

    @staticmethod
    def _is_normalized_txt(name):
        return isinstance(name, str) and (name.endswith("_pnl.txt") or name.endswith("_xml.txt"))

    def _validate_selected_files(self, selected_files, allow_raw_txt=False):
        if not isinstance(selected_files, list):
            raise ValueError("selected_files must be a list")

        # Validate existence against full known set first to keep explicit raw-txt policy errors.
        available_names = {item["name"] for item in self.app.list_available_files(allow_raw_txt=True)}
        invalid = [name for name in selected_files if not isinstance(name, str) or name not in available_names]
        if invalid:
            raise ValueError(f"Unknown file(s): {invalid}")

        if allow_raw_txt:
            return

        blocked_raw_txt = [
            name
            for name in selected_files
            if self._is_txt(name) and not self._is_normalized_txt(name)
        ]
        if blocked_raw_txt:
            raise ValueError(
                "Raw .txt selection is disabled. Set allow_raw_txt=true to analyze these files: "
                f"{blocked_raw_txt}"
            )

    @staticmethod
    def _is_local_absolute_path(path_value: str) -> bool:
        if not isinstance(path_value, str) or not path_value.strip():
            return False
        if path_value.startswith("\\\\"):
            return False
        return os.path.isabs(path_value)

    @classmethod
    def _is_supported_input_file(cls, path_value: str, *, allow_raw_txt: bool) -> bool:
        lower = str(path_value or "").lower()
        if lower.endswith((".ctl", ".pnl", ".xml")):
            return True
        if lower.endswith(".txt"):
            name = os.path.basename(path_value)
            return allow_raw_txt or cls._is_normalized_txt(name)
        return False

    @classmethod
    def _folder_has_supported_targets(cls, folder_path: str, *, allow_raw_txt: bool) -> bool:
        for root, _dirs, files in os.walk(folder_path):
            for name in files:
                if cls._is_supported_input_file(os.path.join(root, name), allow_raw_txt=allow_raw_txt):
                    return True
        return False

    def _validate_input_sources(self, input_sources, allow_raw_txt=False):
        if input_sources is None:
            return []
        if not isinstance(input_sources, list):
            raise ValueError("input_sources must be a list")
        validated = []
        for item in input_sources:
            if not isinstance(item, dict):
                raise ValueError("input_sources entries must be objects")
            source_type = str(item.get("type", "") or "").strip()
            source_value = str(item.get("value", "") or "").strip()
            if source_type not in ("builtin_file", "file_path", "folder_path"):
                raise ValueError(f"Unsupported input source type: {source_type}")
            if not source_value:
                raise ValueError("input_sources value is required")
            if source_type != "builtin_file":
                if not self._is_local_absolute_path(source_value):
                    raise ValueError(f"input_sources path must be a local absolute path: {source_value}")
                normalized = os.path.normpath(source_value)
                if source_type == "file_path" and not os.path.isfile(normalized):
                    raise ValueError(f"Input file not found: {source_value}")
                if source_type == "folder_path" and not os.path.isdir(normalized):
                    raise ValueError(f"Input folder not found: {source_value}")
                source_value = normalized
                if source_type == "file_path" and source_value.lower().endswith(".txt") and not allow_raw_txt:
                    name = os.path.basename(source_value)
                    if self._is_txt(name) and not self._is_normalized_txt(name):
                        raise ValueError(f"Raw .txt selection is disabled: {source_value}")
                if source_type == "file_path" and not self._is_supported_input_file(source_value, allow_raw_txt=allow_raw_txt):
                    raise ValueError(f"Unsupported input file type: {source_value}")
                if source_type == "folder_path" and not self._folder_has_supported_targets(source_value, allow_raw_txt=allow_raw_txt):
                    raise ValueError(f"Input folder has no supported review files: {source_value}")
            validated.append({"type": source_type, "value": source_value})
        return validated

    def _read_multipart_files(self) -> Dict[str, Any]:
        content_type = str(self.headers.get("Content-Type", "") or "")
        if "multipart/form-data" not in content_type.lower():
            raise ValueError("multipart/form-data content type is required")
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            raise ValueError("Invalid Content-Length")
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        if not raw_body:
            return {"mode": "files", "files": []}

        message_bytes = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n"
            "\r\n"
        ).encode("utf-8") + raw_body
        message = BytesParser(policy=policy.default).parsebytes(message_bytes)

        mode = "files"
        uploaded = []
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            field_name = str(part.get_param("name", header="content-disposition") or "")
            filename = str(part.get_filename() or "")
            if field_name == "mode":
                mode_text = part.get_content()
                mode = str(mode_text or "files").strip() or "files"
                continue
            if field_name != "files" or not filename:
                continue
            payload = part.get_payload(decode=True)
            uploaded.append({"name": filename, "content": payload if isinstance(payload, bytes) else b""})
        return {"mode": mode, "files": uploaded}
