let analysisData = {
    summary: { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
    violations: { P1: [], P2: [], P3: [] },
    output_dir: "",
    metrics: {},
    report_jobs: {},
};

const dashboardView = document.getElementById("dashboard-view");
const workspaceView = document.getElementById("workspace-view");
const navDashboard = document.getElementById("nav-dashboard");
const navWorkspace = document.getElementById("nav-workspace");
const btnAnalyze = document.getElementById("btn-analyze");

const totalText = document.getElementById("total-issues");
const criticalText = document.getElementById("critical-issues");
const warningText = document.getElementById("warning-issues");
const scoreBar = document.getElementById("score-bar");
const scoreText = document.getElementById("score-text");
const codeViewer = document.getElementById("code-viewer");

const resultTableWrap = document.querySelector(".result-table");
const resultBody = document.getElementById("result-body");
const violationDetail = document.getElementById("violation-detail");
const aiCard = document.getElementById("ai-suggestion-card");
const aiText = document.getElementById("ai-text");
const aiDiffPanel = document.getElementById("autofix-diff-panel");
const aiDiffText = document.getElementById("autofix-diff-text");
const aiValidationPanel = document.getElementById("autofix-validation-panel");
const aiValidationText = document.getElementById("autofix-validation-text");
const fileList = document.getElementById("file-list");
const filterMatrix = document.querySelector(".filter-matrix");
const ctrlppToggle = document.getElementById("toggle-ctrlppcheck");
const flushExcelBtn = document.getElementById("btn-flush-excel");
const excelJobStatusText = document.getElementById("excel-job-status");
const liveAiToggle = document.getElementById("toggle-live-ai");
const aiContextToggle = document.getElementById("toggle-ai-context");
const aiContextLabel = document.getElementById("label-ai-context");
let currentViewerFile = "";
let currentViewerResolvedName = "";
let currentViewerSource = "";
let currentViewerContent = "";
let currentViewerHeaderLines = 0;
let currentHighlightedLine = null;
let currentHighlightedLineNear = false;
let currentViewerLines = [];
let workspaceRowIndex = [];
let workspaceRenderToken = 0;
let workspaceFilteredRows = [];
const resultTableVirtualState = {
    scrollAttached: false,
    rowHeight: 34,
    renderedStart: -1,
    renderedEnd: -1,
};
let resultTableRenderQueued = false;
const autofixProposalCache = new Map();
const codeViewerVirtualState = {
    headerEl: null,
    linesWrap: null,
    topSpacer: null,
    visibleHost: null,
    bottomSpacer: null,
    lineHeight: 20,
    renderedStart: -1,
    renderedEnd: -1,
    scrollHandlerAttached: false,
};
let codeViewerWindowRenderQueued = false;
const filterControls = {
    p1: null,
    p2: null,
    p3: null,
    critical: null,
    warning: null,
    info: null,
};

navDashboard.onclick = () => {
    dashboardView.style.display = "block";
    workspaceView.style.display = "none";
};

navWorkspace.onclick = () => {
    dashboardView.style.display = "none";
    workspaceView.style.display = "flex";
    queueCodeViewerWindowRender(true);
};

function syncAiContextToggle() {
    const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
    if (aiContextToggle) {
        aiContextToggle.disabled = !liveEnabled;
        if (!liveEnabled) {
            aiContextToggle.checked = false;
        }
    }
    if (aiContextLabel) {
        aiContextLabel.style.opacity = liveEnabled ? "1" : "0.7";
    }
}

function setCodeViewerText(text) {
    if (!codeViewer) return;
    codeViewer.textContent = text || "";
    currentViewerLines = [];
    currentHighlightedLine = null;
    currentHighlightedLineNear = false;
    codeViewerVirtualState.headerEl = null;
    codeViewerVirtualState.linesWrap = null;
    codeViewerVirtualState.topSpacer = null;
    codeViewerVirtualState.visibleHost = null;
    codeViewerVirtualState.bottomSpacer = null;
    codeViewerVirtualState.renderedStart = -1;
    codeViewerVirtualState.renderedEnd = -1;
}

function attachCodeViewerVirtualScrollHandler() {
    if (!codeViewer || codeViewerVirtualState.scrollHandlerAttached) return;
    codeViewer.addEventListener("scroll", () => {
        queueCodeViewerWindowRender();
    });
    codeViewer.addEventListener("wheel", (event) => {
        // Keep wheel scrolling scoped to the code viewer to avoid outer pane/table scroll interference.
        event.stopPropagation();
    }, { passive: true });
    codeViewerVirtualState.scrollHandlerAttached = true;
}

function createCodeLineRow(lineNo, lineText) {
    const lineRow = document.createElement("div");
    lineRow.className = "code-line";
    lineRow.dataset.line = String(lineNo);

    const gutter = document.createElement("span");
    gutter.className = "code-line-no";
    gutter.textContent = String(lineNo);

    const text = document.createElement("span");
    text.className = "code-line-text";
    text.textContent = lineText && lineText.length ? lineText : " ";

    lineRow.appendChild(gutter);
    lineRow.appendChild(text);
    return lineRow;
}

function getCodeViewerLineAreaOffset() {
    if (!codeViewer || !codeViewerVirtualState.linesWrap) return 0;
    return Math.max(0, codeViewerVirtualState.linesWrap.offsetTop || 0);
}

function queueCodeViewerWindowRender(force = false) {
    if (!codeViewer || !codeViewerVirtualState.visibleHost) return;
    if (force) {
        codeViewerVirtualState.renderedStart = -1;
        codeViewerVirtualState.renderedEnd = -1;
    }
    if (codeViewerWindowRenderQueued) return;
    codeViewerWindowRenderQueued = true;
    window.requestAnimationFrame(() => {
        codeViewerWindowRenderQueued = false;
        renderCodeViewerWindow();
    });
}

function renderCodeViewerWindow() {
    if (!codeViewer) return;
    const lines = currentViewerLines || [];
    const totalLines = lines.length;
    const {
        topSpacer, visibleHost, bottomSpacer,
    } = codeViewerVirtualState;
    if (!topSpacer || !visibleHost || !bottomSpacer) return;

    if (totalLines <= 0) {
        topSpacer.style.height = "0px";
        bottomSpacer.style.height = "0px";
        visibleHost.replaceChildren();
        codeViewerVirtualState.renderedStart = 0;
        codeViewerVirtualState.renderedEnd = 0;
        return;
    }

    const headerOffset = getCodeViewerLineAreaOffset();
    const lineHeight = Math.max(16, getViewerLineHeight());
    codeViewerVirtualState.lineHeight = lineHeight;
    const viewportHeight = Math.max(1, codeViewer.clientHeight || 1);
    const scrollTop = Math.max(0, (codeViewer.scrollTop || 0) - headerOffset);
    const overscan = 14;
    let start = Math.floor(scrollTop / lineHeight) - overscan;
    if (!Number.isFinite(start)) start = 0;
    start = Math.max(0, start);
    const visibleCount = Math.max(1, Math.ceil(viewportHeight / lineHeight) + overscan * 2);
    const end = Math.min(totalLines, start + visibleCount);

    if (start === codeViewerVirtualState.renderedStart && end === codeViewerVirtualState.renderedEnd) {
        return;
    }

    codeViewerVirtualState.renderedStart = start;
    codeViewerVirtualState.renderedEnd = end;

    topSpacer.style.height = `${start * lineHeight}px`;
    bottomSpacer.style.height = `${Math.max(0, totalLines - end) * lineHeight}px`;

    const frag = document.createDocumentFragment();
    for (let idx = start; idx < end; idx += 1) {
        const lineNo = idx + 1;
        const row = createCodeLineRow(lineNo, lines[idx]);
        if (currentHighlightedLine === lineNo) {
            row.classList.add(currentHighlightedLineNear ? "line-highlight-near" : "line-highlight");
        }
        frag.appendChild(row);
    }
    visibleHost.replaceChildren(frag);

    // If measured line height drifted from estimate, re-render once with the real row height.
    const renderedRow = visibleHost.querySelector(".code-line");
    if (renderedRow) {
        const measured = renderedRow.getBoundingClientRect().height;
        if (Number.isFinite(measured) && measured > 0 && Math.abs(measured - lineHeight) > 1) {
            codeViewerVirtualState.lineHeight = measured;
            codeViewerVirtualState.renderedStart = -1;
            codeViewerVirtualState.renderedEnd = -1;
            queueCodeViewerWindowRender();
        }
    }
}

function renderCodeViewerContent(header, content) {
    if (!codeViewer) return;
    attachCodeViewerVirtualScrollHandler();
    codeViewer.replaceChildren();
    currentViewerLines = String(content || "").split("\n");

    let headerEl = null;
    if (header) {
        headerEl = document.createElement("div");
        headerEl.className = "code-viewer-header";
        headerEl.textContent = header;
        codeViewer.appendChild(headerEl);
    }

    const linesWrap = document.createElement("div");
    linesWrap.className = "code-lines";

    const topSpacer = document.createElement("div");
    topSpacer.className = "code-line-spacer";
    const visibleHost = document.createElement("div");
    visibleHost.className = "code-lines-window";
    const bottomSpacer = document.createElement("div");
    bottomSpacer.className = "code-line-spacer";

    linesWrap.appendChild(topSpacer);
    linesWrap.appendChild(visibleHost);
    linesWrap.appendChild(bottomSpacer);
    codeViewer.appendChild(linesWrap);

    codeViewerVirtualState.headerEl = headerEl;
    codeViewerVirtualState.linesWrap = linesWrap;
    codeViewerVirtualState.topSpacer = topSpacer;
    codeViewerVirtualState.visibleHost = visibleHost;
    codeViewerVirtualState.bottomSpacer = bottomSpacer;
    codeViewerVirtualState.renderedStart = -1;
    codeViewerVirtualState.renderedEnd = -1;

    currentHighlightedLine = null;
    currentHighlightedLineNear = false;
    codeViewer.scrollTop = 0;
    queueCodeViewerWindowRender(true);
}

function basenamePath(value) {
    const text = String(value || "");
    if (!text) return "";
    const parts = text.split(/[\\/]/);
    return parts[parts.length - 1] || text;
}

function positiveLineOrZero(value) {
    const line = Number.parseInt(value, 10);
    return Number.isFinite(line) && line > 0 ? line : 0;
}

function currentViewerLineCount() {
    if (!currentViewerContent) return 0;
    return String(currentViewerContent).split("\n").length;
}

function ensureAiStatusNode() {
    let node = document.getElementById("ai-status-inline");
    if (!node && aiCard) {
        node = document.createElement("p");
        node.id = "ai-status-inline";
        node.style.margin = "8px 0 0 0";
        node.style.fontSize = "12px";
        node.style.color = "#555";
        aiCard.appendChild(node);
    }
    return node;
}

function setAiStatusInline(message, color = "") {
    const node = ensureAiStatusNode();
    if (!node) return;
    node.textContent = message || "";
    node.style.display = message ? "block" : "none";
    node.style.color = color || "#555";
}

function setAutofixValidationPanel(text, { ok = true } = {}) {
    if (!aiValidationPanel || !aiValidationText) return;
    const msg = String(text || "");
    aiValidationText.textContent = msg;
    aiValidationPanel.style.display = msg ? "block" : "none";
    aiValidationText.style.color = ok ? "#1b5e20" : "#b71c1c";
    aiValidationText.style.background = ok ? "#f1f8e9" : "#ffebee";
    aiValidationText.style.borderColor = ok ? "rgba(46,125,50,0.2)" : "rgba(198,40,40,0.18)";
}

function formatAutofixValidationSummary(resultPayload) {
    const validation = (resultPayload && resultPayload.validation) || {};
    if (!validation || typeof validation !== "object") return "";
    const lines = [
        `hash_match: ${validation.hash_match ? "yes" : "no"}`,
        `anchors_match: ${validation.anchors_match ? "yes" : "no"}`,
        `syntax_check_passed: ${validation.syntax_check_passed ? "yes" : "no"}`,
        `heuristic_regression_count: ${Number.parseInt(validation.heuristic_regression_count || 0, 10) || 0}`,
        `ctrlpp_regression_count: ${Number.parseInt(validation.ctrlpp_regression_count || 0, 10) || 0}`,
    ];
    const errors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    if (errors.length) {
        lines.push("");
        lines.push("errors:");
        errors.slice(0, 10).forEach((err) => lines.push(`- ${String(err)}`));
    }
    return lines.join("\n");
}

function setExcelJobStatus(message, color = "") {
    if (!excelJobStatusText) return;
    excelJobStatusText.textContent = String(message || "");
    if (color) {
        excelJobStatusText.style.color = color;
    } else {
        excelJobStatusText.style.color = "rgba(255,255,255,0.92)";
    }
}

function excelJobsFromAnalysis() {
    const reportJobs = (analysisData && analysisData.report_jobs) || {};
    const excel = (reportJobs && reportJobs.excel) || {};
    return excel;
}

function updateExcelJobUiFromAnalysis() {
    const excel = excelJobsFromAnalysis();
    const pending = Number.parseInt(excel.pending_count || 0, 10) || 0;
    const running = Number.parseInt(excel.running_count || 0, 10) || 0;
    const completed = Number.parseInt(excel.completed_count || 0, 10) || 0;
    const failed = Number.parseInt(excel.failed_count || 0, 10) || 0;
    const total = (Array.isArray(excel.jobs) ? excel.jobs.length : 0);
    const hasSession = !!(analysisData && analysisData.output_dir);
    if (flushExcelBtn) {
        flushExcelBtn.disabled = !hasSession || total === 0;
        flushExcelBtn.textContent = (pending > 0 || running > 0) ? "Excel 생성 완료" : "Excel 상태 확인";
    }
    if (!hasSession || total === 0) {
        setExcelJobStatus("");
        return;
    }
    const statusParts = [`Excel ${completed}/${total}`];
    if (pending > 0) statusParts.push(`대기 ${pending}`);
    if (running > 0) statusParts.push(`실행 ${running}`);
    if (failed > 0) statusParts.push(`실패 ${failed}`);
    const color = failed > 0 ? "#ffcdd2" : (pending > 0 || running > 0) ? "#fff59d" : "#c8e6c9";
    setExcelJobStatus(statusParts.join(" | "), color);
}

function makeAiCardKey(violation, eventName, aiMatch) {
    const fileName = basenamePath((violation && (violation.file || violation.file_name || violation.filename)) || currentViewerFile);
    const objectName = String((violation && violation.object) || (aiMatch && aiMatch.object) || "");
    const evt = String(eventName || (aiMatch && aiMatch.event) || "Global");
    const review = String((aiMatch && aiMatch.review) || "");
    return [fileName, objectName, evt, review].join("||");
}

function jumpFailureMessage(jumpResult) {
    if (!jumpResult || jumpResult.ok) return "";
    const reason = String(jumpResult.reason || "");
    if (reason === "cross-file") {
        return "현재 표시 파일과 선택한 이슈 파일이 달라 위치 이동을 수행하지 않았습니다.";
    }
    if (reason === "load-failed") {
        return "선택한 이슈 파일을 불러오지 못해 위치 이동을 수행하지 못했습니다.";
    }
    if (reason === "no-viewer") {
        return "파일 내용이 아직 로드되지 않아 위치 이동을 수행하지 못했습니다. 좌측 파일 목록에서 파일을 먼저 선택하세요.";
    }
    if (reason === "no-match-reviewed") {
        return "REVIEWED.txt 기준 메시지/라인 매칭에 실패했습니다. (근처 하이라이트 포함)";
    }
    return "현재 표시 중인 코드뷰어 기준으로 위치를 찾지 못했습니다.";
}

function buildCodeViewerHeader(payload) {
    if (!payload || typeof payload !== "object") return "";
    const sourceMap = {
        reviewed: "REVIEWED.txt",
        normalized: "정규화 TXT",
        source: "원본 파일",
    };
    const sourceType = sourceMap[String(payload.source || "")] || String(payload.source || "파일");
    const resolvedName = String(payload.resolved_name || payload.file || "");
    return `// 표시 파일: ${resolvedName} (${sourceType})`;
}

async function applyAiSuggestion(violation, eventName, aiMatch) {
    const fileName = basenamePath((violation && (violation.file || violation.file_name || violation.filename)) || currentViewerFile);
    if (!fileName) throw new Error("대상 파일을 확인할 수 없습니다");
    const response = await fetch("/api/ai-review/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            file: fileName,
            object: String((violation && violation.object) || aiMatch.object || ""),
            event: String(eventName || aiMatch.event || "Global"),
            review: String(aiMatch.review || ""),
            output_dir: analysisData.output_dir || undefined,
        }),
    });

    let payload = {};
    let responseText = "";
    const contentType = String(response.headers.get("content-type") || "").toLowerCase();
    try {
        if (contentType.includes("application/json")) {
            payload = await response.json();
        } else {
            responseText = await response.text();
            try {
                payload = JSON.parse(responseText);
            } catch (_) {
                payload = {};
            }
        }
    } catch (_) {
        payload = {};
    }

    if (!response.ok) {
        throw new Error(payload.error || responseText || `AI 제안 적용 실패 (${response.status})`);
    }
    return payload;
}

