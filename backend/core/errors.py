from typing import Any, Dict, Optional


class AppTypedError(RuntimeError):
    """Base typed error with stable error_code/details payload."""

    default_error_code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, error_code: str = "", details: Optional[Dict[str, Any]] = None):
        self.message = str(message or "").strip() or self.__class__.__name__
        self.error_code = str(error_code or self.default_error_code)
        self.details = details if isinstance(details, dict) else {}
        super().__init__(self.message)


class ReviewerError(AppTypedError):
    default_error_code = "AI_REVIEW_ERROR"


class ReviewerTransportError(ReviewerError):
    default_error_code = "AI_REVIEW_TRANSPORT_ERROR"


class ReviewerTimeoutError(ReviewerTransportError):
    default_error_code = "AI_REVIEW_TIMEOUT"


class ReviewerResponseError(ReviewerError):
    default_error_code = "AI_REVIEW_RESPONSE_ERROR"


class CtrlppError(AppTypedError):
    default_error_code = "CTRLPPCHECK_ERROR"


class CtrlppDownloadError(CtrlppError):
    default_error_code = "CTRLPPCHECK_DOWNLOAD_ERROR"


class CtrlppInstallError(CtrlppError):
    default_error_code = "CTRLPPCHECK_INSTALL_ERROR"


class CtrlppExecutionError(CtrlppError):
    default_error_code = "CTRLPPCHECK_EXECUTION_ERROR"
