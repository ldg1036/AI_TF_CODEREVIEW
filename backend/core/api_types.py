from typing import Any, Dict, List, Optional, TypedDict


class AnalyzeSummaryPayload(TypedDict, total=False):
    failed_file_count: int
    successful_file_count: int


class AnalyzeResultPayload(TypedDict, total=False):
    summary: AnalyzeSummaryPayload
    metrics: Dict[str, Any]
    request_id: str


class AnalyzeRequestBody(TypedDict, total=False):
    mode: str
    selected_files: List[str]
    input_sources: List[Dict[str, str]]
    allow_raw_txt: bool
    enable_ctrlppcheck: Optional[bool]
    enable_live_ai: Optional[bool]
    ai_model_name: Optional[str]
    ai_with_context: bool
    defer_excel_reports: Optional[bool]


class AIReviewApplyRequestBody(TypedDict, total=False):
    file: str
    object: str
    event: str
    review: str
    output_dir: Optional[str]


class AIReviewGenerateRequestBody(TypedDict, total=False):
    violation: Dict[str, Any]
    enable_live_ai: Optional[bool]
    ai_model_name: Optional[str]
    ai_with_context: bool
    output_dir: Optional[str]
    session_id: Optional[str]


class AutofixPrepareRequestBody(TypedDict, total=False):
    file: str
    object: str
    event: str
    review: str
    output_dir: Optional[str]
    session_id: Optional[str]
    issue_id: str
    generator_preference: str
    allow_fallback: Optional[bool]
    prepare_mode: str


class AutofixApplyRequestBody(TypedDict, total=False):
    proposal_id: str
    prepared_proposal_id: str
    session_id: Optional[str]
    output_dir: Optional[str]
    file: str
    expected_base_hash: str
    apply_mode: str
    block_on_regression: Optional[bool]
    check_ctrlpp_regression: Optional[bool]


class ExcelFlushRequestBody(TypedDict, total=False):
    session_id: Optional[str]
    output_dir: Optional[str]
    wait: bool
    timeout_sec: Optional[int]


class RuleUpdateEntry(TypedDict, total=False):
    id: str
    enabled: bool


class RuleUpdateRequestBody(TypedDict, total=False):
    updates: List[RuleUpdateEntry]


class RuleRecordRequestBody(TypedDict, total=False):
    rule: Dict[str, Any]


class RuleDeleteRequestBody(TypedDict, total=False):
    id: str


class RuleImportRequestBody(TypedDict, total=False):
    rules: List[Dict[str, Any]]
    mode: str
    dry_run: bool


class P1TriageMatch(TypedDict, total=False):
    file: str
    line: int
    rule_id: str
    message: str
    issue_id: str


class P1TriageUpsertRequestBody(TypedDict, total=False):
    triage_key: str
    status: str
    reason: str
    note: str
    match: P1TriageMatch


class P1TriageDeleteRequestBody(TypedDict, total=False):
    triage_key: str


class AnalyzeProgressPayload(TypedDict, total=False):
    total_files: int
    completed_files: int
    failed_files: int
    percent: int
    current_file: str
    phase: str


class AnalyzeTimingPayload(TypedDict, total=False):
    elapsed_ms: int
    eta_ms: Optional[int]


class AnalyzeJobState(TypedDict, total=False):
    job_id: str
    status: str
    created_at: int
    started_at: Optional[int]
    finished_at: Optional[int]
    request: Dict[str, Any]
    progress: AnalyzeProgressPayload
    timing: AnalyzeTimingPayload
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    request_id: str