function setAutofixDiffPanel(diffText) {
    if (!aiDiffPanel || !aiDiffText) return;
    const text = String(diffText || "");
    aiDiffText.textContent = text;
    aiDiffPanel.style.display = text ? "block" : "none";
}

async function prepareAutofixProposal(violation, eventName, aiMatch) {
    const fileName = basenamePath((violation && (violation.file || violation.file_name || violation.filename)) || currentViewerFile);
    if (!fileName) throw new Error("target file is missing");
    const response = await fetch("/api/autofix/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            file: fileName,
            object: String((violation && violation.object) || aiMatch.object || ""),
            event: String(eventName || aiMatch.event || "Global"),
            review: String(aiMatch.review || ""),
            issue_id: String((violation && violation.issue_id) || aiMatch.parent_issue_id || ""),
            session_id: analysisData.output_dir || undefined,
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const err = new Error(payload.error || `autofix prepare failed (${response.status})`);
        err.payload = payload;
        throw err;
    }
    return payload;
}

async function applyAutofixProposal(proposal, violation, eventName, aiMatch) {
    const fileName = basenamePath((violation && (violation.file || violation.file_name || violation.filename)) || currentViewerFile);
    const response = await fetch("/api/autofix/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            proposal_id: String((proposal && proposal.proposal_id) || ""),
            session_id: analysisData.output_dir || undefined,
            file: fileName || String((proposal && proposal.file) || ""),
            expected_base_hash: String((proposal && proposal.base_hash) || ""),
            apply_mode: "source_ctl",
            check_ctrlpp_regression: !!(ctrlppToggle && ctrlppToggle.checked),
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const message = payload.error_code
            ? `${payload.error || "autofix apply failed"} [${payload.error_code}]`
            : (payload.error || `autofix apply failed (${response.status})`);
        const err = new Error(message);
        err.payload = payload;
        throw err;
    }
    return payload;
}

