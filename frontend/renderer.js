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
const inspectorTabDetail = document.getElementById("inspector-tab-detail");
const inspectorTabAi = document.getElementById("inspector-tab-ai");
const violationDetailPanel = document.getElementById("violation-detail-panel");
const aiPanelWrap = document.getElementById("ai-panel-wrap");
const violationDetail = document.getElementById("violation-detail");
const aiCard = document.getElementById("ai-suggestion-card");
const aiText = document.getElementById("ai-text");
const aiReviewToggleBtn = document.getElementById("btn-ai-review-toggle");
const aiTextFull = document.getElementById("ai-text-full");
const btnAiMore = document.getElementById("btn-ai-more");
const aiMoreActions = document.getElementById("ai-more-actions");
const aiDiffPanel = document.getElementById("autofix-diff-panel");
const aiDiffText = document.getElementById("autofix-diff-text");
const aiComparePanel = document.getElementById("autofix-compare-panel");
const aiCompareButtons = document.getElementById("autofix-compare-buttons");
const aiCompareMeta = document.getElementById("autofix-compare-meta");
const aiValidationPanel = document.getElementById("autofix-validation-panel");
const aiValidationText = document.getElementById("autofix-validation-text");
const fileList = document.getElementById("file-list");
const filterMatrix = document.querySelector(".filter-matrix");
const ctrlppToggle = document.getElementById("toggle-ctrlppcheck");
const flushExcelBtn = document.getElementById("btn-flush-excel");
const excelJobStatusText = document.getElementById("excel-job-status");
const analyzeProgressPanel = document.getElementById("analyze-progress-panel");
const analyzeProgressStatus = document.getElementById("analyze-progress-status");
const analyzeProgressBar = document.getElementById("analyze-progress-bar");
const analyzeProgressMeta = document.getElementById("analyze-progress-meta");
const liveAiToggle = document.getElementById("toggle-live-ai");
const aiContextToggle = document.getElementById("toggle-ai-context");
const aiContextLabel = document.getElementById("label-ai-context");
const aiContextHelp = document.getElementById("ai-context-help");
let currentViewerFile = "";
let currentViewerResolvedName = "";
let currentViewerSource = "";
let currentViewerContent = "";
let currentViewerHeaderLines = 0;
let currentHighlightedLine = null;
let currentHighlightedLineNear = false;
let currentViewerLines = [];
const functionScopeCacheByFile = new Map();
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
const AUTOFIX_PREPARE_MODE = "compare";
let aiReviewExpanded = false;
let activeInspectorTab = "detail";
let aiMoreMenuOpen = false;
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
    updateAiContextHelpText();
}

function updateAiContextHelpText() {
    if (aiContextHelp) {
        const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
        const withContext = liveEnabled && !!(aiContextToggle && aiContextToggle.checked);
        if (!liveEnabled) {
            aiContextHelp.textContent = "Live AI를 켜야 MCP 문맥을 사용할 수 있습니다.";
            return;
        }
        if (!withContext) {
            aiContextHelp.textContent = "현재는 MCP 문맥 없이 Live AI만 사용합니다.";
            return;
        }

        const timings = (analysisData && analysisData.metrics && analysisData.metrics.timings_ms) || {};
        const mcpMs = Number(timings.mcp_context);
        if (Number.isFinite(mcpMs) && mcpMs >= 0) {
            aiContextHelp.textContent = `MCP 문맥 요청을 시도했습니다 (${Math.round(mcpMs)}ms). 실패 시 자동으로 생략됩니다.`;
        } else {
            aiContextHelp.textContent = "분석 시 MCP 문맥을 요청합니다. MCP 서버가 없거나 실패하면 자동으로 생략됩니다.";
        }
    }
}

function setInspectorTab(tabName, hasAiSuggestion = false) {
    const normalized = tabName === "ai" ? "ai" : "detail";
    activeInspectorTab = normalized;

    if (inspectorTabDetail) {
        const active = normalized === "detail";
        inspectorTabDetail.classList.toggle("active", active);
        inspectorTabDetail.setAttribute("aria-selected", active ? "true" : "false");
    }

    if (inspectorTabAi) {
        const aiEnabled = !!hasAiSuggestion;
        inspectorTabAi.disabled = !aiEnabled;
        inspectorTabAi.classList.toggle("disabled", !aiEnabled);
        const active = normalized === "ai" && aiEnabled;
        inspectorTabAi.classList.toggle("active", active);
        inspectorTabAi.setAttribute("aria-selected", active ? "true" : "false");
    }

    if (violationDetailPanel) {
        violationDetailPanel.classList.toggle("active", normalized === "detail");
    }
    if (aiPanelWrap) {
        aiPanelWrap.classList.toggle("active", normalized === "ai");
    }
}

function resetInspectorTabsForViolation({ hasAiSuggestion = false, preferAi = false } = {}) {
    if (!hasAiSuggestion) {
        aiMoreMenuOpen = false;
        if (aiMoreActions) {
            aiMoreActions.style.display = "none";
        }
        setInspectorTab("detail", false);
        return;
    }
    setInspectorTab(preferAi ? "ai" : "detail", true);
}

