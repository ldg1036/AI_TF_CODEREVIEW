import logging
from http import HTTPStatus
from typing import Any, Dict, Optional, cast

from core.api_types import AIReviewApplyRequestBody, AIReviewGenerateRequestBody

logger = logging.getLogger(__name__)


class AIReviewHttpMixin:
    """AI review request handlers extracted from backend/server.py."""

    def _handle_apply_ai_review(self, request_id: str) -> None:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AIReviewApplyRequestBody, body)

        file_name = typed_body.get("file", "")
        object_name = typed_body.get("object", "")
        event_name = typed_body.get("event", "Global")
        review_text = typed_body.get("review", "")
        output_dir = typed_body.get("output_dir", None)

        if not isinstance(file_name, str) or not file_name.strip():
            raise ValueError("file must be a non-empty string")
        if not isinstance(object_name, str) or not object_name.strip():
            raise ValueError("object must be a non-empty string")
        if not isinstance(event_name, str) or not event_name.strip():
            raise ValueError("event must be a non-empty string")
        if not isinstance(review_text, str) or not review_text.strip():
            raise ValueError("review must be a non-empty string")
        if output_dir is not None and not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string when provided")

        logger.info("AI apply request start id=%s file=%s object=%s event=%s", request_id, file_name, object_name, event_name)
        result = self.app.apply_ai_review_to_reviewed_file(
            file_name=file_name,
            object_name=object_name,
            event_name=event_name,
            review_text=review_text,
            output_dir=output_dir,
        )
        self._send_json(HTTPStatus.OK, result)
        logger.info("AI apply request done id=%s status=200 applied_blocks=%d", request_id, int(result.get("applied_blocks", 0)))

    def _handle_generate_ai_review(self, request_id: str) -> None:
        body = self._read_json_body()
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        typed_body = cast(AIReviewGenerateRequestBody, body)
        violation = typed_body.get("violation", {})
        enable_live_ai = typed_body.get("enable_live_ai", None)
        ai_model_name = typed_body.get("ai_model_name", None)
        ai_with_context = typed_body.get("ai_with_context", False)

        if not isinstance(violation, dict):
            raise ValueError("violation must be an object")
        if enable_live_ai is not None and not isinstance(enable_live_ai, bool):
            raise ValueError("enable_live_ai must be a boolean when provided")
        if ai_model_name is not None and not isinstance(ai_model_name, str):
            raise ValueError("ai_model_name must be a string when provided")
        if not isinstance(ai_with_context, bool):
            raise ValueError("ai_with_context must be a boolean")

        logger.info(
            "AI generate request start id=%s issue_id=%s rule_id=%s",
            request_id,
            str((violation or {}).get("issue_id", "") or ""),
            str((violation or {}).get("rule_id", "") or ""),
        )
        result = self.app.generate_ai_review_for_violation(
            cast(Dict[str, Any], violation),
            enable_live_ai=enable_live_ai,
            ai_model_name=cast(Optional[str], ai_model_name),
            ai_with_context=bool(ai_with_context),
            request_id=request_id,
        )
        self._send_json(HTTPStatus.OK, result)
        logger.info("AI generate request done id=%s status=200 available=%s", request_id, bool(result.get("available", False)))