async function flushExcelReports(options = {}) {
    const wait = !(options && options.wait === false);
    const timeoutSec = Number.isFinite(Number(options && options.timeout_sec)) ? Number(options.timeout_sec) : undefined;
    const response = await fetch("/api/report/excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: analysisData.output_dir || undefined,
            wait,
            timeout_sec: Number.isFinite(timeoutSec) ? timeoutSec : undefined,
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || `excel report flush failed (${response.status})`);
    }
    return payload;
}

async function loadCodeViewer(fileName, options = {}) {
    if (!fileName) return;
    const preferSource = !!(options && options.preferSource);
    try {
        const qs = new URLSearchParams({ name: String(fileName) });
        if (preferSource) {
            qs.set("prefer_source", "true");
        }
        const response = await fetch(`/api/file-content?${qs.toString()}`);
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "파일 내용을 불러오지 못했습니다.");
        }
        const header = buildCodeViewerHeader(payload);
        const content = String(payload.content || "");
        currentViewerFile = String(payload.file || fileName || "");
        currentViewerResolvedName = String(payload.resolved_name || "");
        currentViewerSource = String(payload.source || "");
        currentViewerContent = content;
        currentViewerHeaderLines = header ? 2 : 0;
        renderCodeViewerContent(header, content);
        return payload;
    } catch (err) {
        currentViewerSource = "";
        currentViewerContent = "";
        currentViewerHeaderLines = 0;
        setCodeViewerText(`// 파일 내용을 불러오지 못했습니다.\n// ${String((err && err.message) || err || "")}`);
        throw err;
    }
}

