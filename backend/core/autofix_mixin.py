"""AutoFix mixin facade composed from proposal, prepare, and apply helpers."""

from core.autofix_apply_engine import apply_with_engine
from core.autofix_instruction import instruction_to_hunks, normalize_instruction, validate_instruction
from core.autofix_apply_mixin import AutoFixApplyMixin, AutoFixQualityMetrics
from core.autofix_prepare_quality_mixin import AutoFixPrepareQualityMixin
from core.autofix_prepare_mixin import AutoFixPrepareMixin
from core.autofix_proposal_mixin import AutoFixProposalMixin


class AutoFixMixin(AutoFixProposalMixin, AutoFixPrepareQualityMixin, AutoFixPrepareMixin, AutoFixApplyMixin):
    """Compose autofix proposal preparation, application, and regression helpers.

    Host class must supply (via __init__ or other mixins):
        checker, ctrl_tool, ai_tool, reporter
        _sha256_text, _safe_int, _iso_now, _now_ts, _perf_now, _elapsed_ms
        _basic_syntax_check, _build_focus_snippet, _extract_review_code_block
        _extract_review_summary, _indent_lines, _line_indent
        _ensure_review_session, _get_review_session, _touch_review_session
        _resolve_review_session_and_file, _candidate_cached_filenames
        autofix_* config attributes
        AutoFixApplyError (from main module)
    """

    pass