function syncAiMoreMenuUi() {
    if (!aiMoreActions) return;
    const show = !!aiMoreMenuOpen;
    aiMoreActions.style.display = show ? "grid" : "none";
    if (btnAiMore) {
        btnAiMore.textContent = show ? "접기" : "더보기";
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

function countChar(text, ch) {
    let count = 0;
    const s = String(text || "");
    for (let i = 0; i < s.length; i += 1) {
        if (s[i] === ch) count += 1;
    }
    return count;
}

function isLikelyFunctionKeyword(name) {
    const lowered = String(name || "").toLowerCase();
    return lowered === "if"
        || lowered === "for"
        || lowered === "while"
        || lowered === "switch"
        || lowered === "catch"
        || lowered === "return";
}

function buildFunctionScopes(lines) {
    const src = Array.isArray(lines) ? lines : [];
    const scopes = [];
    const fnHeaderRe = /^\s*(?:[A-Za-z_]\w*\s+)*([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$/;

    for (let i = 0; i < src.length; i += 1) {
        const raw = String(src[i] || "");
        const trimmed = raw.trim();
        if (!trimmed || trimmed.startsWith("//") || trimmed.startsWith("*")) continue;

        const m = trimmed.match(fnHeaderRe);
        if (!m) continue;
        const fnName = String(m[1] || "").trim();
        if (!fnName || isLikelyFunctionKeyword(fnName)) continue;

        let openLineIdx = -1;
        if (trimmed.includes("{")) {
            openLineIdx = i;
        } else {
            for (let j = i + 1; j < Math.min(src.length, i + 4); j += 1) {
                const t = String(src[j] || "").trim();
                if (!t) continue;
                if (t.startsWith("{")) {
                    openLineIdx = j;
                }
                break;
            }
        }
        if (openLineIdx < 0) continue;

        let depth = 0;
        let endLineIdx = -1;
        for (let k = openLineIdx; k < src.length; k += 1) {
            const lineText = String(src[k] || "");
            depth += countChar(lineText, "{");
            depth -= countChar(lineText, "}");
            if (depth <= 0 && k >= openLineIdx) {
                endLineIdx = k;
                break;
            }
        }
        if (endLineIdx < openLineIdx) continue;

        scopes.push({
            name: fnName,
            start: i + 1,
            end: endLineIdx + 1,
        });
        i = Math.max(i, endLineIdx);
    }

    return scopes;
}

function findScopeForLine(scopes, lineNo) {
    const targetLine = positiveLineOrZero(lineNo);
    if (targetLine <= 0 || !Array.isArray(scopes) || scopes.length === 0) return null;
    let picked = null;
    for (const s of scopes) {
        const start = positiveLineOrZero(s && s.start);
        const end = positiveLineOrZero(s && s.end);
        if (start <= 0 || end <= 0) continue;
        if (targetLine >= start && targetLine <= end) {
            if (!picked || ((end - start) < (picked.end - picked.start))) {
                picked = { name: String((s && s.name) || "Global"), start, end };
            }
        }
    }
    return picked;
}

function cacheFunctionScopesForFile(fileName, content) {
    const key = basenamePath(fileName);
    if (!key) return;
    const scopes = buildFunctionScopes(String(content || "").split("\n"));
    functionScopeCacheByFile.set(key, scopes);
}

function getFunctionScopeFor(fileName, lineNo) {
    const key = basenamePath(fileName);
    if (!key) return null;
    return findScopeForLine(functionScopeCacheByFile.get(key) || [], lineNo);
}

function resolveFunctionScopeForViolation(fileName, lineNo) {
    const scope = getFunctionScopeFor(fileName, lineNo);
    if (!scope) return { name: "Global", start: 0, end: 0 };
    return scope;
}

async function fetchFileContentPayload(fileName, options = {}) {
    if (!fileName) throw new Error("file name is required");
    const preferSource = !!(options && options.preferSource);
    const qs = new URLSearchParams({ name: String(fileName) });
    if (preferSource) {
        qs.set("prefer_source", "true");
    }
    const response = await fetch(`/api/file-content?${qs.toString()}`);
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "파일 내용을 불러오지 못했습니다.");
    }
    return payload;
}

async function prepareFunctionScopeCacheForSelectedFiles(selectedFiles) {
    functionScopeCacheByFile.clear();
    const files = Array.isArray(selectedFiles)
        ? selectedFiles.map((name) => basenamePath(name)).filter((name) => !!name)
        : [];
    if (files.length === 0) return;

    const batchSize = 4;
    for (let i = 0; i < files.length; i += batchSize) {
        const batch = files.slice(i, i + batchSize);
        // Fail-soft: best-effort cache population. Missing files remain unresolved.
        // eslint-disable-next-line no-await-in-loop
        await Promise.all(batch.map(async (fileName) => {
            try {
                const payload = await fetchFileContentPayload(fileName, { preferSource: true });
                cacheFunctionScopesForFile(fileName, String(payload.content || ""));
            } catch (_) {
                // unresolved scope fallback
            }
        }));
    }
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
    const quality = (resultPayload && resultPayload.quality_metrics) || {};
    if ((!validation || typeof validation !== "object") && (!quality || typeof quality !== "object")) return "";
    const readValue = (key, fallback = "") => {
        if (validation && typeof validation === "object" && Object.prototype.hasOwnProperty.call(validation, key)) {
            return validation[key];
        }
        if (quality && typeof quality === "object" && Object.prototype.hasOwnProperty.call(quality, key)) {
            return quality[key];
        }
        return fallback;
    };
    const boolText = (value) => (value ? "yes" : "no");
    const toFloat = (value, fallback = 0) => {
        const parsed = Number.parseFloat(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };
    const toInt = (value, fallback = 0) => {
        const parsed = Number.parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : fallback;
    };
    const observeMode = String(readValue("benchmark_observe_mode", "strict_hash") || "strict_hash");
    const hashBypassed = !!readValue("hash_gate_bypassed", false);
    const tuningApplied = !!readValue("benchmark_tuning_applied", false);
    const tokenMinConfidence = toFloat(readValue("token_min_confidence_used", 0.8), 0.8);
    const tokenMinGap = toFloat(readValue("token_min_gap_used", 0.15), 0.15);
    const tokenMaxLineDrift = toInt(readValue("token_max_line_drift_used", 0), 0);
    const lines = [
        `hash_match: ${boolText(!!readValue("hash_match", false))}`,
        `anchors_match: ${boolText(!!readValue("anchors_match", false))}`,
        `syntax_check_passed: ${boolText(!!readValue("syntax_check_passed", false))}`,
        `heuristic_regression_count: ${toInt(readValue("heuristic_regression_count", 0), 0)}`,
        `ctrlpp_regression_count: ${toInt(readValue("ctrlpp_regression_count", 0), 0)}`,
        `locator_mode: ${String(readValue("locator_mode", "")) || "-"}`,
        `apply_engine_mode: ${String(readValue("apply_engine_mode", "")) || "-"}`,
        `apply_engine_fallback_reason: ${String(readValue("apply_engine_fallback_reason", "")) || "-"}`,
        `benchmark_observe_mode: ${observeMode}`,
        `hash_gate_bypassed: ${boolText(hashBypassed)}`,
        `benchmark_tuning_applied: ${boolText(tuningApplied)}`,
        `token_min_confidence_used: ${tokenMinConfidence}`,
        `token_min_gap_used: ${tokenMinGap}`,
        `token_max_line_drift_used: ${tokenMaxLineDrift}`,
    ];
    const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    const mergedErrorSet = new Set([...validationErrors, ...qualityErrors].map((item) => String(item || "").trim()).filter(Boolean));
    const errors = Array.from(mergedErrorSet);
    if (errors.length) {
        lines.push("");
        lines.push("errors:");
        errors.slice(0, 10).forEach((err) => lines.push(`- ${String(err)}`));
    }
    return lines.join("\n");
}

function buildAiReviewSummary(reviewText) {
    const raw = String(reviewText || "");
    if (!raw.trim()) return "AI 개선 제안";
    const noCodeBlock = raw.replace(/```[\s\S]*?```/g, " ").replace(/`([^`]+)`/g, "$1");
    const cleaned = noCodeBlock
        .split(/\r?\n/)
        .map((line) => line.replace(/^\s*(요약|summary)\s*[:：-]?\s*/i, "").trim())
        .filter((line) => line.length > 0)
        .join(" ");
    const sentence = cleaned.split(/(?<=[.!?])\s+/)[0] || cleaned;
    const compact = sentence.replace(/\s+/g, " ").trim();
    if (!compact) return "AI 개선 제안";
    if (compact.length <= 200) return compact;
    return `${compact.slice(0, 197)}...`;
}

function setAiReviewText(reviewText) {
    const full = String(reviewText || "").trim();
    if (aiText) {
        aiText.textContent = buildAiReviewSummary(full);
    }
    if (aiTextFull) {
        aiTextFull.textContent = full;
        aiTextFull.style.display = aiReviewExpanded && full ? "block" : "none";
    }
    if (aiReviewToggleBtn) {
        aiReviewToggleBtn.style.display = full ? "inline-block" : "none";
        aiReviewToggleBtn.textContent = aiReviewExpanded ? "접기" : "자세히 보기";
    }
}

function hasAutofixValidationErrors(resultPayload) {
    const validation = (resultPayload && resultPayload.validation) || {};
    const quality = (resultPayload && resultPayload.quality_metrics) || {};
    const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    return (validationErrors.length + qualityErrors.length) > 0;
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
    if (reason === "no-locatable-position") {
        return "이 항목은 위치 정보(line/file)가 없어 줄 이동을 수행하지 않습니다.";
    }
    if (reason === "load-source-failed") {
        return "P2는 원본 .ctl 기준이라 source 로드 실패 시 줄 이동을 중단했습니다.";
    }
    if (reason === "source-not-found") {
        return "대상 .ctl source 파일을 찾지 못해 줄 이동을 수행할 수 없습니다.";
    }
    if (reason === "invalid-target-file") {
        return "P2 항목의 대상 파일이 .ctl 형식이 아니어서 위치 이동을 수행하지 않았습니다.";
    }
    if (reason === "cross-file") {
        return "현재 표시 파일과 선택한 이슈 파일이 달라 위치 이동을 수행하지 않았습니다.";
    }
    if (reason === "load-failed") {
        return "선택한 이슈 파일을 불러오지 못해 위치 이동을 수행하지 못했습니다.";
    }
    if (reason === "no-viewer") {
        return "파일 내용을 아직 불러오지 않아 위치 이동을 수행하지 못했습니다. 왼쪽 파일 목록에서 파일을 먼저 선택하세요.";
    }
    if (reason === "no-match-reviewed") {
        return "REVIEWED.txt 기준 메시지/라인 매칭에 실패했습니다. (근접 하이라이트 포함)";
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
    if (!fileName) throw new Error("대상 파일을 확인할 수 없습니다.");
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

function normalizeAutofixBundle(payload) {
    const data = (payload && typeof payload === "object") ? payload : {};
    const rawProposals = Array.isArray(data.proposals) && data.proposals.length ? data.proposals : [data];
    const proposals = rawProposals.filter((item) => item && typeof item === "object" && item.proposal_id);
    const fallbackProposal = proposals[0] || {};
    let selected = String(data.selected_proposal_id || "");
    if (!selected || !proposals.some((item) => String(item.proposal_id) === selected)) {
        const ruleProposal = proposals.find((item) => String(item.generator_type || "").toLowerCase() === "rule");
        selected = String((ruleProposal || fallbackProposal).proposal_id || "");
    }
    return {
        proposals,
        selected_proposal_id: selected,
        active_proposal_id: selected,
        compare_meta: (data.compare_meta && typeof data.compare_meta === "object") ? data.compare_meta : null,
    };
}

function getActiveAutofixProposal(bundle) {
    if (!bundle || !Array.isArray(bundle.proposals) || !bundle.proposals.length) return null;
    const activeId = String(bundle.active_proposal_id || bundle.selected_proposal_id || "");
    const found = bundle.proposals.find((item) => String(item.proposal_id) === activeId);
    return found || bundle.proposals[0];
}

function renderAutofixComparePanel(bundle, onSelect) {
    if (!aiComparePanel || !aiCompareButtons || !aiCompareMeta) return;
    const proposals = (bundle && Array.isArray(bundle.proposals)) ? bundle.proposals : [];
    if (proposals.length <= 1) {
        aiCompareButtons.innerHTML = "";
        aiCompareMeta.textContent = "";
        aiComparePanel.style.display = "none";
        return;
    }
    aiCompareButtons.innerHTML = "";
    const activeId = String((bundle && bundle.active_proposal_id) || (bundle && bundle.selected_proposal_id) || "");
    proposals.forEach((proposal) => {
        const pid = String((proposal && proposal.proposal_id) || "");
        if (!pid) return;
        const gen = String((proposal && proposal.generator_type) || "unknown").toUpperCase();
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = gen;
        btn.style.padding = "4px 8px";
        btn.style.borderRadius = "4px";
        btn.style.border = "1px solid rgba(21,101,192,0.35)";
        btn.style.cursor = "pointer";
        const active = pid === activeId;
        btn.style.background = active ? "#1565c0" : "#ffffff";
        btn.style.color = active ? "#ffffff" : "#1565c0";
        btn.onclick = () => onSelect(pid);
        aiCompareButtons.appendChild(btn);
    });
    const generatedCount = proposals.length;
    aiCompareMeta.textContent = `compare mode: ${generatedCount} candidates`;
    aiComparePanel.style.display = "block";
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
            prepare_mode: AUTOFIX_PREPARE_MODE,
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const err = new Error(payload.error || `autofix prepare failed (${response.status})`);
        err.payload = payload;
        throw err;
    }
    return normalizeAutofixBundle(payload);
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
        const payload = await fetchFileContentPayload(fileName, { preferSource });
        const header = buildCodeViewerHeader(payload);
        const content = String(payload.content || "");
        currentViewerFile = String(payload.file || fileName || "");
        currentViewerResolvedName = String(payload.resolved_name || "");
        currentViewerSource = String(payload.source || "");
        currentViewerContent = content;
        cacheFunctionScopesForFile(currentViewerFile || fileName, content);
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

function pickHigherSeverity(currentSeverity, candidateSeverity) {
    const rank = { info: 0, warning: 1, critical: 2 };
    const currentKey = severityFilterKey(currentSeverity);
    const candidateKey = severityFilterKey(candidateSeverity);
    return (rank[candidateKey] || 0) > (rank[currentKey] || 0) ? candidateSeverity : currentSeverity;
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
        "함수 $1 사용은 잠재적인 안전성 이슈가 될 수 있습니다",
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
        "Cppcheck가 일부 include 파일을 찾지 못했습니다 (--check-config로 상세 확인)",
    );
    return out;
}

function localizeCtrlppByRuleId(ruleId, message, verbose) {
    const id = String(ruleId || "").toLowerCase();
    const msg = String(message || "");
    const details = String(verbose || "");
    const mapping = [
        { keys: ["uninitializedvariable", "uninitvar"], text: "초기화되지 않은 변수 사용 가능성이 있습니다." },
        { keys: ["nullpointer", "nullpointerdereference"], text: "널 포인터 접근 가능성이 있습니다." },
        { keys: ["checklibrarynoreturn", "noreturn"], text: "반환값/예외 처리 누락 가능성이 있습니다." },
        { keys: ["memleak", "resourceleak"], text: "메모리/자원 해제 누락 가능성이 있습니다." },
        { keys: ["unusedfunction", "unusedvariable"], text: "미사용 코드(함수/변수)가 포함되어 있습니다." },
        { keys: ["syntaxerror", "parseerror"], text: "문법/구문 오류 가능성이 있습니다." },
        { keys: ["bufferaccessoutofbounds", "outofbounds"], text: "배열/버퍼 경계 초과 접근 가능성이 있습니다." },
        { keys: ["useafterfree"], text: "해제된 자원 접근(use-after-free) 가능성이 있습니다." },
        { keys: ["shadowvariable", "shadowedvariable"], text: "변수 그림자(shadowing)로 인한 혼동 가능성이 있습니다." },
    ];
    for (const entry of mapping) {
        if (entry.keys.some((k) => id.includes(k))) return entry.text;
    }
    if (id === "ctrlppcheck.info") {
        const localized = localizeCtrlppMessage(msg || details);
        return localized || "CtrlppCheck 정보성 메시지입니다.";
    }
    return "";
}

function localizeCtrlppByPattern(message) {
    const text = String(message || "").trim();
    if (!text) return "";
    const localized = localizeCtrlppMessage(text);
    if (localized !== text) return localized;

    const nullMatch = text.match(/null(?:\s+pointer)?\s+([A-Za-z_][A-Za-z0-9_]*)?/i);
    if (nullMatch) {
        const name = String(nullMatch[1] || "").trim();
        return name ? `포인터 ${name}가 null일 수 있어 접근 시 오류 가능성이 있습니다.` : "null 포인터 접근 가능성이 있습니다.";
    }
    const callMatch = text.match(/function\s+([A-Za-z_][A-Za-z0-9_]*)/i);
    if (callMatch) return `함수 ${callMatch[1]} 호출부에서 안전성/예외 처리 점검이 필요합니다.`;
    const varMatch = text.match(/variable:\s*([A-Za-z_][A-Za-z0-9_]*)/i);
    if (varMatch) return `변수 ${varMatch[1]} 사용 전에 초기화/유효성 검증이 필요합니다.`;
    return "";
}

function truncateMiddle(text, maxLen = 140) {
    const s = String(text || "").trim();
    if (s.length <= maxLen) return s;
    const keep = Math.max(20, Math.floor((maxLen - 3) / 2));
    return `${s.slice(0, keep)}...${s.slice(s.length - keep)}`;
}

function buildP2LocalizedMessage(violation) {
    const ruleId = String((violation && violation.rule_id) || "");
    const rawMessage = String((violation && violation.message) || "").trim();
    const verbose = String((violation && violation.verbose) || "").trim();
    const byRule = localizeCtrlppByRuleId(ruleId, rawMessage, verbose);
    const byPattern = localizeCtrlppByPattern(rawMessage || verbose);
    const localizedText = byRule || byPattern || (rawMessage ? `(원문) ${truncateMiddle(rawMessage, 180)}` : "P2 점검 메시지");
    const shortText = truncateMiddle(localizedText.replace(/^\(원문\)\s*/i, ""), 80) || "P2 점검 메시지";
    return { shortText, localizedText, rawText: rawMessage || verbose || "" };
}

function buildP2DetailBlocks(violation) {
    const ruleId = String((violation && violation.rule_id) || "unknown");
    const severity = String((violation && (violation.severity || violation.type)) || "information").toLowerCase();
    const lineNo = positiveLineOrZero(violation && violation.line);
    const fileName = basenamePath(violation && (violation.file || violation.file_name || violation.filename));
    const localized = buildP2LocalizedMessage(violation);

    const cause = localized.localizedText || "P2 정적 분석에서 위험 신호가 감지되었습니다.";
    const impactMap = {
        error: "실행 중 오류 또는 안전성 문제로 이어질 가능성이 높습니다.",
        warning: "기능 안정성/유지보수성 저하 가능성이 있습니다.",
        performance: "성능 저하 또는 불필요한 리소스 사용이 발생할 수 있습니다.",
        information: "즉시 오류는 아니지만 코드 품질 개선이 필요할 수 있습니다.",
        style: "가독성/일관성 저하로 유지보수 비용이 증가할 수 있습니다.",
        portability: "환경/버전 차이에서 동작 차이가 발생할 수 있습니다.",
    };
    const impact = impactMap[severity] || "코드 품질 및 안정성에 부정적 영향이 있을 수 있습니다.";

    let action = "관련 코드에서 입력값 검증, 예외 처리, 반환값 확인을 추가하고 동일 패턴을 함께 점검하세요.";
    const lowerRule = ruleId.toLowerCase();
    if (lowerRule.includes("uninitialized")) {
        action = "변수 선언 시 초기값을 명시하고 사용 전에 초기화 경로를 보장하세요.";
    } else if (lowerRule.includes("null")) {
        action = "포인터/핸들 사용 전 null 검사와 실패 분기 처리를 추가하세요.";
    } else if (lowerRule.includes("noreturn")) {
        action = "함수 반환값을 확인하고 실패 시 로그/복구 로직을 추가하세요.";
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleId || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `원인: ${cause}`,
        impact: `영향: ${impact}`,
        action: `권장조치: ${action} (근거: ${evidence})`,
        raw: localized.rawText ? `원문: ${truncateMiddle(localized.rawText, 180)}` : "",
    };
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
    const lineNo = positiveLineOrZero(violation && violation.line);
    const ruleId = String((violation && violation.rule_id) || "").toLowerCase();
    const currentFile = basenamePath(currentViewerFile);

    if (
        isP2
        && (
            ((!fileHint || !String(fileHint).trim()) && lineNo <= 0)
            || (ruleId === "ctrlppcheck.info" && lineNo <= 0)
        )
    ) {
        return { ok: false, reason: "no-locatable-position" };
    }

    if (!currentViewerContent) return { ok: false, reason: "no-viewer" };

    if (isP2 && fileHint && !String(fileHint).toLowerCase().endsWith(".ctl")) {
        return { ok: false, reason: "invalid-target-file" };
    }

    const ensureP2SourceView = async () => {
        const targetFile = fileHint || basenamePath(currentViewerFile);
        if (!targetFile) {
            return { ok: false, reason: "source-not-found" };
        }
        if (isP2 && !String(targetFile).toLowerCase().endsWith(".ctl")) {
            return { ok: false, reason: "invalid-target-file" };
        }
        const shouldReload =
            basenamePath(currentViewerFile) !== targetFile
            || currentViewerSource === "reviewed"
            || currentViewerSource === "normalized"
            || currentViewerSource !== "source";
        if (!shouldReload) return { ok: true };
        try {
            await loadCodeViewer(targetFile, { preferSource: true });
        } catch (_) {
            return { ok: false, reason: "load-source-failed" };
        }
        if (String(currentViewerSource || "") !== "source") {
            return { ok: false, reason: "source-not-found" };
        }
        return { ok: true };
    };

    if (fileHint && currentFile && fileHint !== currentFile) {
        if (isP1 || isP2) {
            try {
                await loadCodeViewer(fileHint, isP2 ? { preferSource: true } : {});
            } catch (_) {
                return { ok: false, reason: "load-failed" };
            }
        } else {
            return { ok: false, reason: "cross-file" };
        }
    }

    if (isP2) {
        const sourceReady = await ensureP2SourceView();
        if (!sourceReady.ok) {
            clearCodeViewerHighlight();
            return sourceReady;
        }
    }

    const isReviewed = currentViewerSource === "reviewed";
    const tryNearLine = () => {
        if (lineNo <= 0) return false;
        const maxLine = currentViewerLineCount();
        const clamped = maxLine > 0 ? Math.min(lineNo, maxLine) : lineNo;
        if (clamped <= 0) return false;
        return scrollCodeViewerToLine(clamped, { near: true });
    };

    if (isP2) {
        if (tryNearLine()) {
            return { ok: true, reason: "hit-line-near" };
        }
        if (scrollCodeViewerToMessage(violation && violation.message)) {
            return { ok: true, reason: "hit-message" };
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
    const p3List = analysisData.violations.P3 || [];
    const jumpTargetGroups = new Map();
    const fallbackDedup = new Map();
    const unresolvedFallbackStats = new Map();
    const fallbackCandidates = [];

    p1Groups.forEach((group) => {
        (group.violations || []).forEach((v) => {
            const violation = { ...v, object: group.object };
            violation.file = violation.file || group.object;
            const source = v.priority_origin || "P1";
            const sourceKey = sourceFilterKey(source);
            const fileKey = basenamePath(violation.file || group.object || "");
            const ruleIdKey = String(violation.rule_id || "");
            const messageKey = String(violation.message || "");
            const lineValue = positiveLineOrZero(violation.line);
            const fnScope = resolveFunctionScopeForViolation(violation.file || group.object || "", lineValue);
            const fnScopeName = String((fnScope && fnScope.name) || "Global");
            const fnScopeStart = positiveLineOrZero(fnScope && fnScope.start);
            const fnScopeEnd = positiveLineOrZero(fnScope && fnScope.end);
            const fnScopeResolved = !!(fnScopeStart > 0 && fnScopeEnd > 0);

            const candidate = {
                violation,
                eventName: group.event,
                rowObject: group.object,
                severity: v.severity,
                message: v.message,
                source,
                sourceKey,
                fileKey,
                ruleIdKey,
                messageKey,
                lineValue,
                fnScopeName,
                fnScopeStart,
                fnScopeEnd,
                fnScopeResolved,
            };

            if (lineValue > 0) {
                const jumpKey = [sourceKey, fileKey, lineValue].join("||");
                const existingJump = jumpTargetGroups.get(jumpKey);
                if (existingJump) {
                    existingJump.count += 1;
                    existingJump.lines.push(lineValue);
                    if (ruleIdKey && !existingJump.ruleIds.includes(ruleIdKey)) existingJump.ruleIds.push(ruleIdKey);
                    if (messageKey && !existingJump.messages.includes(messageKey)) existingJump.messages.push(messageKey);
                    const issueId = String(violation.issue_id || "");
                    if (issueId && !existingJump.issueIds.includes(issueId)) existingJump.issueIds.push(issueId);
                    existingJump.severity = pickHigherSeverity(existingJump.severity, candidate.severity);
                    return;
                }
                jumpTargetGroups.set(jumpKey, {
                    count: 1,
                    lines: [lineValue],
                    primaryLine: lineValue,
                    representativeViolation: candidate.violation,
                    eventName: candidate.eventName,
                    rowObject: candidate.rowObject,
                    severity: candidate.severity,
                    message: candidate.message,
                    source: candidate.source,
                    fileKey: candidate.fileKey,
                    ruleIds: ruleIdKey ? [ruleIdKey] : [],
                    messages: messageKey ? [messageKey] : [],
                    issueIds: String(violation.issue_id || "") ? [String(violation.issue_id || "")] : [],
                });
                return;
            }

            fallbackCandidates.push(candidate);
            if (!fnScopeResolved) {
                const statKey = [sourceKey, fileKey, ruleIdKey, messageKey].join("||");
                const stat = unresolvedFallbackStats.get(statKey);
                if (!stat) {
                    unresolvedFallbackStats.set(statKey, { count: 1, minLine: 0, maxLine: 0 });
                } else {
                    stat.count += 1;
                }
            }
        });
    });

    jumpTargetGroups.forEach((entry) => {
        const uniqueLines = Array.from(new Set((entry.lines || []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
        const primaryLine = positiveLineOrZero(entry.primaryLine) || uniqueLines[0] || 0;
        const violationWithCount = {
            ...entry.representativeViolation,
            _duplicate_count: entry.count,
            _duplicate_lines: uniqueLines,
            _primary_line: primaryLine,
            _function_scope_name: "line-target",
            _function_scope_start: 0,
            _function_scope_end: 0,
            _function_scope_resolved: false,
            _dedup_mode: "jump_target",
            _grouping_mode: "jump_target",
            _group_rule_ids: Array.isArray(entry.ruleIds) ? entry.ruleIds : [],
            _group_messages: Array.isArray(entry.messages) ? entry.messages : [],
            _group_issue_ids: Array.isArray(entry.issueIds) ? entry.issueIds : [],
        };
        if (primaryLine > 0) {
            violationWithCount.line = primaryLine;
        }
        nextRows.push({
            source: entry.source || "P1",
            object: entry.rowObject || violationWithCount.object || "Global",
            severity: entry.severity,
            message: entry.message,
            onClick: async () => {
                showDetail(violationWithCount, entry.eventName);
                const jumpResult = await jumpCodeViewerToViolation(violationWithCount);
                showDetail(violationWithCount, entry.eventName, { jumpResult });
            },
        });
    });

    fallbackCandidates.forEach((item) => {
        const fnScopeRange = item.fnScopeResolved ? `${item.fnScopeStart}-${item.fnScopeEnd}` : "unresolved";
        const dedupMode = item.fnScopeResolved ? "strong" : "none";
        const dedupKey = dedupMode === "strong"
            ? [item.sourceKey, item.fileKey, item.fnScopeName, fnScopeRange, item.ruleIdKey, item.messageKey].join("||")
            : [item.sourceKey, item.fileKey, "scope:unresolved:none", item.ruleIdKey, item.messageKey, `${item.lineValue || 0}:${String(item.violation.issue_id || "") || "no-issue-id"}`].join("||");

        const existing = fallbackDedup.get(dedupKey);
        if (existing) {
            existing.count += 1;
            if (item.lineValue > 0) existing.lines.push(item.lineValue);
            return;
        }

        fallbackDedup.set(dedupKey, {
            count: 1,
            lines: item.lineValue > 0 ? [item.lineValue] : [],
            primaryLine: item.lineValue > 0 ? item.lineValue : 0,
            functionScopeName: item.fnScopeName,
            functionScopeStart: item.fnScopeStart,
            functionScopeEnd: item.fnScopeEnd,
            functionScopeResolved: item.fnScopeResolved,
            dedupMode,
            representativeViolation: item.violation,
            eventName: item.eventName,
            rowObject: item.rowObject,
            severity: item.severity,
            message: item.message,
            source: item.source,
        });
    });

    fallbackDedup.forEach((entry) => {
        const uniqueLines = Array.from(
            new Set((Array.isArray(entry.lines) ? entry.lines : []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0)),
        ).sort((a, b) => a - b);
        const primaryLine = positiveLineOrZero(entry.primaryLine) || uniqueLines[0] || 0;
        const violationWithCount = {
            ...entry.representativeViolation,
            _duplicate_count: entry.count,
            _duplicate_lines: uniqueLines,
            _primary_line: primaryLine,
            _function_scope_name: entry.functionScopeName || "Global",
            _function_scope_start: positiveLineOrZero(entry.functionScopeStart),
            _function_scope_end: positiveLineOrZero(entry.functionScopeEnd),
            _function_scope_resolved: !!entry.functionScopeResolved,
            _dedup_mode: String(entry.dedupMode || "none"),
            _grouping_mode: String(entry.dedupMode || "none"),
            _group_rule_ids: entry.representativeViolation && entry.representativeViolation.rule_id ? [String(entry.representativeViolation.rule_id)] : [],
            _group_messages: entry.representativeViolation && entry.representativeViolation.message ? [String(entry.representativeViolation.message)] : [],
            _group_issue_ids: entry.representativeViolation && entry.representativeViolation.issue_id ? [String(entry.representativeViolation.issue_id)] : [],
        };
        if (primaryLine > 0) {
            violationWithCount.line = primaryLine;
        }
        nextRows.push({
            source: entry.source || "P1",
            object: entry.rowObject || violationWithCount.object || "Global",
            severity: entry.severity,
            message: entry.message,
            onClick: async () => {
                showDetail(violationWithCount, entry.eventName);
                const jumpResult = await jumpCodeViewerToViolation(violationWithCount);
                showDetail(violationWithCount, entry.eventName, { jumpResult });
            },
        });
    });

    p2List.forEach((v) => {
        const objectName = String(v.object || "Global");
        const fileFromPayload = basenamePath(v.file || v.file_name || v.filename);
        const fileFromObject = /\.ctl$/i.test(objectName) ? basenamePath(objectName) : "";
        const fileHint = fileFromPayload || fileFromObject;
        const displayObject = fileHint || objectName || "Global";
        const p2Violation = {
            ...v,
            object: displayObject,
            file: fileHint || "",
            priority_origin: v.priority_origin || "P2",
        };
        const p2Localized = buildP2LocalizedMessage(p2Violation);
        nextRows.push({
            source: p2Violation.priority_origin || "P2",
            object: p2Violation.object || "Global",
            severity: p2Violation.severity || p2Violation.type || "Info",
            message: p2Localized.shortText,
            onClick: async () => {
                showDetail(p2Violation, "Global");
                const jumpResult = await jumpCodeViewerToViolation(p2Violation);
                showDetail(p2Violation, "Global", { jumpResult });
            },
        });
    });

    p3List.forEach((v) => {
        if (!v || typeof v !== "object") return;
        const reviewText = String(v.review || "");
        const rowMessage = buildAiReviewSummary(reviewText || String(v.message || ""));
        const p3Violation = {
            ...v,
            priority_origin: v.priority_origin || "P3",
            severity: v.severity || "Info",
            message: rowMessage,
            file: v.file || v.object || currentViewerFile,
        };
        nextRows.push({
            source: p3Violation.priority_origin,
            object: p3Violation.object || "Global",
            severity: p3Violation.severity || "Info",
            message: rowMessage,
            onClick: async () => {
                const event = String(p3Violation.event || "Global");
                showDetail(p3Violation, event);
                const jumpResult = await jumpCodeViewerToViolation(p3Violation);
                showDetail(p3Violation, event, { jumpResult });
            },
        });
    });

    workspaceRowIndex = nextRows;
}

function showDetail(violation, eventName, options = {}) {
    violationDetail.replaceChildren();
    const detailSourceKey = sourceFilterKey(violation.priority_origin || "P1");
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
    const duplicateCount = Math.max(1, Number.parseInt(violation._duplicate_count, 10) || 1);
      if (detailSourceKey === "p1" && duplicateCount > 1) {
          const duplicateLines = Array.from(
              new Set(
                  (Array.isArray(violation._duplicate_lines) ? violation._duplicate_lines : [])
                    .map((line) => positiveLineOrZero(line))
                    .filter((line) => line > 0),
            ),
        ).sort((a, b) => a - b);
        const primaryLine = positiveLineOrZero(violation._primary_line || violation.line);
        const dup = document.createElement("p");
        dup.style.marginTop = "4px";
        dup.style.fontSize = "12px";
        dup.style.color = "#666";
          dup.textContent = `중복 검출: ${duplicateCount}건`;
          violationDetail.appendChild(dup);

          const groupingMode = String(violation._grouping_mode || violation._dedup_mode || "none");
          if (groupingMode === "jump_target") {
              const target = document.createElement("p");
              target.style.marginTop = "2px";
              target.style.fontSize = "12px";
              target.style.color = "#666";
              const targetFile = basenamePath(violation.file || violation.object || "");
              target.textContent = `이동 타깃 기준 묶음: ${targetFile || "N/A"}:${primaryLine > 0 ? primaryLine : "N/A"}`;
              violationDetail.appendChild(target);

              const groupedRules = Array.from(
                  new Set(
                      (Array.isArray(violation._group_rule_ids) ? violation._group_rule_ids : [])
                          .map((value) => String(value || "").trim())
                          .filter(Boolean),
                  ),
              );
              if (groupedRules.length > 0) {
                  const ruleLimit = 8;
                  const rulePreview = groupedRules.slice(0, ruleLimit);
                  const ruleSuffix = groupedRules.length > ruleLimit
                      ? ` ... (+${groupedRules.length - ruleLimit}개)`
                      : "";
                  const ruleInfo = document.createElement("p");
                  ruleInfo.style.marginTop = "2px";
                  ruleInfo.style.fontSize = "12px";
                  ruleInfo.style.color = "#666";
                  ruleInfo.textContent = `포함 규칙: ${rulePreview.join(", ")}${ruleSuffix}`;
                  violationDetail.appendChild(ruleInfo);
              }

              const groupedMessages = Array.from(
                  new Set(
                      (Array.isArray(violation._group_messages) ? violation._group_messages : [])
                          .map((value) => String(value || "").trim())
                          .filter(Boolean),
                  ),
              );
              if (groupedMessages.length > 1) {
                  const msgInfo = document.createElement("p");
                  msgInfo.style.marginTop = "2px";
                  msgInfo.style.fontSize = "12px";
                  msgInfo.style.color = "#666";
                  msgInfo.textContent = `추가 메시지: ${groupedMessages.length - 1}건`;
                  violationDetail.appendChild(msgInfo);
              }
          }

          const functionScopeName = String(violation._function_scope_name || "Global");
          const functionScopeStart = positiveLineOrZero(violation._function_scope_start);
          const functionScopeEnd = positiveLineOrZero(violation._function_scope_end);
        const fn = document.createElement("p");
        fn.style.marginTop = "2px";
        fn.style.fontSize = "12px";
        fn.style.color = "#666";
        if (functionScopeStart > 0 && functionScopeEnd > 0) {
            fn.textContent = `함수: ${functionScopeName} (line ${functionScopeStart}~${functionScopeEnd})`;
        } else {
            fn.textContent = `함수: ${functionScopeName}`;
        }
        violationDetail.appendChild(fn);

          const primary = document.createElement("p");
        primary.style.marginTop = "2px";
        primary.style.fontSize = "12px";
        primary.style.color = "#666";
        primary.textContent = `대표 라인: ${primaryLine > 0 ? primaryLine : "N/A"}`;
        violationDetail.appendChild(primary);

        if (duplicateLines.length > 0) {
            const previewLimit = 12;
            const previewLines = duplicateLines.slice(0, previewLimit);
            const suffix = duplicateLines.length > previewLimit
                ? ` ... (+${duplicateLines.length - previewLimit}건)`
                : "";
            const lines = document.createElement("p");
            lines.style.marginTop = "2px";
            lines.style.fontSize = "12px";
            lines.style.color = "#666";
            lines.textContent = `검출 라인: ${previewLines.join(", ")}${suffix}`;
            violationDetail.appendChild(lines);
        }
    }
    const isP2 = detailSourceKey === "p2";
    if (isP2) {
        const title = document.createElement("p");
        const titleStrong = document.createElement("strong");
        titleStrong.textContent = "설명:";
        title.appendChild(titleStrong);
        violationDetail.appendChild(title);

        const blocks = buildP2DetailBlocks(violation);
        [blocks.cause, blocks.impact, blocks.action].forEach((line) => {
            const p = document.createElement("p");
            p.style.marginTop = "4px";
            p.textContent = line;
            violationDetail.appendChild(p);
        });
        if (blocks.raw) {
            const raw = document.createElement("p");
            raw.style.marginTop = "6px";
            raw.style.fontSize = "12px";
            raw.style.color = "#666";
            raw.textContent = blocks.raw;
            violationDetail.appendChild(raw);
        }
    } else {
        const desc = document.createElement("p");
        const descLabel = document.createElement("strong");
        descLabel.textContent = "설명:";
        desc.appendChild(descLabel);
        desc.append(` ${violation.message || ""}`);
        violationDetail.appendChild(desc);
    }

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
    const hasAiSuggestion = !!(aiMatch && aiStatus !== "Ignored");
    const sourceKey = sourceFilterKey(violation.priority_origin || "P1");
    const preferAiTab = sourceKey === "p3";
    resetInspectorTabsForViolation({ hasAiSuggestion, preferAi: preferAiTab });

    if (hasAiSuggestion) {
        aiCard.style.display = "block";
        aiReviewExpanded = false;
        setAiReviewText(aiMatch.review);
        const btnAiAccept = document.getElementById("btn-ai-accept");
        const btnAiDiff = document.getElementById("btn-ai-diff");
        const btnAiSourceApply = document.getElementById("btn-ai-source-apply");
        const btnAiIgnore = document.getElementById("btn-ai-ignore");
        const btnAiMoreLocal = document.getElementById("btn-ai-more");
        const aiKey = makeAiCardKey(violation, eventName, aiMatch);
        const cachedAutofixBundle = autofixProposalCache.get(aiKey) || null;
        const cachedAutofixProposal = getActiveAutofixProposal(cachedAutofixBundle);
        const refreshComparePanel = (boundKey) => {
            const currentBundle = autofixProposalCache.get(boundKey) || null;
            renderAutofixComparePanel(currentBundle, (proposalId) => {
                const latestBundle = autofixProposalCache.get(boundKey);
                if (!latestBundle || !Array.isArray(latestBundle.proposals)) return;
                latestBundle.active_proposal_id = String(proposalId || "");
                autofixProposalCache.set(boundKey, latestBundle);
                const active = getActiveAutofixProposal(latestBundle);
                setAutofixDiffPanel(active ? active.unified_diff : "");
                refreshComparePanel(boundKey);
                if (active) {
                    const gen = String(active.generator_type || "unknown").toUpperCase();
                    setAiStatusInline(`Selected candidate: ${gen}`, "#1565c0");
                }
            });
        };
        aiCard.dataset.aiKey = aiKey;
        aiMoreMenuOpen = false;
        syncAiMoreMenuUi();
        setAiStatusInline("");
        setAutofixDiffPanel(cachedAutofixProposal ? cachedAutofixProposal.unified_diff : "");
        refreshComparePanel(aiKey);
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
        if (btnAiMoreLocal) {
            btnAiMoreLocal.onclick = () => {
                aiMoreMenuOpen = !aiMoreMenuOpen;
                syncAiMoreMenuUi();
            };
            btnAiMoreLocal.disabled = false;
            btnAiMoreLocal.style.opacity = "1";
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
            if (btnAiMoreLocal) {
                btnAiMoreLocal.disabled = true;
                btnAiMoreLocal.style.opacity = "0.8";
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
                    const bundle = await prepareAutofixProposal(violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    autofixProposalCache.set(boundKey, bundle);
                    const proposal = getActiveAutofixProposal(bundle);
                    setAutofixDiffPanel((proposal && proposal.unified_diff) || "");
                    refreshComparePanel(boundKey);
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
                let bundle = autofixProposalCache.get(boundKey) || null;
                let proposal = getActiveAutofixProposal(bundle);
                btnAiSourceApply.disabled = true;
                btnAiSourceApply.textContent = "Applying...";
                btnAiSourceApply.style.opacity = "0.8";
                if (btnAiDiff) btnAiDiff.disabled = true;
                if (btnAiIgnore) btnAiIgnore.disabled = true;
                setAiStatusInline("Applying source diff...", "#555");
                try {
                    if (!proposal) {
                        bundle = await prepareAutofixProposal(violation, eventName, aiMatch);
                        autofixProposalCache.set(boundKey, bundle);
                        proposal = getActiveAutofixProposal(bundle);
                        setAutofixDiffPanel((proposal && proposal.unified_diff) || "");
                        refreshComparePanel(boundKey);
                    }
                    if (!proposal) throw new Error("autofix proposal is missing");
                    const result = await applyAutofixProposal(proposal, violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    const mergedProposal = { ...(proposal || {}), ...(result || {}) };
                    if (bundle && Array.isArray(bundle.proposals)) {
                        bundle.proposals = bundle.proposals.map((item) =>
                            String(item.proposal_id) === String(mergedProposal.proposal_id) ? mergedProposal : item
                        );
                        autofixProposalCache.set(boundKey, bundle);
                    } else {
                        autofixProposalCache.set(boundKey, normalizeAutofixBundle(mergedProposal));
                    }
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
                    const validation = (result && result.validation) || {};
                    const observeMode = String(validation.benchmark_observe_mode || "strict_hash");
                    const bypassText = validation.hash_gate_bypassed ? "yes" : "no";
                    setAiStatusInline(`Source patch applied (${generatorType}). mode=${observeMode}, bypass=${bypassText}`, "#2e7d32");
                    setAutofixValidationPanel(formatAutofixValidationSummary(result), {
                        ok: !hasAutofixValidationErrors(result),
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
                    const observeMode = String(((payload && payload.validation && payload.validation.benchmark_observe_mode) || "strict_hash"));
                    setAiStatusInline(`Source apply failed: ${msg} (mode=${observeMode}${errorCode ? `, code=${errorCode}` : ""})`, "#c62828");
                    const validationSummary = formatAutofixValidationSummary(payload);
                    const panelMsg = [
                        errorCode ? `${msg}\nerror_code: ${errorCode}` : String(msg || ""),
                        validationSummary,
                    ].filter(Boolean).join("\n\n");
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
                aiMoreMenuOpen = false;
                syncAiMoreMenuUi();
                setInspectorTab("detail", false);
                setAiStatusInline("");
                setAutofixDiffPanel("");
                setAutofixValidationPanel("");
            };
        }
    } else {
        aiCard.style.display = "none";
        aiReviewExpanded = false;
        aiMoreMenuOpen = false;
        syncAiMoreMenuUi();
        setAiReviewText("");
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

function formatDurationMs(ms) {
    const safeMs = Math.max(0, Number(ms) || 0);
    const totalSec = Math.floor(safeMs / 1000);
    const minutes = Math.floor(totalSec / 60);
    const seconds = totalSec % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function setAnalyzeProgressVisible(visible) {
    if (!analyzeProgressPanel) return;
    analyzeProgressPanel.style.display = visible ? "block" : "none";
}

function updateAnalyzeProgressUi(statusPayload = {}) {
    const status = String(statusPayload.status || "queued");
    const progress = (statusPayload && statusPayload.progress) || {};
    const timing = (statusPayload && statusPayload.timing) || {};
    const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));
    const completed = Math.max(0, Number(progress.completed_files) || 0);
    const total = Math.max(0, Number(progress.total_files) || 0);
    const currentFile = String(progress.current_file || "");
    const etaMs = timing.eta_ms;
    const elapsedMs = timing.elapsed_ms;

    if (analyzeProgressStatus) {
        const head = status === "queued" ? "분석 대기 중..." : status === "running" ? "분석 중..." : status === "completed" ? "분석 완료" : "분석 실패";
        analyzeProgressStatus.textContent = currentFile ? `${head} (${currentFile})` : head;
    }
    if (analyzeProgressBar) {
        analyzeProgressBar.style.width = `${percent}%`;
    }
    if (analyzeProgressMeta) {
        const etaText = Number.isFinite(Number(etaMs)) && Number(etaMs) >= 0 ? formatDurationMs(Number(etaMs)) : "계산 중";
        const elapsedText = Number.isFinite(Number(elapsedMs)) && Number(elapsedMs) >= 0 ? formatDurationMs(Number(elapsedMs)) : "00:00";
        analyzeProgressMeta.textContent = `${percent}% | ${completed}/${total} 파일 | ETA ${etaText} | 경과 ${elapsedText}`;
    }
}

async function applyAnalyzePayload(payload) {
    analysisData = {
        summary: payload.summary || { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
        violations: payload.violations || { P1: [], P2: [], P3: [] },
        output_dir: payload.output_dir || "",
        metrics: payload.metrics || {},
        report_jobs: payload.report_jobs || {},
    };
    workspaceRowIndex = [];
    functionScopeCacheByFile.clear();
    autofixProposalCache.clear();
    setAutofixDiffPanel("");
    setAutofixValidationPanel("");
    const selected = getSelectedFiles();
    await prepareFunctionScopeCacheForSelectedFiles(selected);
    buildWorkspaceRowIndex();

    updateDashboard();
    renderWorkspace();
    updateExcelJobUiFromAnalysis();
    updateAiContextHelpText();
    navWorkspace.onclick();

    if (selected.length > 0) {
        void loadCodeViewer(selected[0]).catch(() => { });
    }
}

async function sleepMs(ms) {
    await new Promise((resolve) => setTimeout(resolve, ms));
}

btnAnalyze.onclick = async () => {
    const originalText = btnAnalyze ? btnAnalyze.textContent : "";
    try {
        const allowRawTxt = false;
        const enableCtrlppcheck = !!(ctrlppToggle && ctrlppToggle.checked);
        const enableLiveAi = !!(liveAiToggle && liveAiToggle.checked);
        const aiWithContext = enableLiveAi && !!(aiContextToggle && aiContextToggle.checked);
        const selected_files = getSelectedFiles();

        if (btnAnalyze) {
            btnAnalyze.disabled = true;
            btnAnalyze.textContent = "분석 중...";
        }
        setAnalyzeProgressVisible(true);
        updateAnalyzeProgressUi({
            status: "queued",
            progress: {
                total_files: selected_files.length,
                completed_files: 0,
                failed_files: 0,
                percent: 0,
                current_file: "",
            },
            timing: { elapsed_ms: 0, eta_ms: null },
        });

        const response = await fetch("/api/analyze/start", {
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

        const jobId = String(payload.job_id || "");
        if (!jobId) {
            throw new Error("분석 작업 ID를 받지 못했습니다.");
        }
        const pollIntervalMs = Math.max(200, Number(payload.poll_interval_ms) || 500);

        for (;;) {
            const statusResp = await fetch(`/api/analyze/status?job_id=${encodeURIComponent(jobId)}`);
            const statusPayload = await statusResp.json();
            if (!statusResp.ok) {
                throw new Error(statusPayload.error || `분석 상태 조회 실패 (${statusResp.status})`);
            }
            updateAnalyzeProgressUi(statusPayload);
            const status = String(statusPayload.status || "");
            if (status === "completed") {
                await applyAnalyzePayload(statusPayload.result || {});
                break;
            }
            if (status === "failed") {
                throw new Error(String(statusPayload.error || "분석 실패"));
            }
            await sleepMs(pollIntervalMs);
        }
    } catch (err) {
        alert(`분석 실패: ${(err && err.message) || String(err)}`);
    } finally {
        setAnalyzeProgressVisible(false);
        if (btnAnalyze) {
            btnAnalyze.disabled = false;
            btnAnalyze.textContent = originalText || "선택 항목 분석";
        }
    }
};

window.addEventListener("DOMContentLoaded", async () => {
    initFilterControls();
    attachResultTableVirtualScrollHandler();
    setInspectorTab("detail", false);
    if (inspectorTabDetail) {
        inspectorTabDetail.addEventListener("click", () => setInspectorTab("detail", !!(aiCard && aiCard.style.display !== "none")));
    }
    if (inspectorTabAi) {
        inspectorTabAi.addEventListener("click", () => {
            if (inspectorTabAi.disabled) return;
            setInspectorTab("ai", true);
        });
    }
    syncAiMoreMenuUi();
    if (aiReviewToggleBtn) {
        aiReviewToggleBtn.addEventListener("click", () => {
            aiReviewExpanded = !aiReviewExpanded;
            const currentFull = (aiTextFull && aiTextFull.textContent) ? aiTextFull.textContent : "";
            setAiReviewText(currentFull);
        });
    }
    if (liveAiToggle) {
        liveAiToggle.addEventListener("change", syncAiContextToggle);
    }
    if (aiContextToggle) {
        aiContextToggle.addEventListener("change", updateAiContextHelpText);
    }
    syncAiContextToggle();
    updateExcelJobUiFromAnalysis();
    updateDashboard();
    setCodeViewerText("// 파일을 선택하면 원본 코드와 위반 항목을 확인할 수 있습니다.");
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