function updateDashboard() {
    totalText.textContent = analysisData.summary.total || 0;
    criticalText.textContent = analysisData.summary.critical || 0;
    warningText.textContent = analysisData.summary.warning || 0;
    scoreBar.style.width = `${analysisData.summary.score || 0}%`;
    scoreText.textContent = `점수: ${analysisData.summary.score || 0}/100`;
}

function initFilterControls() {
    if (!filterMatrix) return;
    const boxes = Array.from(filterMatrix.querySelectorAll("input[type='checkbox']"));
    [
        filterControls.p1,
        filterControls.p2,
        filterControls.p3,
        filterControls.critical,
        filterControls.warning,
        filterControls.info,
    ] = boxes;

    boxes.forEach((cb) => {
        cb.addEventListener("change", () => renderWorkspace());
    });
}

function getFilterState() {
    const read = (cb, fallback = true) => (cb ? !!cb.checked : fallback);
    return {
        sources: {
            p1: read(filterControls.p1),
            p2: read(filterControls.p2),
            p3: read(filterControls.p3),
        },
        severities: {
            critical: read(filterControls.critical),
            warning: read(filterControls.warning),
            info: read(filterControls.info),
        },
    };
}

function sourceFilterKey(source) {
    const key = String(source || "").toLowerCase();
    if (key.startsWith("p1")) return "p1";
    if (key.startsWith("p2")) return "p2";
    if (key.startsWith("p3")) return "p3";
    return "p1";
}

function severityFilterKey(rawSeverity) {
    const sev = String(rawSeverity || "").toLowerCase();
    if (["critical", "error", "fatal"].includes(sev)) return "critical";
    if (["warning", "high", "medium", "performance", "style", "portability"].includes(sev)) return "warning";
    return "info";
}

function normalizeSeverityKeyword(rawSeverity) {
    const sev = String(rawSeverity || "").toLowerCase();
    if (["critical", "error", "fatal"].includes(sev)) return "error";
    if (["warning", "high", "medium", "performance", "style", "portability"].includes(sev)) return "performance";
    return "information";
}

function shouldRenderRow(source, severity) {
    const filters = getFilterState();
    const srcKey = sourceFilterKey(source);
    const sevKey = severityFilterKey(severity);
    return !!filters.sources[srcKey] && !!filters.severities[sevKey];
}

function localizeCtrlppMessage(message) {
    const text = String(message || "");
    if (!text) return text;

    let out = text;
    out = out.replace(/^Uninitialized variable:\s*(.+)$/i, "초기화되지 않은 변수: $1");
    out = out.replace(
        /^It is potentially a safety issue to use the function\s+(.+)$/i,
        "함수 $1 사용은 잠재적인 안전성 이슈가 있습니다",
    );
    out = out.replace(
        /^It is really neccessary to use the function\s+(.+)$/i,
        "함수 $1 사용이 정말 필요한지 검토하세요",
    );
    out = out.replace(
        /^It is really necessary to use the function\s+(.+)$/i,
        "함수 $1 사용이 정말 필요한지 검토하세요",
    );
    out = out.replace(
        /^Cppcheck cannot find all the include files \(use --check-config for details\)$/i,
        "Cppcheck가 모든 include 파일을 찾지 못했습니다 (자세한 내용은 --check-config 사용)",
    );
    return out;
}

function localizeCtrlppSeverity(severity) {
    const sev = String(severity || "").toLowerCase();
    if (sev === "error") return "오류";
    if (sev === "information" || sev === "info") return "정보";
    if (sev === "performance") return "성능";
    if (sev === "warning") return "경고";
    if (sev === "style") return "스타일";
    if (sev === "portability") return "이식성";
    return severity || "정보";
}

function clearCodeViewerHighlight() {
    if (!codeViewer || !currentHighlightedLine) return;
    const prev = codeViewer.querySelector(`.code-line[data-line="${currentHighlightedLine}"]`);
    if (prev) {
        prev.classList.remove("line-highlight", "line-highlight-near");
    }
    currentHighlightedLine = null;
    currentHighlightedLineNear = false;
}

function highlightCodeViewerLine(lineNumber, near = false) {
    if (!codeViewer) return false;
    const line = Number.parseInt(lineNumber, 10);
    if (!Number.isFinite(line) || line <= 0) return false;
    if (currentViewerLines.length > 0 && (line > currentViewerLines.length)) return false;
    queueCodeViewerWindowRender();
    const target = codeViewer.querySelector(`.code-line[data-line="${line}"]`);
    if (!target) return false;

    clearCodeViewerHighlight();
    target.classList.add(near ? "line-highlight-near" : "line-highlight");
    currentHighlightedLine = line;
    currentHighlightedLineNear = !!near;

    // Re-trigger animation on repeated clicks.
    void target.offsetWidth;
    target.classList.add(near ? "line-highlight-near" : "line-highlight");
    return true;
}

function getViewerLineHeight() {
    if (!codeViewer) return 20;
    const rendered = codeViewer.querySelector(".code-line");
    if (rendered) {
        const h = rendered.getBoundingClientRect().height;
        if (Number.isFinite(h) && h > 0) return h;
    }
    if (Number.isFinite(codeViewerVirtualState.lineHeight) && codeViewerVirtualState.lineHeight > 0) {
        return codeViewerVirtualState.lineHeight;
    }
    const computed = window.getComputedStyle(codeViewer);
    const lineHeight = Number.parseFloat(computed.lineHeight || "");
    if (Number.isFinite(lineHeight) && lineHeight > 0) return lineHeight;
    const fontSize = Number.parseFloat(computed.fontSize || "");
    return Number.isFinite(fontSize) && fontSize > 0 ? fontSize * 1.4 : 20;
}

function scrollCodeViewerToLine(lineNumber, { near = false } = {}) {
    if (!codeViewer) return false;
    const line = Number.parseInt(lineNumber, 10);
    if (!Number.isFinite(line) || line <= 0) return false;
    const totalLines = currentViewerLines.length;
    const clampedLine = totalLines > 0 ? Math.min(line, totalLines) : line;
    const lineHeight = Math.max(16, getViewerLineHeight());
    const headerOffset = getCodeViewerLineAreaOffset();
    const centerOffset = Math.max(0, (codeViewer.clientHeight - lineHeight) / 2);
    const targetTop = Math.max(0, headerOffset + (clampedLine - 1) * lineHeight - centerOffset);
    codeViewer.scrollTop = targetTop;
    queueCodeViewerWindowRender(true);
    renderCodeViewerWindow();
    highlightCodeViewerLine(clampedLine, near);
    return true;
}

function messageSearchToken(message) {
    const text = String(message || "").trim();
    if (!text) return "";
    const patterns = [
        /Uninitialized variable:\s*([A-Za-z_][A-Za-z0-9_]*)/i,
        /function\s+([A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\))/i,
        /([A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\))/,
    ];
    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match && match[1]) return match[1].trim();
    }
    return text.slice(0, 80);
}

function scrollCodeViewerToMessage(message) {
    if (!currentViewerContent) return false;
    const token = messageSearchToken(message);
    if (!token) return false;
    const index = currentViewerContent.toLowerCase().indexOf(token.toLowerCase());
    if (index < 0) return false;
    const line = currentViewerContent.slice(0, index).split("\n").length;
    return scrollCodeViewerToLine(line, { near: true });
}

async function jumpCodeViewerToViolation(violation) {
    const sourceKey = sourceFilterKey(violation && violation.priority_origin);
    const isP2 = sourceKey === "p2";
    const isP1 = sourceKey === "p1";
    const fileHint = basenamePath(violation && (violation.file || violation.file_name || violation.filename));
    const currentFile = basenamePath(currentViewerFile);
    if (!currentViewerContent) return { ok: false, reason: "no-viewer" };
    if (fileHint && currentFile && fileHint !== currentFile) {
        if (isP1) {
            try {
                await loadCodeViewer(fileHint);
            } catch (_) {
                return { ok: false, reason: "load-failed" };
            }
        } else {
            return { ok: false, reason: "cross-file" };
        }
    }

    const isReviewed = currentViewerSource === "reviewed";
    const lineNo = positiveLineOrZero(violation && violation.line);
    const tryNearLine = () => {
        if (lineNo <= 0) return false;
        const maxLine = currentViewerLineCount();
        const clamped = maxLine > 0 ? Math.min(lineNo, maxLine) : lineNo;
        if (clamped <= 0) return false;
        return scrollCodeViewerToLine(clamped, { near: true });
    };

    if (isP2) {
        if (scrollCodeViewerToMessage(violation && violation.message)) {
            return { ok: true, reason: "hit-message" };
        }
        if (tryNearLine()) {
            return { ok: true, reason: "hit-line-near" };
        }
        return { ok: false, reason: isReviewed ? "no-match-reviewed" : "line-miss" };
    }

    if (!isReviewed && lineNo > 0 && scrollCodeViewerToLine(lineNo)) {
        return { ok: true, reason: "hit-line" };
    }

    if (scrollCodeViewerToMessage(violation && violation.message)) {
        return { ok: true, reason: "hit-message" };
    }

    if (tryNearLine()) {
        return { ok: true, reason: "hit-line-near" };
    }

    return { ok: false, reason: isReviewed ? "no-match-reviewed" : "line-miss" };
}
function createResultRow(source, object, severity, message, onclick) {
    const row = document.createElement("tr");
    row.className = "result-item-row";
    row.style.cursor = "pointer";

    const sourceCell = document.createElement("td");
    sourceCell.style.padding = "8px";
    const sourceBadge = document.createElement("span");
    sourceBadge.className = `badge badge-${String(source || "").toLowerCase()}`;
    sourceBadge.textContent = String(source || "N/A");
    sourceCell.appendChild(sourceBadge);

    const objectCell = document.createElement("td");
    objectCell.style.padding = "8px";
    objectCell.textContent = object || "N/A";

    const severityCell = document.createElement("td");
    severityCell.style.padding = "8px";
    const severitySpan = document.createElement("span");
    const severityRaw = String(severity || "Info");
    const severityClassKey = severityFilterKey(severityRaw);
    severitySpan.className = `severity-${severityClassKey}`;
    severitySpan.textContent = normalizeSeverityKeyword(severityRaw);
    severityCell.appendChild(severitySpan);

    const messageCell = document.createElement("td");
    messageCell.style.padding = "8px";
    messageCell.textContent = message || "";

    row.appendChild(sourceCell);
    row.appendChild(objectCell);
    row.appendChild(severityCell);
    row.appendChild(messageCell);
    row.onclick = () => {
        navWorkspace.onclick();
        if (typeof onclick === "function") {
            void onclick();
        }
    };
    return row;
}

function appendRow(source, object, severity, message, onclick) {
    resultBody.appendChild(createResultRow(source, object, severity, message, onclick));
}

function attachResultTableVirtualScrollHandler() {
    if (!resultTableWrap || resultTableVirtualState.scrollAttached) return;
    resultTableWrap.addEventListener("scroll", () => {
        queueResultTableWindowRender();
    });
    resultTableVirtualState.scrollAttached = true;
}

function getResultTableBodyOffset() {
    if (!resultTableWrap || !resultBody) return 0;
    const wrapRect = resultTableWrap.getBoundingClientRect();
    const bodyRect = resultBody.getBoundingClientRect();
    return Math.max(0, (bodyRect.top - wrapRect.top) + resultTableWrap.scrollTop);
}

function createResultSpacerRow(heightPx) {
    const spacerRow = document.createElement("tr");
    spacerRow.className = "result-spacer-row";
    const td = document.createElement("td");
    td.colSpan = 4;
    td.style.padding = "0";
    td.style.border = "0";
    td.style.height = `${Math.max(0, Math.round(heightPx))}px`;
    spacerRow.appendChild(td);
    return spacerRow;
}

function queueResultTableWindowRender(force = false) {
    if (!resultBody) return;
    if (force) {
        resultTableVirtualState.renderedStart = -1;
        resultTableVirtualState.renderedEnd = -1;
    }
    if (resultTableRenderQueued) return;
    resultTableRenderQueued = true;
    window.requestAnimationFrame(() => {
        resultTableRenderQueued = false;
        renderWorkspaceWindow();
    });
}

function renderWorkspaceWindow() {
    if (!resultBody) return;
    attachResultTableVirtualScrollHandler();

    const rows = Array.isArray(workspaceFilteredRows) ? workspaceFilteredRows : [];
    if (!resultTableWrap) {
        resultBody.replaceChildren();
        const frag = document.createDocumentFragment();
        rows.forEach((row) => {
            frag.appendChild(createResultRow(row.source, row.object, row.severity, row.message, row.onClick));
        });
        resultBody.appendChild(frag);
        return;
    }

    if (!rows.length) {
        resultBody.replaceChildren();
        resultTableVirtualState.renderedStart = 0;
        resultTableVirtualState.renderedEnd = 0;
        return;
    }

    const rowHeight = Math.max(24, Number(resultTableVirtualState.rowHeight || 34));
    const bodyOffset = getResultTableBodyOffset();
    const viewportHeight = Math.max(1, resultTableWrap.clientHeight || 1);
    const scrollTop = Math.max(0, (resultTableWrap.scrollTop || 0) - bodyOffset);
    const overscan = 18;
    let start = Math.floor(scrollTop / rowHeight) - overscan;
    if (!Number.isFinite(start)) start = 0;
    start = Math.max(0, start);
    const visibleCount = Math.max(1, Math.ceil(viewportHeight / rowHeight) + overscan * 2);
    const end = Math.min(rows.length, start + visibleCount);

    if (start === resultTableVirtualState.renderedStart && end === resultTableVirtualState.renderedEnd) {
        return;
    }
    resultTableVirtualState.renderedStart = start;
    resultTableVirtualState.renderedEnd = end;

    const frag = document.createDocumentFragment();
    frag.appendChild(createResultSpacerRow(start * rowHeight));
    for (let idx = start; idx < end; idx += 1) {
        const row = rows[idx];
        frag.appendChild(createResultRow(row.source, row.object, row.severity, row.message, row.onClick));
    }
    frag.appendChild(createResultSpacerRow(Math.max(0, (rows.length - end) * rowHeight)));
    resultBody.replaceChildren(frag);

    const measuredRow = resultBody.querySelector("tr.result-item-row");
    if (measuredRow) {
        const h = measuredRow.getBoundingClientRect().height;
        if (Number.isFinite(h) && h > 0 && Math.abs(h - resultTableVirtualState.rowHeight) > 1) {
            resultTableVirtualState.rowHeight = h;
            resultTableVirtualState.renderedStart = -1;
            resultTableVirtualState.renderedEnd = -1;
            queueResultTableWindowRender();
        }
    }
}

function buildWorkspaceRowIndex() {
    const nextRows = [];
    const p1Groups = analysisData.violations.P1 || [];
    const p2List = analysisData.violations.P2 || [];

    p1Groups.forEach((group) => {
        (group.violations || []).forEach((v) => {
            const violation = { ...v, object: group.object };
            violation.file = violation.file || group.object;
            nextRows.push({
                source: v.priority_origin || "P1",
                object: group.object,
                severity: v.severity,
                message: v.message,
                onClick: async () => {
                    showDetail(violation, group.event);
                    const jumpResult = await jumpCodeViewerToViolation(violation);
                    showDetail(violation, group.event, { jumpResult });
                },
            });
        });
    });

    p2List.forEach((v) => {
        nextRows.push({
            source: v.priority_origin || "P2",
            object: v.object || "Global",
            severity: v.severity || v.type || "Info",
            message: localizeCtrlppMessage(v.message || ""),
            onClick: async () => {
                showDetail(v, "Global");
                const jumpResult = await jumpCodeViewerToViolation(v);
                showDetail(v, "Global", { jumpResult });
            },
        });
    });

    workspaceRowIndex = nextRows;
}

function showDetail(violation, eventName, options = {}) {
    violationDetail.replaceChildren();
    const detailRows = [
        ["이슈 ID", violation.issue_id || "N/A"],
        ["우선순위 출처", violation.priority_origin || "N/A"],
        ["객체", violation.object || "N/A"],
        ["이벤트", eventName || "Global"],
    ];
    detailRows.forEach(([label, value]) => {
        const p = document.createElement("p");
        const strong = document.createElement("strong");
        strong.textContent = `${label}:`;
        p.appendChild(strong);
        p.append(` ${value}`);
        violationDetail.appendChild(p);
    });
    violationDetail.appendChild(document.createElement("hr"));
    const desc = document.createElement("p");
    const descLabel = document.createElement("strong");
    descLabel.textContent = "설명:";
    desc.appendChild(descLabel);
    const detailMessage = sourceFilterKey(violation.priority_origin || "P1") === "p2"
        ? localizeCtrlppMessage(violation.message || "")
        : (violation.message || "");
    desc.append(` ${detailMessage}`);
    violationDetail.appendChild(desc);

    const jumpMsg = jumpFailureMessage(options && options.jumpResult);
    if (jumpMsg) {
        const jumpNotice = document.createElement("p");
        jumpNotice.style.marginTop = "8px";
        jumpNotice.style.fontSize = "12px";
        jumpNotice.style.color = "#8a6d3b";
        jumpNotice.textContent = jumpMsg;
        violationDetail.appendChild(jumpNotice);
    }

    const aiMatch = (analysisData.violations.P3 || []).find((r) => {
        if (!r || typeof r !== "object") return false;
        if (r.parent_issue_id && violation.issue_id) {
            return r.parent_issue_id === violation.issue_id;
        }
        return String(r.object || "") === String(violation.object || "")
            && String(r.event || "Global") === String(eventName || "Global");
    });
    const aiStatus = String((aiMatch && aiMatch.status) || "Pending");
    if (aiMatch && aiStatus !== "Ignored") {
        aiCard.style.display = "block";
        aiText.textContent = aiMatch.review;
        const btnAiAccept = document.getElementById("btn-ai-accept");
        const btnAiDiff = document.getElementById("btn-ai-diff");
        const btnAiSourceApply = document.getElementById("btn-ai-source-apply");
        const btnAiIgnore = document.getElementById("btn-ai-ignore");
        const aiKey = makeAiCardKey(violation, eventName, aiMatch);
        const cachedAutofixProposal = autofixProposalCache.get(aiKey) || null;
        aiCard.dataset.aiKey = aiKey;
        setAiStatusInline("");
        setAutofixDiffPanel(cachedAutofixProposal ? cachedAutofixProposal.unified_diff : "");
        setAutofixValidationPanel("");

        if (btnAiAccept) {
            btnAiAccept.onclick = null;
            btnAiAccept.disabled = false;
            btnAiAccept.textContent = aiStatus === "Accepted" ? "REVIEWED Applied" : "Apply REVIEWED";
            btnAiAccept.style.opacity = "1";
        }
        if (btnAiDiff) {
            btnAiDiff.onclick = null;
            btnAiDiff.disabled = false;
            btnAiDiff.textContent = cachedAutofixProposal ? "Diff Ready" : "Diff Preview";
            btnAiDiff.style.opacity = "1";
        }
        if (btnAiSourceApply) {
            btnAiSourceApply.onclick = null;
            btnAiSourceApply.disabled = !cachedAutofixProposal;
            btnAiSourceApply.textContent = "Apply Source";
            btnAiSourceApply.style.opacity = cachedAutofixProposal ? "1" : "0.7";
        }
        if (btnAiIgnore) {
            btnAiIgnore.onclick = null;
            btnAiIgnore.disabled = false;
            btnAiIgnore.style.display = "inline-block";
        }

        if (aiStatus === "Accepted") {
            if (btnAiAccept) {
                btnAiAccept.disabled = true;
                btnAiAccept.style.opacity = "0.8";
            }
            if (btnAiDiff) {
                btnAiDiff.disabled = true;
                btnAiDiff.style.opacity = "0.8";
            }
            if (btnAiSourceApply) {
                btnAiSourceApply.disabled = true;
                btnAiSourceApply.style.opacity = "0.8";
                btnAiSourceApply.textContent = "Source Applied";
            }
            if (btnAiIgnore) {
                btnAiIgnore.disabled = true;
            }
            setAiStatusInline("Applied", "#2e7d32");
            setAutofixValidationPanel(
                cachedAutofixProposal ? formatAutofixValidationSummary(cachedAutofixProposal) : "",
                { ok: true },
            );
            return;
        }

        if (btnAiDiff) {
            btnAiDiff.onclick = async () => {
                const boundKey = aiKey;
                btnAiDiff.disabled = true;
                btnAiDiff.textContent = "Preparing...";
                if (btnAiSourceApply) {
                    btnAiSourceApply.disabled = true;
                    btnAiSourceApply.style.opacity = "0.7";
                }
                setAiStatusInline("Preparing source diff...", "#555");
                try {
                    const proposal = await prepareAutofixProposal(violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    autofixProposalCache.set(boundKey, proposal);
                    setAutofixDiffPanel(proposal.unified_diff || "");
                    btnAiDiff.textContent = "Diff Ready";
                    btnAiDiff.disabled = false;
                    btnAiDiff.style.opacity = "1";
                    if (btnAiSourceApply) {
                        btnAiSourceApply.disabled = false;
                        btnAiSourceApply.style.opacity = "1";
                    }
                    const generatorType = String((proposal && proposal.generator_type) || "llm").toUpperCase();
                    setAiStatusInline(`Source diff prepared (${generatorType}).`, "#1565c0");
                } catch (err) {
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    btnAiDiff.disabled = false;
                    btnAiDiff.textContent = "Diff Preview";
                    btnAiDiff.style.opacity = "1";
                    const msg = String((err && err.message) || err || "autofix prepare failed");
                    setAiStatusInline(`Diff prepare failed: ${msg}`, "#c62828");
                    alert(`Diff prepare failed: ${msg}`);
                }
            };
        }

        if (btnAiSourceApply) {
            btnAiSourceApply.onclick = async () => {
                const boundKey = aiKey;
                let proposal = autofixProposalCache.get(boundKey) || null;
                btnAiSourceApply.disabled = true;
                btnAiSourceApply.textContent = "Applying...";
                btnAiSourceApply.style.opacity = "0.8";
                if (btnAiDiff) btnAiDiff.disabled = true;
                if (btnAiIgnore) btnAiIgnore.disabled = true;
                setAiStatusInline("Applying source diff...", "#555");
                try {
                    if (!proposal) {
                        proposal = await prepareAutofixProposal(violation, eventName, aiMatch);
                        autofixProposalCache.set(boundKey, proposal);
                        setAutofixDiffPanel(proposal.unified_diff || "");
                    }
                    const result = await applyAutofixProposal(proposal, violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    autofixProposalCache.set(boundKey, { ...(proposal || {}), ...(result || {}) });
                    aiMatch.status = "Accepted";
                    if (btnAiAccept) {
                        btnAiAccept.disabled = true;
                        btnAiAccept.style.opacity = "0.8";
                    }
                    if (btnAiDiff) {
                        btnAiDiff.disabled = true;
                        btnAiDiff.style.opacity = "0.8";
                    }
                    btnAiSourceApply.textContent = "Source Applied";
                    btnAiSourceApply.disabled = true;
                    const generatorType = String((result && result.quality_metrics && result.quality_metrics.generator_type) || (proposal && proposal.generator_type) || "llm").toUpperCase();
                    setAiStatusInline(`Source patch applied (${generatorType}).`, "#2e7d32");
                    setAutofixValidationPanel(formatAutofixValidationSummary(result), {
                        ok: !(Array.isArray((result && result.validation && result.validation.errors)) && result.validation.errors.length),
                    });
                    const resultFile = basenamePath(result && result.file);
                    if (resultFile && basenamePath(currentViewerFile) === resultFile) {
                        try {
                            await loadCodeViewer(currentViewerFile || resultFile, { preferSource: true });
                        } catch (_) {
                            // fail-soft
                        }
                    }
                } catch (err) {
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    btnAiSourceApply.disabled = false;
                    btnAiSourceApply.textContent = "Apply Source";
                    btnAiSourceApply.style.opacity = "1";
                    if (btnAiDiff) btnAiDiff.disabled = false;
                    if (btnAiIgnore) btnAiIgnore.disabled = false;
                    const msg = String((err && err.message) || err || "autofix apply failed");
                    const payload = (err && err.payload) || {};
                    const errorCode = String((payload && payload.error_code) || "");
                    setAiStatusInline(`Source apply failed: ${msg}`, "#c62828");
                    const panelMsg = errorCode ? `${msg}\nerror_code: ${errorCode}` : String(msg || "");
                    setAutofixValidationPanel(panelMsg, { ok: false });
                    alert(`Source apply failed: ${msg}`);
                }
            };
        }

        if (btnAiAccept) {
            btnAiAccept.onclick = async () => {
                const boundKey = aiKey;
                btnAiAccept.disabled = true;
                btnAiAccept.textContent = "Applying...";
                btnAiAccept.style.opacity = "0.8";
                if (btnAiIgnore) {
                    btnAiIgnore.disabled = true;
                }
                setAiStatusInline("Applying REVIEWED...", "#555");
                try {
                    const result = await applyAiSuggestion(violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) {
                        return;
                    }
                    aiMatch.status = "Accepted";
                    const appliedBlocks = positiveLineOrZero(result && result.applied_blocks);
                    btnAiAccept.textContent = "REVIEWED Applied";
                    btnAiAccept.disabled = true;
                    setAiStatusInline(
                        appliedBlocks > 0 ? `REVIEWED applied (${appliedBlocks})` : "REVIEWED applied",
                        "#2e7d32",
                    );
                    if (btnAiIgnore) {
                        btnAiIgnore.disabled = true;
                    }

                    const resultFile = basenamePath(result && result.file);
                    if (resultFile && basenamePath(currentViewerFile) === resultFile) {
                        try {
                            await loadCodeViewer(currentViewerFile || resultFile);
                        } catch (_) {
                            // fail-soft
                        }
                    }
                } catch (err) {
                    if ((aiCard.dataset.aiKey || "") !== boundKey) {
                        return;
                    }
                    btnAiAccept.disabled = false;
                    btnAiAccept.textContent = "Apply REVIEWED";
                    btnAiAccept.style.opacity = "1";
                    if (btnAiIgnore) {
                        btnAiIgnore.disabled = false;
                    }
                    const msg = String((err && err.message) || err || "AI review apply failed");
                    setAiStatusInline(`REVIEWED apply failed: ${msg}`, "#c62828");
                    alert(`REVIEWED apply failed: ${msg}`);
                }
            };
        }

        if (btnAiIgnore) {
            btnAiIgnore.onclick = () => {
                aiMatch.status = "Ignored";
                aiCard.style.display = "none";
                setAiStatusInline("");
                setAutofixDiffPanel("");
                setAutofixValidationPanel("");
            };
        }
    } else {
        aiCard.style.display = "none";
        setAiStatusInline("");
        setAutofixDiffPanel("");
        setAutofixValidationPanel("");
    }
}
function renderWorkspace(options = {}) {
    workspaceRenderToken += 1;
    workspaceFilteredRows = (workspaceRowIndex || []).filter((row) => shouldRenderRow(row.source, row.severity));
    if ((options && options.resetScroll !== false) && resultTableWrap) {
        resultTableWrap.scrollTop = 0;
    }
    queueResultTableWindowRender(true);
}

function getSelectedFiles() {
    return Array.from(fileList.querySelectorAll("input[type='checkbox'][data-file]"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.getAttribute("data-file"));
}

function renderFileList(files) {
    fileList.replaceChildren();

    const selectAllWrap = document.createElement("div");
    const chkAll = document.createElement("input");
    chkAll.type = "checkbox";
    chkAll.id = "chk-all";
    chkAll.checked = true;
    const chkAllLabel = document.createElement("strong");
    chkAllLabel.textContent = "전체 선택";
    selectAllWrap.appendChild(chkAll);
    selectAllWrap.append(" ");
    selectAllWrap.appendChild(chkAllLabel);
    fileList.appendChild(selectAllWrap);

    files.forEach((file) => {
        const row = document.createElement("div");
        row.className = "file-item";
        row.style.cursor = "pointer";

        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = true;
        cb.setAttribute("data-file", file.name);
        cb.addEventListener("click", (event) => event.stopPropagation());

        const label = document.createElement("span");
        label.textContent = ` ${file.name}`;

        row.appendChild(cb);
        row.appendChild(label);
        row.addEventListener("click", () => {
            void loadCodeViewer(file.name).catch(() => { });
        });
        fileList.appendChild(row);
    });

    chkAll.addEventListener("change", () => {
        const checked = chkAll.checked;
        fileList.querySelectorAll("input[type='checkbox'][data-file]").forEach((cb) => {
            cb.checked = checked;
        });
    });
}

async function loadFiles() {
    const response = await fetch("/api/files");
    if (!response.ok) {
        throw new Error(`파일 목록 로드 실패 (${response.status})`);
    }
    const payload = await response.json();
    renderFileList(payload.files || []);
}

async function handleFlushExcelReportsClick() {
    if (!analysisData.output_dir) return;
    if (flushExcelBtn) {
        flushExcelBtn.disabled = true;
        flushExcelBtn.textContent = "Excel 생성 중...";
    }
    setExcelJobStatus("Excel 리포트 생성 상태 확인 중...", "#fff59d");
    try {
        const payload = await flushExcelReports({ wait: true, timeout_sec: 120 });
        analysisData.report_jobs = payload.report_jobs || {};
        if (payload.report_paths && payload.report_paths.excel) {
            // No direct UI list for excel filenames yet; status only.
        }
        updateExcelJobUiFromAnalysis();
    } catch (err) {
        const msg = String((err && err.message) || err || "Excel flush failed");
        setExcelJobStatus(`Excel 실패: ${msg}`, "#ffcdd2");
        alert(`Excel 생성 완료 처리 실패: ${msg}`);
    } finally {
        updateExcelJobUiFromAnalysis();
    }
}

btnAnalyze.onclick = async () => {
    try {
        const allowRawTxt = false;
        const enableCtrlppcheck = !!(ctrlppToggle && ctrlppToggle.checked);
        const enableLiveAi = !!(liveAiToggle && liveAiToggle.checked);
        const aiWithContext = enableLiveAi && !!(aiContextToggle && aiContextToggle.checked);
        const selected_files = getSelectedFiles();
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: "AI 보조",
                selected_files,
                allow_raw_txt: allowRawTxt,
                enable_ctrlppcheck: enableCtrlppcheck,
                enable_live_ai: enableLiveAi,
                ai_with_context: aiWithContext,
            }),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "분석 실패");
        }

        analysisData = {
            summary: payload.summary || { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
            violations: payload.violations || { P1: [], P2: [], P3: [] },
            output_dir: payload.output_dir || "",
            metrics: payload.metrics || {},
            report_jobs: payload.report_jobs || {},
        };
        workspaceRowIndex = [];
        autofixProposalCache.clear();
        setAutofixDiffPanel("");
        setAutofixValidationPanel("");
        buildWorkspaceRowIndex();

        updateDashboard();
        renderWorkspace();
        updateExcelJobUiFromAnalysis();
        navWorkspace.onclick();

        const selected = getSelectedFiles();
        if (selected.length > 0) {
            void loadCodeViewer(selected[0]).catch(() => { });
        }
    } catch (err) {
        alert(`분석 실패: ${(err && err.message) || String(err)}`);
    }
};

window.addEventListener("DOMContentLoaded", async () => {
    initFilterControls();
    attachResultTableVirtualScrollHandler();
    if (liveAiToggle) {
        liveAiToggle.addEventListener("change", syncAiContextToggle);
    }
    syncAiContextToggle();
    updateExcelJobUiFromAnalysis();
    updateDashboard();
    setCodeViewerText("// 파일을 선택하면 정규화 코드와 위반 항목을 볼 수 있습니다");
    try {
        await loadFiles();
    } catch (err) {
        alert(`파일 목록 초기화 실패: ${(err && err.message) || String(err)}`);
    }
});

window.addEventListener("resize", () => {
    queueCodeViewerWindowRender(true);
    queueResultTableWindowRender(true);
});
