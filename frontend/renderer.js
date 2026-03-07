let analysisData = {
    summary: { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
    violations: { P1: [], P2: [], P3: [] },
    ai_review_statuses: [],
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
const verificationBadge = document.getElementById("verification-badge");
const verificationProfileCard = document.getElementById("verification-profile-card");
const dedupeSummary = document.getElementById("dedupe-summary");
const priorityRecommendations = document.getElementById("priority-recommendations");
const codeViewer = document.getElementById("code-viewer");
const workspaceQuickFilter = document.getElementById("workspace-quick-filter");
const workspaceQuickFilterText = document.getElementById("workspace-quick-filter-text");
const workspaceQuickFilterClear = document.getElementById("workspace-quick-filter-clear");
const workspaceFilterSummaryText = document.getElementById("workspace-filter-summary-text");

const resultTableWrap = document.querySelector(".result-table");
const resultBody = document.getElementById("result-body");
const inspectorTabDetail = document.getElementById("inspector-tab-detail");
const inspectorTabAi = document.getElementById("inspector-tab-ai");
const violationDetailPanel = document.getElementById("violation-detail-panel");
const aiPanelWrap = document.getElementById("ai-panel-wrap");
const violationDetail = document.getElementById("violation-detail");
const inspectorSelectionMeta = document.getElementById("inspector-selection-meta");
const aiCard = document.getElementById("ai-suggestion-card");
const aiText = document.getElementById("ai-text");
const aiSummaryList = document.getElementById("ai-summary-list");
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
const diffModal = document.getElementById("autofix-diff-modal");
const diffModalBackdrop = document.getElementById("autofix-diff-modal-backdrop");
const diffModalClose = document.getElementById("autofix-diff-modal-close");
const diffModalTitle = document.getElementById("autofix-diff-modal-title");
const diffModalMeta = document.getElementById("autofix-diff-modal-meta");
const diffModalSummary = document.getElementById("autofix-diff-modal-summary");
const diffModalCandidates = document.getElementById("autofix-diff-modal-candidates");
const diffModalViewSplit = document.getElementById("autofix-diff-view-split");
const diffModalViewUnified = document.getElementById("autofix-diff-view-unified");
const diffModalSplit = document.getElementById("autofix-diff-modal-split");
const diffModalBefore = document.getElementById("autofix-diff-modal-before");
const diffModalAfter = document.getElementById("autofix-diff-modal-after");
const diffModalText = document.getElementById("autofix-diff-modal-text");
const fileList = document.getElementById("file-list");
const btnAddExternalFiles = document.getElementById("btn-add-external-files");
const btnAddExternalFolder = document.getElementById("btn-add-external-folder");
const externalFileInput = document.getElementById("external-file-input");
const externalFolderInput = document.getElementById("external-folder-input");
const externalInputSummary = document.getElementById("external-input-summary");
const externalInputList = document.getElementById("external-input-list");
const filterMatrix = document.querySelector(".filter-matrix");
const ctrlppToggle = document.getElementById("toggle-ctrlppcheck");
const flushExcelBtn = document.getElementById("btn-flush-excel");
const excelJobStatusText = document.getElementById("excel-job-status");
const analyzeProgressPanel = document.getElementById("analyze-progress-panel");
const analyzeProgressStatus = document.getElementById("analyze-progress-status");
const analyzeProgressBar = document.getElementById("analyze-progress-bar");
const analyzeProgressMeta = document.getElementById("analyze-progress-meta");
const liveAiToggle = document.getElementById("toggle-live-ai");
const aiModelSelect = document.getElementById("select-ai-model");
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
let activeJumpRequestState = { status: "idle", line: 0 };
const functionScopeCacheByFile = new Map();
const reviewedTodoCacheByFile = new Map();
const viewerContentCache = new Map();
let workspaceRowIndex = [];
let workspaceRenderToken = 0;
let workspaceFilteredRows = [];
let activeWorkspaceRowId = "";
let flashedWorkspaceRowId = "";
let activeWorkspaceFlashTimer = 0;
let codeViewerFocusTimer = 0;
let workspaceSelectionToken = 0;
let activeRecommendationRowId = "";
let recommendationInsightByRowId = new Map();
let workspaceRecommendationInsightByRowId = new Map();
let recommendationWorkspaceFilter = { mode: "", label: "", value: "", source: "" };
let activeDiffModalKey = "";
let activeDiffModalBundle = null;
let activeDiffModalViolation = null;
let activeDiffModalSelectHandler = null;
let activeDiffModalView = "split";
let analysisInsights = {
    dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
    recommendations: [],
};
let workspaceAnalysisInsights = {
    dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
    recommendations: [],
};
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
let sessionInputSources = [];
let selectedAiModel = "";
let aiModelCatalogLoaded = false;
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
    if (aiModelSelect) {
        if (!liveEnabled) {
            aiModelSelect.disabled = true;
        } else if (!aiModelCatalogLoaded) {
            void loadAiModels();
        } else {
            aiModelSelect.disabled = !aiModelSelect.options.length;
        }
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

function renderExternalInputSources() {
    if (externalInputSummary) {
        externalInputSummary.textContent = sessionInputSources.length
            ? `세션 입력 ${sessionInputSources.length}건`
            : "세션 입력 없음";
    }
    if (!externalInputList) return;
    externalInputList.replaceChildren();
    sessionInputSources.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = "external-input-chip";
        const label = document.createElement("span");
        label.textContent = `${item.type === "folder_path" ? "폴더" : "파일"} · ${item.label || basenamePath(item.value)}`;
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.textContent = "×";
        removeBtn.addEventListener("click", () => {
            sessionInputSources.splice(index, 1);
            renderExternalInputSources();
        });
        row.append(label, removeBtn);
        externalInputList.appendChild(row);
    });
}

async function loadAiModels() {
    if (!aiModelSelect) return;
    aiModelSelect.disabled = true;
    aiModelSelect.innerHTML = '<option value="">기본 모델</option>';
    try {
        const response = await fetch("/api/ai/models");
        const payload = await response.json().catch(() => ({}));
        const models = Array.isArray(payload.models) ? payload.models : [];
        const defaultModel = String(payload.default_model || "");
        models.forEach((modelName) => {
            const opt = document.createElement("option");
            opt.value = String(modelName);
            opt.textContent = String(modelName);
            aiModelSelect.appendChild(opt);
        });
        aiModelSelect.value = selectedAiModel || defaultModel || "";
        if (!aiModelSelect.value && models.length === 1) {
            aiModelSelect.value = String(models[0]);
        }
        selectedAiModel = aiModelSelect.value || "";
        aiModelCatalogLoaded = true;
        aiModelSelect.disabled = !models.length;
        if (aiContextHelp && liveAiToggle && liveAiToggle.checked && !models.length) {
            const errorText = String(payload.error || "설치된 Ollama 모델을 찾지 못했습니다.");
            aiContextHelp.textContent = `${errorText} 기본 모델 fallback을 사용합니다.`;
        }
    } catch (err) {
        aiModelCatalogLoaded = false;
        aiModelSelect.disabled = true;
        if (aiContextHelp && liveAiToggle && liveAiToggle.checked) {
            aiContextHelp.textContent = `모델 목록 조회 실패: ${String((err && err.message) || err || "")}`;
        }
    }
}

async function stageExternalInputs(files, mode) {
    if (!files || !files.length) return;
    const formData = new FormData();
    formData.append("mode", mode);
    Array.from(files).forEach((file) => {
        const stagedName = mode === "folder" && file.webkitRelativePath ? file.webkitRelativePath : file.name;
        formData.append("files", file, stagedName);
    });
    const response = await fetch("/api/input-sources/stage", {
        method: "POST",
        body: formData,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || `입력 staging 실패 (${response.status})`);
    }
    const staged = Array.isArray(payload.input_sources) ? payload.input_sources : [];
    const seen = new Set(sessionInputSources.map((item) => `${item.type}::${item.value}`));
    staged.forEach((item) => {
        const key = `${item.type}::${item.value}`;
        if (seen.has(key)) return;
        sessionInputSources.push({
            type: String(item.type || ""),
            value: String(item.value || ""),
            label: String(item.label || basenamePath(item.value || "")),
        });
        seen.add(key);
    });
    renderExternalInputSources();
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

function ensureAiEmptyStateNode() {
    let node = document.getElementById("ai-empty-state");
    if (!node && aiPanelWrap) {
        node = document.createElement("div");
        node.id = "ai-empty-state";
        node.className = "inspector-empty-state";
        aiPanelWrap.appendChild(node);
    }
    return node;
}

function renderAiEmptyState(title, detail) {
    const node = ensureAiEmptyStateNode();
    if (!node) return;
    node.replaceChildren();
    const strong = document.createElement("strong");
    strong.textContent = title || "AI 개선안이 없습니다.";
    const paragraph = document.createElement("p");
    paragraph.textContent = detail || "";
    node.append(strong, paragraph);
    node.style.display = "block";
    if (aiCard) {
        aiCard.style.display = "none";
        aiCard.dataset.aiKey = "";
    }
}

function hideAiEmptyState() {
    const node = document.getElementById("ai-empty-state");
    if (node) {
        node.style.display = "none";
        node.replaceChildren();
    }
}

function syncAiMoreMenuUi() {
    if (!aiMoreActions) return;
    const show = !!aiMoreMenuOpen;
    aiMoreActions.style.display = show ? "grid" : "none";
    if (btnAiMore) {
        btnAiMore.textContent = show ? "고급 옵션 접기" : "고급 옵션";
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
        const eyebrowEl = document.createElement("div");
        eyebrowEl.className = "code-viewer-header-eyebrow";
        eyebrowEl.textContent = "Code Context";
        const titleEl = document.createElement("div");
        titleEl.className = "code-viewer-header-title";
        const subtitleEl = document.createElement("div");
        subtitleEl.className = "code-viewer-header-subtitle";
        const metaEl = document.createElement("div");
        metaEl.className = "code-viewer-header-meta";
        const legacyEl = document.createElement("div");
        legacyEl.className = "code-viewer-header-legacy";
        legacyEl.textContent = header;
        headerEl.append(eyebrowEl, titleEl, subtitleEl, metaEl, legacyEl);
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
    updateCodeViewerHeaderMeta();
    queueCodeViewerWindowRender(true);
}

function basenamePath(value) {
    const text = String(value || "");
    if (!text) return "";
    const parts = text.split(/[\\/]/);
    return parts[parts.length - 1] || text;
}

function fileIdentityKey(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.replace(/\\/g, "/").toLowerCase();
}

function violationResolvedFile(violation, fallback = "") {
    return String(
        (violation && (
            violation.file_path
            || violation.parent_file_path
            || violation.file
            || violation.file_name
            || violation.filename
            || violation.object
        )) || fallback || "",
    );
}

function violationDisplayFile(violation, fallback = "") {
    return basenamePath(violationResolvedFile(violation, fallback)) || String((violation && violation.object) || fallback || "");
}

function sameFileIdentity(left, right) {
    const leftKey = fileIdentityKey(left);
    const rightKey = fileIdentityKey(right);
    if (!leftKey || !rightKey) return false;
    if (leftKey === rightKey) return true;
    return basenamePath(leftKey) === basenamePath(rightKey);
}

function positiveLineOrZero(value) {
    const line = Number.parseInt(value, 10);
    return Number.isFinite(line) && line > 0 ? line : 0;
}

const P1_RULE_ALIAS_MAP = {
    "cfg-perf-01": "PERF-01",
    "cfg-perf-02": "PERF-02",
    "cfg-perf-02-dpt-in-01": "PERF-02-WHERE-DPT-IN-01",
    "cfg-perf-03-active-delay-01": "PERF-03-ACTIVE-DELAY-01",
    "cfg-hard-01": "HARD-01",
    "cfg-clean-dup-01": "CLEAN-DUP-01",
    "cfg-log-dbg-01": "LOG-DBG-01",
    "cfg-log-level-01": "LOG-LEVEL-01",
    "cfg-db-01": "DB-01",
    "cfg-db-02": "DB-02",
    "cfg-active-01": "ACTIVE-01",
    "cfg-dup-act-01": "DUP-ACT-01",
    "cfg-getmultivalue-adopt-01": "PERF-GETMULTIVALUE-ADOPT-01",
};

function normalizeP1RuleId(ruleId) {
    const raw = String(ruleId || "").trim();
    if (!raw) return "UNKNOWN";
    const lowered = raw.toLowerCase();
    if (P1_RULE_ALIAS_MAP[lowered]) {
        return String(P1_RULE_ALIAS_MAP[lowered]);
    }
    return raw.toUpperCase();
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

function parseReviewedMetaLine(lineText) {
    const text = String(lineText || "");
    const m = text.match(/^\/\/\s*\[META\]\s*(.+)$/i);
    if (!m || !m[1]) return null;
    const meta = {};
    String(m[1]).split(";").forEach((entry) => {
        const token = String(entry || "").trim();
        if (!token) return;
        const sep = token.indexOf("=");
        if (sep <= 0) return;
        const key = token.slice(0, sep).trim().toLowerCase();
        const value = token.slice(sep + 1).trim();
        meta[key] = value;
    });
    return meta;
}

function parseReviewedSeverity(reviewLine) {
    const text = String(reviewLine || "");
    const m = text.match(/^\/\/\s*\[REVIEW\]\s*([A-Za-z]+)/i);
    return m && m[1] ? m[1] : "Info";
}

function parseReviewedTodoBlocks(content, fileName = "") {
    const lines = String(content || "").split("\n");
    const blocks = [];
    for (let i = 0; i < lines.length; i += 1) {
        const raw = String(lines[i] || "");
        if (!/^\/\/\s*>>TODO/i.test(raw.trim())) continue;

        const block = {
            file: basenamePath(fileName),
            todo_line: i + 1,
            message: "",
            review_line: "",
            severity: "Info",
            meta: {},
        };

        let j = i + 1;
        while (j < lines.length) {
            const lraw = String(lines[j] || "");
            const ltrim = lraw.trim();
            if (!ltrim.startsWith("//")) break;

            if (/^\/\/\s*\[REVIEW\]/i.test(ltrim)) {
                block.review_line = ltrim;
                block.severity = parseReviewedSeverity(ltrim);
            } else if (/^\/\/\s*\[META\]/i.test(ltrim)) {
                const meta = parseReviewedMetaLine(ltrim);
                if (meta && typeof meta === "object") {
                    block.meta = meta;
                }
            } else if (!/^\/\/\s*>>TODO/i.test(ltrim) && !block.message) {
                block.message = ltrim.replace(/^\/\/\s*/, "").trim();
            }
            j += 1;
        }
        blocks.push(block);
        i = Math.max(i, j - 1);
    }
    return blocks;
}

function normalizeReviewedMessageKey(message) {
    return String(message || "")
        .replace(/^\/\/\s*/g, "")
        .replace(/\[review\]\s*warning\s*-\s*/gi, "")
        .replace(/\[review\]\s*info\s*-\s*/gi, "")
        .replace(/[()[\]{}.,:;!?'"`]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
}

function p1RulePrefixGroup(ruleId) {
    const normalized = normalizeP1RuleId(ruleId);
    if (!normalized || normalized === "UNKNOWN") return "UNKNOWN";
    const idx = normalized.indexOf("-");
    return idx > 0 ? normalized.slice(0, idx) : normalized;
}

function inferRuleIdFromReviewedBlock(block) {
    const meta = (block && block.meta && typeof block.meta === "object") ? block.meta : {};
    const metaRule = normalizeP1RuleId(meta.rule_id);
    if (metaRule !== "UNKNOWN") {
        return { inferredRuleId: metaRule, confidence: 1.0, source: "meta" };
    }
    const reviewLine = String((block && block.review_line) || "").toLowerCase();
    const message = String((block && block.message) || "").toLowerCase();
    const text = `${reviewLine} ${message}`;

    const rules = [
        { pattern: /dpget|반복\s*구간\s*dpget|일괄\/캐시\s*처리\s*권장/, ruleId: "PERF-DPGET-BATCH-01", confidence: 0.9 },
        { pattern: /dpsetwait|dpsettimed/, ruleId: "PERF-05", confidence: 0.9 },
        { pattern: /연속\s*dpset|반복\s*구간\s*dpset|dpset.*일괄|dpset.*배치|배치\/동기\/조건부 업데이트/, ruleId: "PERF-DPSET-BATCH-01", confidence: 0.88 },
        { pattern: /active\/?enable|enable\/?active|active.*조건|enable.*조건/, ruleId: "ACTIVE-01", confidence: 0.88 },
        { pattern: /try\/catch|getlasterror|예외 처리/, ruleId: "EXC-TRY-01", confidence: 0.85 },
        { pattern: /setmultivalue|다중\s*set\s*업데이트/, ruleId: "PERF-SETMULTIVALUE-ADOPT-01", confidence: 0.86 },
        { pattern: /getmultivalue|다중\s*get\s*업데이트/, ruleId: "PERF-GETMULTIVALUE-ADOPT-01", confidence: 0.86 },
        { pattern: /dp query.*_dpt.*in/, ruleId: "PERF-02-WHERE-DPT-IN-01", confidence: 0.82 },
        { pattern: /dp query|전체 범위 조회/, ruleId: "PERF-02", confidence: 0.8 },
        { pattern: /divide by zero|0.*나눗셈|분모.*0/, ruleId: "SAFE-DIV-01", confidence: 0.82 },
        { pattern: /유효성|범위|형식.*검증/, ruleId: "VAL-01", confidence: 0.78 },
        { pattern: /디버그 로그|debug/, ruleId: "LOG-DBG-01", confidence: 0.78 },
        { pattern: /로그 레벨/, ruleId: "LOG-LEVEL-01", confidence: 0.78 },
        { pattern: /중복 동작|중복 처리/, ruleId: "DUP-ACT-01", confidence: 0.8 },
    ];
    for (const entry of rules) {
        if (entry.pattern.test(text)) {
            return { inferredRuleId: entry.ruleId, confidence: entry.confidence, source: "review_text" };
        }
    }
    return { inferredRuleId: "UNKNOWN", confidence: 0, source: "none" };
}

function resolveReviewedJumpLineFromCache(fileName, violation) {
    const reviewedFile = basenamePath(fileName || (violation && (violation.file || violation.object)) || "");
    if (!reviewedFile) return 0;
    const blocks = reviewedTodoCacheByFile.get(reviewedFile) || [];
    if (!Array.isArray(blocks) || !blocks.length) return 0;

    const explicitTodoLine = positiveLineOrZero(violation && (violation._reviewed_todo_line || violation.reviewed_todo_line));
    if (explicitTodoLine > 0) return explicitTodoLine;

    const blockIndexes = Array.isArray(violation && violation._reviewed_block_indexes)
        ? violation._reviewed_block_indexes
            .map((value) => Number.parseInt(value, 10))
            .filter((value) => Number.isFinite(value) && value > 0)
        : [];
    for (const blockIndex of blockIndexes) {
        const block = blocks[blockIndex - 1];
        const todoLine = positiveLineOrZero(block && block.todo_line);
        if (todoLine > 0) return todoLine;
    }

    const issueId = String((violation && violation.issue_id) || "").trim();
    if (issueId) {
        const byIssue = blocks.find((block) => String((((block || {}).meta || {}).issue_id) || "").trim() === issueId);
        const todoLine = positiveLineOrZero(byIssue && byIssue.todo_line);
        if (todoLine > 0) return todoLine;
    }

    const targetRuleId = normalizeP1RuleId((violation && violation.rule_id) || "");
    const targetMessage = normalizeReviewedMessageKey(
        String((violation && (violation._reviewed_original_message || violation.message)) || "").trim(),
    );
    if (targetRuleId !== "UNKNOWN" || targetMessage) {
        const matched = blocks.find((block) => {
            const inferredRuleId = normalizeP1RuleId(inferRuleIdFromReviewedBlock(block).inferredRuleId);
            const normalizedMessage = normalizeReviewedMessageKey((block && block.message) || "");
            const ruleMatch = targetRuleId !== "UNKNOWN" && inferredRuleId === targetRuleId;
            const messageMatch = targetMessage
                && normalizedMessage
                && (normalizedMessage.includes(targetMessage) || targetMessage.includes(normalizedMessage));
            return ruleMatch || messageMatch;
        });
        const todoLine = positiveLineOrZero(matched && matched.todo_line);
        if (todoLine > 0) return todoLine;
    }

    return 0;
}

function applyPrecomputedJumpTarget(violation, preferredSource = "") {
    const safe = (violation && typeof violation === "object") ? violation : {};
    const next = { ...safe };
    const source = String(preferredSource || next._jump_target_source || "").trim().toLowerCase();
    const explicitLine = positiveLineOrZero(next._jump_target_line || next.line);
    if (source === "reviewed" || (!source && String(next.priority_origin || "").toUpperCase() === "P1")) {
        const reviewedLine = resolveReviewedJumpLineFromCache(next.file || next.object, next);
        if (reviewedLine > 0) {
            next._jump_target_source = "reviewed";
            next._jump_target_line = reviewedLine;
            next._reviewed_todo_line = positiveLineOrZero(next._reviewed_todo_line || reviewedLine);
            return next;
        }
    }
    if (source === "source" || String(next.priority_origin || "").toUpperCase() === "P2") {
        if (explicitLine > 0) {
            next._jump_target_source = "source";
            next._jump_target_line = explicitLine;
        }
        return next;
    }
    if (explicitLine > 0) {
        next._jump_target_line = explicitLine;
    }
    return next;
}

async function fetchFileContentPayload(fileName, options = {}) {
    if (!fileName) throw new Error("file name is required");
    const preferSource = !!(options && options.preferSource);
    const qs = new URLSearchParams({ name: String(fileName) });
    const outputDir = String((options && options.outputDir) || (analysisData && analysisData.output_dir) || "").trim();
    const cacheKey = `${outputDir}::${String(fileName)}::${preferSource ? "source" : "viewer"}`;
    if (viewerContentCache.has(cacheKey)) {
        return { ...viewerContentCache.get(cacheKey) };
    }
    if (preferSource) {
        qs.set("prefer_source", "true");
    }
    if (outputDir) {
        qs.set("output_dir", outputDir);
    }
    const response = await fetch(`/api/file-content?${qs.toString()}`);
    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.error || "파일 내용을 불러오지 못했습니다.");
    }
    viewerContentCache.set(cacheKey, { ...payload });
    return payload;
}

async function prepareFunctionScopeCacheForSelectedFiles(selectedFiles) {
    functionScopeCacheByFile.clear();
    reviewedTodoCacheByFile.clear();
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
                const [sourcePayload, viewPayload] = await Promise.all([
                    fetchFileContentPayload(fileName, { preferSource: true }),
                    fetchFileContentPayload(fileName, { preferSource: false }),
                ]);
                cacheFunctionScopesForFile(fileName, String((sourcePayload && sourcePayload.content) || ""));
                if (viewPayload && String(viewPayload.source || "") === "reviewed") {
                    reviewedTodoCacheByFile.set(
                        basenamePath(fileName),
                        parseReviewedTodoBlocks(String(viewPayload.content || ""), fileName),
                    );
                }
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
        node.className = "ai-status-inline";
        aiCard.appendChild(node);
    }
    return node;
}

function setAiStatusInline(message, color = "") {
    const node = ensureAiStatusNode();
    if (!node) return;
    node.textContent = message || "";
    node.style.display = message ? "block" : "none";
    node.style.color = color || "";
}

function setActiveJumpRequestState(status = "idle", line = 0) {
    activeJumpRequestState = {
        status: String(status || "idle"),
        line: positiveLineOrZero(line),
    };
    updateCodeViewerHeaderMeta();
}

function setAutofixValidationPanel(text, { ok = true } = {}) {
    if (!aiValidationPanel || !aiValidationText) return;
    const msg = String(text || "");
    aiValidationText.textContent = msg;
    aiValidationPanel.style.display = msg ? "block" : "none";
    aiValidationText.classList.toggle("ai-validation-text-ok", !!ok);
    aiValidationText.classList.toggle("ai-validation-text-error", !ok);
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
    const instructionMode = String(readValue("instruction_mode", "off") || "off");
    const instructionOperation = String(readValue("instruction_operation", "") || "-");
    const instructionApplySuccess = !!readValue("instruction_apply_success", false);
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
        `instruction_mode: ${instructionMode}`,
        `instruction_operation: ${instructionOperation}`,
        `instruction_apply_success: ${boolText(instructionApplySuccess)}`,
    ];
    const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    const mergedErrorSet = new Set([...validationErrors, ...qualityErrors].map((item) => String(item || "").trim()).filter(Boolean));
    const errors = Array.from(mergedErrorSet);
    const instructionErrors = Array.isArray(readValue("instruction_validation_errors", []))
        ? readValue("instruction_validation_errors", []).filter(Boolean).map((item) => String(item))
        : [];
    if (instructionErrors.length) {
        lines.push(`instruction_validation_errors: ${instructionErrors.slice(0, 3).join(" | ")}`);
    }
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

function compactUiText(value, maxLength = 160) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength - 3)}...` : text;
}

function stripDetailEvidence(text) {
    return String(text || "").replace(/\s*\(근거:\s*.*\)\s*$/u, "").trim();
}

function qualityPreviewSummaryLines(preview) {
    const quality = (preview && typeof preview === "object") ? preview : {};
    const syntaxPassed = !!quality.syntax_check_passed;
    const heuristicCount = Number.parseInt(quality.heuristic_regression_count || 0, 10) || 0;
    const ctrlppCount = Number.parseInt(quality.ctrlpp_regression_count || 0, 10) || 0;
    const validationErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    const lines = [
        `검증 상태: syntax ${syntaxPassed ? "통과" : "확인 필요"}, heuristic ${heuristicCount}건, ctrlpp ${ctrlppCount}건`,
    ];
    if (validationErrors.length > 0) {
        lines.push(`주의 사항: ${compactUiText(validationErrors[0], 120)}`);
    }
    return lines;
}

function buildAiSummaryLines(violation, aiMatch, proposal) {
    const activeProposal = (proposal && typeof proposal === "object") ? proposal : null;
    const lines = [];
    const reviewSummary = buildAiReviewSummary((activeProposal && activeProposal.summary) || (aiMatch && aiMatch.review) || "");
    if (reviewSummary) {
        lines.push(`수정 요약: ${reviewSummary}`);
    }
    const generatorType = String((activeProposal && activeProposal.generator_type) || "").trim().toUpperCase();
    const generatorReason = compactUiText((activeProposal && activeProposal.generator_reason) || "", 130);
    if (generatorType || generatorReason) {
        const generatorText = [generatorType && `생성 방식: ${generatorType}`, generatorReason].filter(Boolean).join(" · ");
        if (generatorText) lines.push(generatorText);
    } else {
        const fileName = violationDisplayFile(violation);
        if (fileName) lines.push(`대상 파일: ${fileName}`);
        lines.push("준비 상태: 변경 내용 보기를 누르면 실제 수정안을 생성합니다.");
    }
    qualityPreviewSummaryLines(activeProposal && activeProposal.quality_preview).forEach((line) => {
        if (line) lines.push(line);
    });
    return lines.slice(0, 4);
}

function aiStatusMatchesViolation(statusItem, violation, eventName) {
    if (!statusItem || typeof statusItem !== "object") return false;
    const parentIssueId = String(statusItem.parent_issue_id || "").trim();
    const violationIssueId = String((violation && violation.issue_id) || "").trim();
    if (parentIssueId && violationIssueId && parentIssueId === violationIssueId) {
        return true;
    }
    const parentSource = String(statusItem.parent_source || "").trim().toUpperCase();
    const violationSource = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    if (parentSource && violationSource && parentSource !== violationSource) {
        return false;
    }
    const parentFile = violationResolvedFile(statusItem);
    const violationFile = violationResolvedFile(violation);
    if (parentFile && violationFile && !sameFileIdentity(parentFile, violationFile)) {
        return false;
    }
    const parentRule = String(statusItem.parent_rule_id || "").trim();
    const violationRule = String((violation && violation.rule_id) || "").trim();
    const parentLine = positiveLineOrZero(statusItem.parent_line || 0);
    const violationLine = positiveLineOrZero((violation && violation.line) || 0);
    if (parentRule && violationRule && parentRule === violationRule && parentLine > 0 && violationLine > 0) {
        return Math.abs(parentLine - violationLine) <= 25;
    }
    const parentMessage = messageSearchToken(statusItem.message || "");
    const violationMessage = messageSearchToken((violation && violation.message) || "");
    if (parentRule && violationRule && parentRule === violationRule && parentMessage && violationMessage) {
        return parentMessage === violationMessage;
    }
    if (parentMessage && violationMessage) {
        return parentMessage === violationMessage
            && String(statusItem.event || "Global") === String(eventName || "Global");
    }
    return false;
}

function findAiMatchForViolation(violation, eventName) {
    return (analysisData.violations.P3 || []).find((item) => aiStatusMatchesViolation(item, violation, eventName)) || null;
}

function findAiStatusForViolation(violation, eventName) {
    return (analysisData.ai_review_statuses || []).find((item) => aiStatusMatchesViolation(item, violation, eventName)) || null;
}


function upsertAiReview(reviewItem) {
    if (!reviewItem || typeof reviewItem !== "object") return null;
    const p3 = Array.isArray(analysisData.violations && analysisData.violations.P3) ? analysisData.violations.P3.slice() : [];
    const parentIssueId = String(reviewItem.parent_issue_id || "").trim();
    const next = p3.filter((item) => String((item && item.parent_issue_id) || "").trim() !== parentIssueId);
    next.push(reviewItem);
    analysisData.violations.P3 = next;
    analysisData.summary = analysisData.summary || {};
    analysisData.summary.p3_total = next.length;
    upsertAiReviewStatus({
        parent_source: reviewItem.parent_source || "P1",
        parent_issue_id: reviewItem.parent_issue_id || "",
        parent_rule_id: reviewItem.parent_rule_id || "",
        parent_file: reviewItem.parent_file || reviewItem.file || "",
        parent_file_path: reviewItem.parent_file_path || reviewItem.file_path || reviewItem.parent_file || reviewItem.file || "",
        parent_line: reviewItem.parent_line || 0,
        file: reviewItem.file || "",
        file_path: reviewItem.file_path || reviewItem.file || "",
        object: reviewItem.object || "",
        event: reviewItem.event || "Global",
        severity: reviewItem.severity || "",
        message: reviewItem.message || "",
        status: "generated",
        reason: "generated",
    });
    return reviewItem;
}

function upsertAiReviewStatus(statusItem) {
    if (!statusItem || typeof statusItem !== "object") return null;
    const statuses = Array.isArray(analysisData.ai_review_statuses) ? analysisData.ai_review_statuses.slice() : [];
    const parentIssueId = String(statusItem.parent_issue_id || "").trim();
    const parentSource = String(statusItem.parent_source || "").trim().toUpperCase();
    const parentRule = String(statusItem.parent_rule_id || "").trim();
    const parentLine = positiveLineOrZero(statusItem.parent_line || 0);
    const parentFile = violationResolvedFile(statusItem);
    const next = statuses.filter((item) => {
        if (!item || typeof item !== "object") return false;
        return !(
            String((item.parent_issue_id || "")).trim() === parentIssueId
            && String((item.parent_source || "")).trim().toUpperCase() === parentSource
            && String((item.parent_rule_id || "")).trim() === parentRule
            && positiveLineOrZero(item.parent_line || 0) === parentLine
            && sameFileIdentity(violationResolvedFile(item), parentFile)
        );
    });
    next.push(statusItem);
    analysisData.ai_review_statuses = next;
    return statusItem;
}


function describeAiUnavailable(violation, eventName) {
    if (!(liveAiToggle && liveAiToggle.checked)) {
        return {
            title: "AI 개선안이 비활성화되어 있습니다.",
            detail: "Live AI 사용 (P3)이 꺼져 있어 이 이슈에 대한 개선 적용안을 생성하지 않았습니다.",
        };
    }
    const aiStatus = findAiStatusForViolation(violation, eventName);
    const reason = String((aiStatus && aiStatus.reason) || "").trim();
    if (reason === "timeout") {
        return {
            title: "AI 개선안 생성이 시간 초과로 건너뛰어졌습니다.",
            detail: "Live AI timeout으로 이 이슈의 개선안 생성이 중단되었습니다. 더 빠른 모델로 바꾸거나 P3 범위를 줄여 다시 시도해 보세요.",
        };
    }
    if (reason === "response_parse_failed") {
        return {
            title: "AI 응답을 해석하지 못했습니다.",
            detail: "Live AI가 응답했지만 형식을 해석하지 못해 개선안을 저장하지 않았습니다.",
        };
    }
    if (reason === "fail_soft_skip" || reason === "empty_response") {
        return {
            title: "AI 개선안 생성이 실패했습니다.",
            detail: "Live AI 응답 실패로 fail-soft 처리되어 이 이슈의 개선안이 저장되지 않았습니다.",
        };
    }
    if (reason === "severity_filtered" || reason === "priority_limited") {
        return {
            title: "이 이슈는 현재 P3 대상에서 제외되었습니다.",
            detail: reason === "severity_filtered"
                ? "현재 P3 기준 심각도보다 낮아 개선안 생성을 건너뛰었습니다."
                : "같은 파일의 더 중요한 수정 포인트가 우선 선택되어 이번 P3 대상에서 제외되었습니다.",
        };
    }
    const sourceKey = sourceFilterKey(violation && violation.priority_origin);
    if (sourceKey === "p2") {
        return {
            title: "연결된 AI 개선안이 없습니다.",
            detail: "이 P2 이슈는 parent 매칭 조건을 만족하지 못했거나 연결된 개선안이 생성되지 않았습니다.",
        };
    }
    return {
        title: "이 이슈에 대한 AI 개선안이 아직 없습니다.",
        detail: "현재 P3 대상이 아니거나 parent 매칭 조건을 만족하지 않아 개선안을 만들지 않았습니다.",
    };
}

function renderAiSummaryList(lines) {
    if (!aiSummaryList) return;
    const safeLines = Array.isArray(lines) ? lines.map((line) => String(line || "").trim()).filter(Boolean) : [];
    aiSummaryList.replaceChildren(...safeLines.map((line) => {
        const item = document.createElement("li");
        item.textContent = line;
        return item;
    }));
}

function setDiffModalOpen(open) {
    if (!diffModal) return;
    diffModal.classList.toggle("hidden", !open);
    diffModal.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.classList.toggle("diff-modal-open", !!open);
}

function setDiffModalView(view) {
    const normalized = String(view || "split").trim().toLowerCase() === "unified" ? "unified" : "split";
    activeDiffModalView = normalized;
    if (diffModalViewSplit) {
        const active = normalized === "split";
        diffModalViewSplit.classList.toggle("active", active);
        diffModalViewSplit.setAttribute("aria-selected", active ? "true" : "false");
    }
    if (diffModalViewUnified) {
        const active = normalized === "unified";
        diffModalViewUnified.classList.toggle("active", active);
        diffModalViewUnified.setAttribute("aria-selected", active ? "true" : "false");
    }
    if (diffModalSplit) {
        diffModalSplit.classList.toggle("hidden", normalized !== "split");
    }
    if (diffModalText) {
        diffModalText.classList.toggle("hidden", normalized !== "unified");
    }
}

function closeDiffModal() {
    activeDiffModalKey = "";
    activeDiffModalBundle = null;
    activeDiffModalViolation = null;
    activeDiffModalSelectHandler = null;
    activeDiffModalView = "split";
    if (diffModalCandidates) diffModalCandidates.replaceChildren();
    if (diffModalSummary) diffModalSummary.replaceChildren();
    if (diffModalMeta) diffModalMeta.replaceChildren();
    if (diffModalBefore) diffModalBefore.replaceChildren();
    if (diffModalAfter) diffModalAfter.replaceChildren();
    if (diffModalText) diffModalText.textContent = "";
    setDiffModalView("split");
    setDiffModalOpen(false);
}

function createDiffPaneLine(lineNo, text, kind) {
    const row = document.createElement("div");
    row.className = `diff-pane-line diff-pane-line-${kind || "context"}`;
    const number = document.createElement("span");
    number.className = "diff-pane-line-number";
    number.textContent = lineNo > 0 ? String(lineNo) : "";
    const content = document.createElement("span");
    content.className = "diff-pane-line-text";
    content.textContent = String(text || "");
    row.appendChild(number);
    row.appendChild(content);
    return row;
}

function parseUnifiedDiffForSplit(diffText) {
    const lines = String(diffText || "").split(/\r?\n/);
    const beforeRows = [];
    const afterRows = [];
    let oldLine = 0;
    let newLine = 0;
    let pendingDeletes = [];
    let pendingAdds = [];

    const flushPending = () => {
        if (!pendingDeletes.length && !pendingAdds.length) return;
        const size = Math.max(pendingDeletes.length, pendingAdds.length);
        for (let idx = 0; idx < size; idx += 1) {
            const before = pendingDeletes[idx] || null;
            const after = pendingAdds[idx] || null;
            beforeRows.push({
                lineNo: before ? before.lineNo : 0,
                text: before ? before.text : "",
                kind: before && after ? "change-old" : before ? "remove" : "placeholder",
            });
            afterRows.push({
                lineNo: after ? after.lineNo : 0,
                text: after ? after.text : "",
                kind: before && after ? "change-new" : after ? "add" : "placeholder",
            });
        }
        pendingDeletes = [];
        pendingAdds = [];
    };

    for (const rawLine of lines) {
        if (/^---\s/.test(rawLine) || /^\+\+\+\s/.test(rawLine) || /^\\ No newline/.test(rawLine)) {
            continue;
        }
        const headerMatch = rawLine.match(/^@@\s+\-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
        if (headerMatch) {
            flushPending();
            oldLine = Number.parseInt(headerMatch[1], 10) || 0;
            newLine = Number.parseInt(headerMatch[2], 10) || 0;
            continue;
        }
        if (!rawLine) {
            flushPending();
            beforeRows.push({ lineNo: oldLine, text: "", kind: "context" });
            afterRows.push({ lineNo: newLine, text: "", kind: "context" });
            oldLine += 1;
            newLine += 1;
            continue;
        }
        const prefix = rawLine[0];
        const text = rawLine.slice(1);
        if (prefix === " ") {
            flushPending();
            beforeRows.push({ lineNo: oldLine, text, kind: "context" });
            afterRows.push({ lineNo: newLine, text, kind: "context" });
            oldLine += 1;
            newLine += 1;
        } else if (prefix === "-") {
            pendingDeletes.push({ lineNo: oldLine, text });
            oldLine += 1;
        } else if (prefix === "+") {
            pendingAdds.push({ lineNo: newLine, text });
            newLine += 1;
        }
    }
    flushPending();
    return { beforeRows, afterRows };
}

function renderDiffModalSplitView(proposal) {
    if (!diffModalBefore || !diffModalAfter) return;
    const parsed = parseUnifiedDiffForSplit(String((proposal && proposal.unified_diff) || ""));
    const beforeRows = parsed.beforeRows.length
        ? parsed.beforeRows
        : [{ lineNo: 0, text: "변경 전 비교 정보를 만들지 못했습니다.", kind: "placeholder" }];
    const afterRows = parsed.afterRows.length
        ? parsed.afterRows
        : [{ lineNo: 0, text: "변경 후 비교 정보를 만들지 못했습니다.", kind: "placeholder" }];
    diffModalBefore.replaceChildren(...beforeRows.map((item) => createDiffPaneLine(item.lineNo, item.text, item.kind)));
    diffModalAfter.replaceChildren(...afterRows.map((item) => createDiffPaneLine(item.lineNo, item.text, item.kind)));
}

function buildDiffModalMeta(proposal, violation) {
    const entries = [];
    const fileName = violationDisplayFile(proposal, violationDisplayFile(violation));
    const generatorType = String((proposal && proposal.generator_type) || "").trim().toUpperCase();
    const riskLevel = String((proposal && proposal.risk_level) || "").trim();
    if (fileName) entries.push(`파일 ${fileName}`);
    if (generatorType) entries.push(`생성 ${generatorType}`);
    if (riskLevel) entries.push(`위험 ${riskLevel}`);
    return entries;
}

function renderDiffModal(bundle, violation, onSelectProposal = null) {
    if (!diffModal || !diffModalText || !diffModalTitle || !diffModalMeta || !diffModalSummary || !diffModalCandidates) return;
    const active = getActiveAutofixProposal(bundle);
    const fileName = violationDisplayFile(active, violationDisplayFile(violation)) || "변경 내용";
    diffModalTitle.textContent = `${fileName} 변경 내용`;
    diffModalMeta.replaceChildren(...buildDiffModalMeta(active, violation).map((text) => {
        const chip = document.createElement("span");
        chip.className = "diff-modal-meta-chip";
        chip.textContent = text;
        return chip;
    }));
    const summaryLines = buildAiSummaryLines(violation, null, active);
    diffModalSummary.replaceChildren(...summaryLines.map((line) => {
        const item = document.createElement("p");
        item.textContent = line;
        return item;
    }));
    diffModalText.textContent = String((active && active.unified_diff) || "") || "// 변경 내용을 준비하지 못했습니다.";
    renderDiffModalSplitView(active);
    setDiffModalView(activeDiffModalView || "split");

    const proposals = (bundle && Array.isArray(bundle.proposals)) ? bundle.proposals : [];
    if (proposals.length > 1) {
        diffModalCandidates.classList.remove("hidden");
        diffModalCandidates.replaceChildren(...proposals.map((proposal) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "diff-modal-candidate";
            const generatorType = String((proposal && proposal.generator_type) || "unknown").toUpperCase();
            const score = Number.parseInt((proposal && proposal.compare_score && proposal.compare_score.total) || 0, 10) || 0;
            button.textContent = Number.isFinite(score) && score > 0 ? `${generatorType} (${score})` : generatorType;
            button.classList.toggle(
                "diff-modal-candidate-active",
                String((proposal && proposal.proposal_id) || "") === String((bundle && bundle.active_proposal_id) || (bundle && bundle.selected_proposal_id) || ""),
            );
            button.onclick = () => {
                if (!bundle) return;
                bundle.active_proposal_id = String((proposal && proposal.proposal_id) || "");
                if (typeof onSelectProposal === "function") {
                    onSelectProposal(bundle.active_proposal_id, bundle);
                    return;
                }
                renderDiffModal(bundle, violation, onSelectProposal);
            };
            return button;
        }));
    } else {
        diffModalCandidates.replaceChildren();
        diffModalCandidates.classList.add("hidden");
    }
}

function openDiffModal(bundle, violation, aiKey = "", onSelectProposal = null) {
    activeDiffModalKey = String(aiKey || "");
    activeDiffModalBundle = bundle || null;
    activeDiffModalViolation = violation || null;
    activeDiffModalSelectHandler = typeof onSelectProposal === "function" ? onSelectProposal : null;
    if (!activeDiffModalView) {
        activeDiffModalView = "split";
    }
    renderDiffModal(bundle, violation, onSelectProposal);
    setDiffModalOpen(true);
}

function setAiReviewText(reviewText) {
    const full = String(reviewText || "").trim();
    if (aiText) {
        aiText.textContent = buildAiReviewSummary(full);
    }
    renderAiSummaryList([]);
    if (aiTextFull) {
        aiTextFull.textContent = full;
        aiTextFull.style.display = aiReviewExpanded && full ? "block" : "none";
    }
    if (aiReviewToggleBtn) {
        aiReviewToggleBtn.style.display = full ? "inline-block" : "none";
        aiReviewToggleBtn.textContent = aiReviewExpanded ? "원문 접기" : "원문 보기";
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
    const fileName = violationResolvedFile(violation, currentViewerFile);
    const objectName = String((violation && violation.object) || (aiMatch && aiMatch.object) || "");
    const evt = String(eventName || (aiMatch && aiMatch.event) || "Global");
    const review = String((aiMatch && aiMatch.review) || "");
    return [fileName, objectName, evt, review].join("||");
}

function jumpFailureMessage(jumpResult) {
    if (!jumpResult || jumpResult.ok) return "";
    const reason = String(jumpResult.reason || "");
    if (reason === "reviewed-anchor-miss") {
        return "REVIEWED TODO 블록 앵커를 찾지 못해 해당 코멘트 위치로 이동하지 못했습니다.";
    }
    if (reason === "source-line-miss") {
        return "원본 source 기준 줄 번호를 찾지 못해 하이라이트 이동을 수행하지 못했습니다.";
    }
    if (reason === "file-load-miss") {
        return "대상 파일을 다시 불러오지 못해 코드뷰어 이동을 완료하지 못했습니다.";
    }
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

function buildCodeViewerStatusText() {
    const fileName = basenamePath(currentViewerResolvedName || currentViewerFile || "") || "선택된 파일 없음";
    const sourceMap = {
        reviewed: "REVIEWED.txt",
        normalized: "정규화 TXT",
        source: "원본 파일",
    };
    let lineText = "라인 선택 없음";
    if (activeJumpRequestState.status === "pending") {
        lineText = activeJumpRequestState.line > 0
            ? `라인 ${activeJumpRequestState.line} 이동 중`
            : "점프 이동 중";
    } else if (activeJumpRequestState.status === "failed") {
        lineText = activeJumpRequestState.line > 0
            ? `라인 ${activeJumpRequestState.line} 이동 실패`
            : "위치 이동 실패";
    } else if (currentHighlightedLine) {
        lineText = `라인 ${currentHighlightedLine}${currentHighlightedLineNear ? " 근접 이동" : " 직접 이동"}`;
    }
    return {
        fileName,
        sourceText: sourceMap[String(currentViewerSource || "").trim()] || "파일",
        lineText,
        filterText: buildRecommendationWorkspaceFilterText() || "필터 없음",
    };
}

function createHeaderChip(label, value, tone = "") {
    const chip = document.createElement("span");
    chip.className = `code-viewer-chip${tone ? ` ${tone}` : ""}`;
    const labelEl = document.createElement("strong");
    labelEl.textContent = `${label} `;
    chip.appendChild(labelEl);
    chip.append(value);
    return chip;
}

function updateCodeViewerHeaderMeta() {
    const headerEl = codeViewerVirtualState.headerEl;
    if (!headerEl) return;
    const status = buildCodeViewerStatusText();
    const titleEl = headerEl.querySelector(".code-viewer-header-title");
    const subtitleEl = headerEl.querySelector(".code-viewer-header-subtitle");
    const metaRow = headerEl.querySelector(".code-viewer-header-meta");
    if (titleEl) titleEl.textContent = status.fileName;
    if (subtitleEl) subtitleEl.textContent = "원본 코드와 분석 이동 상태를 한 화면에서 유지합니다.";
    if (metaRow) {
        metaRow.replaceChildren(
            createHeaderChip("소스", status.sourceText, "code-viewer-chip-muted"),
            createHeaderChip("점프", status.lineText, currentHighlightedLine ? "code-viewer-chip-accent" : "code-viewer-chip-muted"),
            createHeaderChip("필터", status.filterText, recommendationWorkspaceFilter.mode ? "code-viewer-chip-filter" : "code-viewer-chip-muted"),
        );
    }
}

async function applyAiSuggestion(violation, eventName, aiMatch) {
    const fileName = violationResolvedFile(violation, currentViewerFile);
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
    const text = String(diffText || "");
    if (aiDiffText) {
        aiDiffText.textContent = text;
    }
    if (aiDiffPanel) {
        aiDiffPanel.style.display = "none";
    }
    if (diffModalText) {
        diffModalText.textContent = text || "// 변경 내용을 준비하지 못했습니다.";
    }
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
        btn.className = "ai-compare-button";
        const preview = (proposal && typeof proposal.instruction_preview === "object") ? proposal.instruction_preview : {};
        const instructionValid = !!preview.valid;
        const compareScore = (proposal && typeof proposal.compare_score === "object") ? proposal.compare_score : {};
        const totalScore = Number.parseInt(compareScore.total, 10);
        const scoreText = Number.isFinite(totalScore) ? ` (${totalScore})` : "";
        btn.textContent = instructionValid ? `${gen} ✓${scoreText}` : `${gen} !${scoreText}`;
        btn.title = instructionValid
            ? "structured instruction: valid"
            : `structured instruction: invalid (${String((preview.errors || []).join(", ") || "unknown")})`;
        const active = pid === activeId;
        btn.classList.toggle("ai-compare-button-active", active);
        btn.onclick = () => onSelect(pid);
        aiCompareButtons.appendChild(btn);
    });
    const generatedCount = proposals.length;
    const compareMeta = (bundle && bundle.compare_meta && typeof bundle.compare_meta === "object") ? bundle.compare_meta : {};
    const selectionPolicy = String(compareMeta.selection_policy || "").trim();
    const active = proposals.find((item) => String((item && item.proposal_id) || "") === activeId) || proposals[0] || {};
    const activePreview = (active && typeof active.instruction_preview === "object") ? active.instruction_preview : {};
    const activeScore = (active && typeof active.compare_score === "object") ? active.compare_score : {};
    const generatorType = String((active && active.generator_type) || "unknown").toUpperCase();
    const validText = activePreview.valid ? "통과" : "확인 필요";
    const totalScore = Number.parseInt(activeScore.total || 0, 10) || 0;
    const selectedReason = compactUiText(active.selection_reason || compareMeta.selected_selection_reason || "", 84);
    const parts = [
        `후보 ${generatedCount}개`,
        `선택 ${generatorType}`,
        `검증 ${validText}`,
        `점수 ${totalScore}`,
    ];
    if (selectionPolicy) parts.push(`정책 ${selectionPolicy}`);
    if (selectedReason) parts.push(selectedReason);
    aiCompareMeta.textContent = parts.join(" · ");
    aiComparePanel.style.display = "block";
}

async function prepareAutofixProposal(violation, eventName, aiMatch) {
    const fileName = String((violation && (violation.file_path || violation.file || violation.file_name || violation.filename)) || currentViewerFile || "");
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
    const fileName = String((violation && (violation.file_path || violation.file || violation.file_name || violation.filename)) || currentViewerFile || "");
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
        const payload = await fetchFileContentPayload(fileName, {
            preferSource,
            outputDir: options && options.outputDir,
        });
        const header = buildCodeViewerHeader(payload);
        const content = String(payload.content || "");
        currentViewerFile = String(payload.resolved_path || payload.file || fileName || "");
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


function updateVerificationBadge() {
    if (!verificationBadge) return;
    const level = String((analysisData.summary && analysisData.summary.verification_level) || "").trim().toUpperCase();
    const optionalDeps = (analysisData.metrics && analysisData.metrics.optional_dependencies) || {};
    const openpyxlAvailable = !!(optionalDeps.openpyxl && optionalDeps.openpyxl.available);

    verificationBadge.classList.remove(
        "verification-badge--core-only",
        "verification-badge--core-report",
        "verification-badge--full",
        "verification-badge--unknown"
    );

    if (level === "CORE_ONLY") {
        verificationBadge.textContent = "검증 레벨: CORE_ONLY";
        verificationBadge.classList.add("verification-badge--core-only");
    } else if (level === "CORE+REPORT") {
        verificationBadge.textContent = "검증 레벨: CORE+REPORT";
        verificationBadge.classList.add("verification-badge--core-report");
    } else if (level === "FULL_WITH_OPTIONALS") {
        verificationBadge.textContent = "검증 레벨: FULL_WITH_OPTIONALS";
        verificationBadge.classList.add("verification-badge--full");
    } else {
        verificationBadge.textContent = "검증 레벨: UNKNOWN";
        verificationBadge.classList.add("verification-badge--unknown");
    }

    const openpyxlText = openpyxlAvailable ? "available" : "missing";
    verificationBadge.title = `verification_level=${level || "UNKNOWN"}, openpyxl=${openpyxlText}`;
}

function updateVerificationProfileCard(payload = null, errorMessage = "") {
    if (!verificationProfileCard) return;
    verificationProfileCard.classList.remove(
        "verification-profile-card--ok",
        "verification-profile-card--degraded",
        "verification-profile-card--failed",
        "verification-profile-card--unknown"
    );

    if (!payload || typeof payload !== "object") {
        verificationProfileCard.classList.add("verification-profile-card--unknown");
        verificationProfileCard.textContent = "검증 프로파일: 없음";
        verificationProfileCard.title = errorMessage || "검증 프로파일 결과 파일이 없습니다.";
        return;
    }

    const summary = payload.summary || {};
    const failed = Number(summary.failed || 0);
    const skipped = Number(summary.skipped_optional_missing || 0);
    const passed = Number(summary.passed || 0);
    if (failed > 0) {
        verificationProfileCard.classList.add("verification-profile-card--failed");
        verificationProfileCard.textContent = `검증 프로파일: 실패 ${failed}`;
    } else if (skipped > 0) {
        verificationProfileCard.classList.add("verification-profile-card--degraded");
        verificationProfileCard.textContent = `검증 프로파일: 통과 ${passed}, 스킵 ${skipped}`;
    } else {
        verificationProfileCard.classList.add("verification-profile-card--ok");
        verificationProfileCard.textContent = `검증 프로파일: 통과 ${passed}`;
    }

    const sourceFile = String(payload.source_file || "");
    verificationProfileCard.title = sourceFile ? `latest=${sourceFile}` : "최신 검증 프로파일";
}

async function loadLatestVerificationProfile() {
    try {
        const response = await fetch("/api/verification/latest");
        const payload = await response.json();
        if (!response.ok) {
            updateVerificationProfileCard(null, payload.error || `검증 프로파일 조회 실패 (${response.status})`);
            return;
        }
        updateVerificationProfileCard(payload, "");
    } catch (err) {
        updateVerificationProfileCard(null, (err && err.message) || String(err));
    }
}

function updateDashboard() {
    totalText.textContent = analysisData.summary.total || 0;
    criticalText.textContent = analysisData.summary.critical || 0;
    warningText.textContent = analysisData.summary.warning || 0;
    scoreBar.style.width = `${analysisData.summary.score || 0}%`;
    scoreText.textContent = `점수: ${analysisData.summary.score || 0}/100`;
    updateVerificationBadge();
    renderAnalysisInsights();
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function truncateUiText(value, maxLength = 96) {
    const text = String(value || "").trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, Math.max(0, maxLength - 1))}…`;
}

function scoreSeverityWeight(severity) {
    const key = severityFilterKey(severity);
    if (key === "critical") return 9;
    if (key === "warning") return 4;
    return 1;
}

function scoreSourceWeight(source) {
    const key = sourceFilterKey(source);
    if (key === "p1") return 4;
    if (key === "p2") return 3;
    if (key === "p3") return 2;
    return 1;
}

function normalizeInsightToken(value, fallback = "global") {
    const text = String(value || "").trim();
    return text ? text.toLowerCase() : fallback;
}

function summarizeRuleCluster(ruleIds) {
    const ids = Array.isArray(ruleIds) ? ruleIds : [];
    const normalized = ids
        .map((id) => String(id || "").trim())
        .filter(Boolean);
    if (!normalized.length) {
        return { label: "규칙 미상", familyCount: 0, dominantFamily: "unknown", dominantCount: 0, repeatedFamilyBonus: 0 };
    }
    const families = new Map();
    normalized.forEach((id) => {
        const family = normalizeInsightToken(id.split("-")[0] || id, "unknown");
        families.set(family, (families.get(family) || 0) + 1);
    });
    let dominantFamily = "unknown";
    let dominantCount = 0;
    families.forEach((count, family) => {
        if (count > dominantCount) {
            dominantFamily = family;
            dominantCount = count;
        }
    });
    return {
        label: dominantFamily.toUpperCase(),
        familyCount: families.size,
        dominantFamily,
        dominantCount,
        repeatedFamilyBonus: Math.min(5, Math.max(0, dominantCount - 1)),
    };
}

function buildRecommendationReason(item) {
    const reasons = [];
    const duplicateCount = Math.max(0, Number.parseInt(item && item.duplicateCount, 10) || 0);
    const hotspotIssueCount = Math.max(0, Number.parseInt(item && item.hotspotIssueCount, 10) || 0);
    const ruleBreadth = Math.max(0, Number.parseInt(item && item.ruleBreadth, 10) || 0);
    const dominantRuleCount = Math.max(0, Number.parseInt(item && item.dominantRuleCount, 10) || 0);
    const severityKey = severityFilterKey(item && item.severity);
    const sourceKey = sourceFilterKey(item && item.source);

    if (severityKey === "critical") {
        reasons.push("치명도 기준 최우선");
    } else if (severityKey === "warning") {
        reasons.push("경고급 이슈 밀집");
    }

    if (duplicateCount >= 4) {
        reasons.push(`중복 영향 ${duplicateCount}건`);
    }
    if (hotspotIssueCount >= 3) {
        reasons.push(`${String(item && item.hotspotObject || item && item.target || "대상")} 집중 ${hotspotIssueCount}건`);
    }
    if (dominantRuleCount >= 2) {
        reasons.push(`${String(item && item.dominantRuleFamily || "RULE")} 계열 반복 ${dominantRuleCount}건`);
    }
    if (ruleBreadth >= 3) {
        reasons.push(`다중 규칙 ${ruleBreadth}종 연관`);
    }
    if (sourceKey === "p1") {
        reasons.push("정적 규칙 기준 우선 검토");
    } else if (sourceKey === "p2") {
        reasons.push("Ctrlpp 정적 분석 우선 검토");
    } else if (sourceKey === "p3") {
        reasons.push("AI 리뷰 후속 확인 권장");
    }

    return reasons.slice(0, 3).join(" · ") || "심각도와 집중도를 기준으로 우선 추천";
}

function getRowHotspotKey(row) {
    const hotspot = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
    return normalizeInsightToken(hotspot, "global");
}

function getRowRuleFamilies(row) {
    const ruleIds = Array.isArray(row && row.ruleIds) ? row.ruleIds : [];
    return Array.from(new Set(
        ruleIds
            .map((ruleId) => normalizeInsightToken(String(ruleId || "").split("-")[0] || ruleId, "unknown"))
            .filter(Boolean),
    ));
}

function rowMatchesRecommendationFilter(row) {
    const mode = String(recommendationWorkspaceFilter.mode || "").trim();
    const value = String(recommendationWorkspaceFilter.value || "").trim();
    if (!mode || !value) return true;
    if (mode === "hotspot") {
        return getRowHotspotKey(row) === value;
    }
    if (mode === "rule_family") {
        return getRowRuleFamilies(row).includes(value);
    }
    return true;
}

function renderWorkspaceQuickFilter() {
    if (!workspaceQuickFilter || !workspaceQuickFilterText || !workspaceQuickFilterClear) return;
    const mode = String(recommendationWorkspaceFilter.mode || "").trim();
    const label = String(recommendationWorkspaceFilter.label || "").trim();
    const source = String(recommendationWorkspaceFilter.source || "").trim();
    if (!mode || !label) {
        workspaceQuickFilter.classList.add("hidden");
        workspaceQuickFilterText.textContent = "";
        updateCodeViewerHeaderMeta();
        return;
    }
    const prefix = mode === "rule_family" ? "추천 rule 보기" : "추천 hotspot 보기";
    const dedupe = (workspaceAnalysisInsights && workspaceAnalysisInsights.dedupe) || {};
    const topRecommendation = Array.isArray(workspaceAnalysisInsights && workspaceAnalysisInsights.recommendations)
        ? workspaceAnalysisInsights.recommendations[0]
        : null;
    const comparison = buildWorkspaceFilterComparisonSummary();
    workspaceQuickFilter.classList.remove("hidden");
    workspaceQuickFilterText.textContent = `${prefix}: ${label}${source ? ` · ${source.toUpperCase()}` : ""} · 행 ${dedupe.displayedRowCount || 0}개 · 이슈 ${dedupe.rawIssueCount || 0}개${topRecommendation ? ` · Top ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` · ${comparison.banner}` : ""}`;
    updateCodeViewerHeaderMeta();
}

function applyRecommendationWorkspaceFilter(mode, label, value, source = "") {
    recommendationWorkspaceFilter = {
        mode: String(mode || "").trim(),
        label: String(label || "").trim(),
        value: String(value || "").trim(),
        source: String(source || "").trim(),
    };
    renderWorkspace();
}

function clearRecommendationWorkspaceFilter() {
    recommendationWorkspaceFilter = { mode: "", label: "", value: "", source: "" };
    renderWorkspace();
}

function buildRecommendationWorkspaceFilterText() {
    const mode = String(recommendationWorkspaceFilter.mode || "").trim();
    const label = String(recommendationWorkspaceFilter.label || "").trim();
    const source = String(recommendationWorkspaceFilter.source || "").trim();
    if (!mode || !label) return "";
    const prefix = mode === "rule_family" ? "현재 추천 rule 필터" : "현재 추천 hotspot 필터";
    return `${prefix}: ${label}${source ? ` · ${source.toUpperCase()}` : ""}`;
}

function buildWorkspaceFilterComparisonSummary() {
    const activeMode = String(recommendationWorkspaceFilter.mode || "").trim();
    if (!activeMode) return { banner: "", detail: "" };
    const overall = (analysisInsights && analysisInsights.dedupe) || {};
    const current = (workspaceAnalysisInsights && workspaceAnalysisInsights.dedupe) || {};
    const overallIssues = Math.max(0, Number.parseInt(overall.rawIssueCount, 10) || 0);
    const currentIssues = Math.max(0, Number.parseInt(current.rawIssueCount, 10) || 0);
    const overallRows = Math.max(0, Number.parseInt(overall.displayedRowCount, 10) || 0);
    const currentRows = Math.max(0, Number.parseInt(current.displayedRowCount, 10) || 0);
    const issueDelta = Math.max(0, overallIssues - currentIssues);
    const rowDelta = Math.max(0, overallRows - currentRows);
    return {
        banner: `전체 대비 행 ${currentRows}/${overallRows} · 이슈 ${currentIssues}/${overallIssues} · ${rowDelta}행/${issueDelta}건 제외`,
        detail: `전체 결과 ${overallRows}행 ${overallIssues}건 중 현재 ${currentRows}행 ${currentIssues}건만 표시합니다. ${rowDelta}행/${issueDelta}건이 필터로 제외되었습니다.`,
    };
}

function appendDetailFact(container, label, value) {
    const row = document.createElement("div");
    row.className = "detail-fact-row";
    const labelEl = document.createElement("div");
    labelEl.className = "detail-fact-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("div");
    valueEl.className = "detail-fact-value";
    valueEl.textContent = value;
    row.append(labelEl, valueEl);
    container.appendChild(row);
}

function appendDetailNote(container, text, tone = "") {
    const note = document.createElement("p");
    note.className = `detail-note${tone ? ` ${tone}` : ""}`;
    note.textContent = text;
    container.appendChild(note);
}

function renderInspectorSelectionMeta(violation, options = {}) {
    if (!inspectorSelectionMeta) return;
    const chips = [];
    const objectName = basenamePath((violation && (violation.file || violation.object)) || "") || String((violation && violation.object) || "").trim();
    const source = String((violation && violation.priority_origin) || "").trim();
    const lineNo = positiveLineOrZero(
        (options && options.jumpResult && options.jumpResult.ok && currentHighlightedLine)
        || (options && options.jumpPendingLine)
        || (violation && (violation._jump_target_line || violation.line)),
    );
    const ruleId = String((violation && violation.rule_id) || "").trim();
    if (objectName) chips.push({ label: "객체", value: objectName });
    if (lineNo > 0) chips.push({ label: "라인", value: String(lineNo) });
    if (ruleId) chips.push({ label: "Rule", value: ruleId });
    if (source) chips.push({ label: "출처", value: source });
    if (!chips.length) {
        inspectorSelectionMeta.replaceChildren();
        inspectorSelectionMeta.classList.add("hidden");
        return;
    }
    inspectorSelectionMeta.replaceChildren(...chips.map((chip) => {
        const node = document.createElement("span");
        node.className = "inspector-selection-chip";
        node.textContent = `${chip.label} ${chip.value}`;
        return node;
    }));
    inspectorSelectionMeta.classList.remove("hidden");
}

function deriveAnalysisInsights(rows) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const dedupe = {
        rawIssueCount: 0,
        displayedRowCount: safeRows.length,
        collapsedDuplicateCount: 0,
    };
    const grouped = new Map();

    safeRows.forEach((row, index) => {
        const duplicateCount = Math.max(1, Number.parseInt(row && row.duplicateCount, 10) || 1);
        dedupe.rawIssueCount += duplicateCount;
        dedupe.collapsedDuplicateCount += Math.max(0, duplicateCount - 1);

        const source = String((row && row.source) || "P1");
        const target = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
        const key = `${source}||${target}`;
        if (!grouped.has(key)) {
            grouped.set(key, {
                source,
                target,
                severity: row && row.severity || "Info",
                rowCount: 0,
                duplicateCount: 0,
                messages: [],
                firstIndex: index,
                representativeRow: row || null,
                objectCounts: new Map(),
                objectLabels: new Map(),
                ruleFamilyCounts: new Map(),
                uniqueRuleIds: new Set(),
                severityTotal: 0,
                sourceTotal: 0,
                duplicateBonusTotal: 0,
            });
        }
        const current = grouped.get(key);
        current.rowCount += 1;
        current.duplicateCount += duplicateCount;
        current.severity = pickHigherSeverity(current.severity, row && row.severity || "Info");
        current.severityTotal += scoreSeverityWeight(row && row.severity);
        current.sourceTotal += scoreSourceWeight(source);
        current.duplicateBonusTotal += Math.min(6, duplicateCount - 1);
        if (!current.representativeRow || scoreSeverityWeight(row && row.severity) >= scoreSeverityWeight(current.representativeRow && current.representativeRow.severity)) {
            current.representativeRow = row || current.representativeRow;
        }
        const message = String((row && row.message) || "").trim();
        if (message && current.messages.length < 3) {
            current.messages.push(message);
        }
        const hotspotObject = basenamePath((row && row.object) || "") || String((row && row.object) || target || "Global");
        const objectKey = normalizeInsightToken(hotspotObject);
        current.objectCounts.set(objectKey, (current.objectCounts.get(objectKey) || 0) + duplicateCount);
        if (!current.objectLabels.has(objectKey)) {
            current.objectLabels.set(objectKey, hotspotObject);
        }
        const rowRuleIds = Array.isArray(row && row.ruleIds) ? row.ruleIds : [];
        rowRuleIds.forEach((ruleId) => {
            const normalizedRuleId = String(ruleId || "").trim();
            if (!normalizedRuleId) return;
            current.uniqueRuleIds.add(normalizedRuleId);
            const family = normalizeInsightToken(normalizedRuleId.split("-")[0] || normalizedRuleId, "unknown");
            current.ruleFamilyCounts.set(family, (current.ruleFamilyCounts.get(family) || 0) + 1);
        });
    });

    const recommendations = Array.from(grouped.values())
        .map((item) => {
            let hotspotObject = item.target;
            let hotspotIssueCount = 0;
            item.objectCounts.forEach((count, objectKey) => {
                if (count > hotspotIssueCount) {
                    hotspotIssueCount = count;
                    hotspotObject = item.objectLabels.get(objectKey) || objectKey;
                }
            });
            let dominantRuleFamily = "unknown";
            let dominantRuleCount = 0;
            item.ruleFamilyCounts.forEach((count, family) => {
                if (count > dominantRuleCount) {
                    dominantRuleCount = count;
                    dominantRuleFamily = family;
                }
            });
            const objectHotspotBonus = Math.min(6, Math.max(0, hotspotIssueCount - 1));
            const ruleBreadthBonus = Math.min(4, item.uniqueRuleIds.size);
            const ruleClusterBonus = Math.min(5, Math.max(0, dominantRuleCount - 1));
            const score = item.severityTotal
                + item.sourceTotal
                + item.duplicateBonusTotal
                + objectHotspotBonus
                + ruleBreadthBonus
                + ruleClusterBonus;
            return {
                ...item,
                score,
                hotspotObject,
                hotspotIssueCount,
                ruleBreadth: item.uniqueRuleIds.size,
                dominantRuleFamily: dominantRuleFamily.toUpperCase(),
                dominantRuleCount,
            };
        })
        .sort((a, b) => {
            if (b.score !== a.score) return b.score - a.score;
            if (b.duplicateCount !== a.duplicateCount) return b.duplicateCount - a.duplicateCount;
            if (b.rowCount !== a.rowCount) return b.rowCount - a.rowCount;
            return a.firstIndex - b.firstIndex;
        })
        .slice(0, 5)
        .map((item) => ({
            ...item,
            leadMessage: item.messages[0] || "",
            reason: buildRecommendationReason(item),
        }));

    return { dedupe, recommendations };
}

function buildRecommendationInsightIndex(insights) {
    const index = new Map();
    const recommendations = Array.isArray(insights && insights.recommendations) ? insights.recommendations : [];
    recommendations.forEach((item) => {
        const rowId = String(item && item.representativeRow && item.representativeRow.rowId || "").trim();
        if (rowId) {
            index.set(rowId, item);
        }
    });
    return index;
}

function findRecommendationInsightForViolation(violation) {
    const activeRowKey = String(activeRecommendationRowId || activeWorkspaceRowId || "").trim();
    const exact = workspaceRecommendationInsightByRowId.get(activeRowKey)
        || recommendationInsightByRowId.get(activeRowKey)
        || null;
    if (exact) return exact;

    const violationSource = String((violation && violation.priority_origin) || (violation && violation.source) || "").trim().toUpperCase();
    const violationTarget = basenamePath((violation && (violation.file || violation.object)) || "") || String((violation && violation.object) || "Global");
    const matchByTarget = (insights) => {
        const recommendations = Array.isArray(insights && insights.recommendations) ? insights.recommendations : [];
        return recommendations.find((item) =>
            String(item && item.source || "").trim().toUpperCase() === violationSource
            && String(item && item.target || "").trim() === String(violationTarget || "").trim(),
        ) || null;
    };

    return matchByTarget(workspaceAnalysisInsights)
        || matchByTarget(analysisInsights)
        || ((workspaceAnalysisInsights && workspaceAnalysisInsights.recommendations && workspaceAnalysisInsights.recommendations[0]) || null)
        || ((analysisInsights && analysisInsights.recommendations && analysisInsights.recommendations[0]) || null);
}

function renderAnalysisInsights() {
    if (dedupeSummary) {
        const dedupe = (analysisInsights && analysisInsights.dedupe) || {};
        if (!dedupe.displayedRowCount) {
            dedupeSummary.className = "review-insight-empty";
            dedupeSummary.textContent = "분석 후 중복 정리 결과가 표시됩니다.";
        } else {
            dedupeSummary.className = "";
            dedupeSummary.innerHTML = `
                <div class="review-insight-stats">
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">원시 이슈 수</div>
                        <div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div>
                    </div>
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">표시 행 수</div>
                        <div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div>
                    </div>
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">접힌 중복 수</div>
                        <div class="review-insight-stat-value">${escapeHtml(dedupe.collapsedDuplicateCount)}</div>
                    </div>
                </div>
            `;
        }
    }

    if (priorityRecommendations) {
        const recommendations = (analysisInsights && analysisInsights.recommendations) || [];
        recommendationInsightByRowId = buildRecommendationInsightIndex(analysisInsights);
        if (!recommendations.length) {
            priorityRecommendations.className = "review-insight-empty";
            priorityRecommendations.textContent = "분석 후 우선 수정 추천이 표시됩니다.";
        } else {
            priorityRecommendations.className = "priority-list";
            priorityRecommendations.replaceChildren();
            const frag = document.createDocumentFragment();
            recommendations.forEach((item, idx) => {
                const card = document.createElement("div");
                card.className = "priority-item";
                card.tabIndex = 0;
                card.setAttribute("role", "button");
                card.setAttribute("aria-label", `${idx + 1}. ${String(item.target || "")} 우선 수정 추천 열기`);
                if (item && item.representativeRow && item.representativeRow.rowId) {
                    card.setAttribute("data-row-id", String(item.representativeRow.rowId));
                }
                card.innerHTML = `
                    <div class="priority-item-header">
                        <div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div>
                        <div class="priority-item-score">점수 ${escapeHtml(item.score)}</div>
                    </div>
                    <div class="priority-item-meta">
                        ${escapeHtml(String(item.source).toUpperCase())} · ${escapeHtml(String(item.severity || "Info"))} · 행 ${escapeHtml(item.rowCount)}개 · 이슈 ${escapeHtml(item.duplicateCount)}개
                    </div>
                    <div class="priority-item-meta">
                        hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)}건 · rule ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)}건 · 규칙 ${escapeHtml(item.ruleBreadth || 0)}종
                    </div>
                    <div class="priority-item-reason">${escapeHtml(item.reason || "심각도와 집중도를 기준으로 우선 추천")}</div>
                    <div class="priority-item-actions">
                        <button type="button" class="priority-chip priority-chip-hotspot">같은 hotspot 보기</button>
                        <button type="button" class="priority-chip priority-chip-rule">같은 rule 보기</button>
                    </div>
                    <div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "대표 이슈 메시지 없음"))}</div>
                `;
                const openRecommendation = () => {
                    navWorkspace.onclick();
                    activeRecommendationRowId = String(item && item.representativeRow && item.representativeRow.rowId || "").trim();
                    markWorkspaceRowActive(activeRecommendationRowId);
                    if (item && item.representativeRow && typeof item.representativeRow.onClick === "function") {
                        void item.representativeRow.onClick();
                        focusWorkspaceRow(item.representativeRow.rowId);
                    }
                };
                const hotspotButton = card.querySelector(".priority-chip-hotspot");
                if (hotspotButton) {
                    hotspotButton.addEventListener("click", (event) => {
                        event.stopPropagation();
                        navWorkspace.onclick();
                        applyRecommendationWorkspaceFilter(
                            "hotspot",
                            String(item.hotspotObject || item.target || "Global"),
                            normalizeInsightToken(item.hotspotObject || item.target, "global"),
                            String(item.source || ""),
                        );
                    });
                }
                const ruleButton = card.querySelector(".priority-chip-rule");
                if (ruleButton) {
                    ruleButton.addEventListener("click", (event) => {
                        event.stopPropagation();
                        navWorkspace.onclick();
                        applyRecommendationWorkspaceFilter(
                            "rule_family",
                            String(item.dominantRuleFamily || "UNKNOWN"),
                            normalizeInsightToken(item.dominantRuleFamily, "unknown"),
                            String(item.source || ""),
                        );
                    });
                }
                card.addEventListener("click", openRecommendation);
                card.addEventListener("keydown", (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openRecommendation();
                    }
                });
                frag.appendChild(card);
            });
            priorityRecommendations.appendChild(frag);
        }
    }
}

function markWorkspaceRowActive(rowId) {
    activeWorkspaceRowId = String(rowId || "").trim();
}

function syncWorkspaceRowHighlight() {
    if (!resultBody) return;
    const activeId = String(activeWorkspaceRowId || "").trim();
    const flashId = String(flashedWorkspaceRowId || "").trim();
    resultBody.querySelectorAll("tr.result-item-row").forEach((row) => {
        const isActive = !!activeId && row.getAttribute("data-row-id") === activeId;
        const isFlashed = !!flashId && row.getAttribute("data-row-id") === flashId;
        row.classList.toggle("result-item-row-active", isActive);
        row.classList.toggle("result-item-row-flash", isFlashed);
    });
}

function flashWorkspaceRow(rowId) {
    const targetId = String(rowId || "").trim();
    if (!targetId || !resultBody) return;
    if (activeWorkspaceFlashTimer) {
        window.clearTimeout(activeWorkspaceFlashTimer);
        activeWorkspaceFlashTimer = 0;
    }
    flashedWorkspaceRowId = targetId;
    syncWorkspaceRowHighlight();
    const targetRow = resultBody.querySelector(`tr.result-item-row[data-row-id="${CSS.escape(targetId)}"]`);
    if (targetRow) {
        targetRow.classList.remove("result-item-row-flash");
        void targetRow.offsetWidth;
        targetRow.classList.add("result-item-row-flash");
    }
    activeWorkspaceFlashTimer = window.setTimeout(() => {
        flashedWorkspaceRowId = "";
        syncWorkspaceRowHighlight();
        activeWorkspaceFlashTimer = 0;
    }, 1400);
}

function focusWorkspaceRow(rowId) {
    const targetId = String(rowId || "").trim();
    if (!targetId) return;
    markWorkspaceRowActive(targetId);
    const rowIndex = (workspaceFilteredRows || []).findIndex((row) => String(row && row.rowId || "").trim() === targetId);
    if (rowIndex < 0) {
        queueResultTableWindowRender(true);
        return;
    }
    if (resultTableWrap) {
        const rowHeight = Math.max(24, Number(resultTableVirtualState.rowHeight || 34));
        const bodyOffset = getResultTableBodyOffset();
        const viewportHeight = Math.max(1, resultTableWrap.clientHeight || 1);
        const targetTop = Math.max(0, bodyOffset + (rowIndex * rowHeight) - Math.max(0, (viewportHeight - rowHeight) / 2));
        resultTableWrap.scrollTop = targetTop;
    }
    queueResultTableWindowRender(true);
    window.requestAnimationFrame(() => {
        syncWorkspaceRowHighlight();
        const targetRow = resultBody.querySelector(`tr.result-item-row[data-row-id="${CSS.escape(targetId)}"]`);
        if (targetRow) {
            targetRow.scrollIntoView({ block: "nearest" });
            flashWorkspaceRow(targetId);
        }
    });
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
    if (filterControls.p3) {
        filterControls.p3.checked = false;
        const row = filterControls.p3.closest("div");
        if (row) row.style.display = "none";
    }
}

function getFilterState() {
    const read = (cb, fallback = true) => (cb ? !!cb.checked : fallback);
    return {
        sources: {
            p1: read(filterControls.p1),
            p2: read(filterControls.p2),
            p3: false,
        },
        severities: {
            critical: read(filterControls.critical),
            warning: read(filterControls.warning),
            info: read(filterControls.info),
        },
    };
}

function buildWorkspaceFilterSummaryText() {
    const filters = getFilterState();
    const sourceLabels = [
        filters.sources.p1 ? "P1" : "",
        filters.sources.p2 ? "P2" : "",
    ].filter(Boolean);
    const severityLabels = [
        filters.severities.critical ? "치명" : "",
        filters.severities.warning ? "경고" : "",
        filters.severities.info ? "정보" : "",
    ].filter(Boolean);
    const recommendationText = buildRecommendationWorkspaceFilterText();
    const comparison = buildWorkspaceFilterComparisonSummary();
    const parts = [
        `소스 ${sourceLabels.length ? sourceLabels.join(", ") : "없음"}`,
        `심각도 ${severityLabels.length ? severityLabels.join(", ") : "없음"}`,
    ];
    if (recommendationText) {
        parts.push(recommendationText);
    } else {
        parts.push("추천 필터 없음");
    }
    if (comparison.banner && recommendationText) {
        parts.push(comparison.banner);
    }
    return parts.join(" · ");
}

function renderWorkspaceFilterSummary() {
    if (!workspaceFilterSummaryText) return;
    workspaceFilterSummaryText.textContent = buildWorkspaceFilterSummaryText();
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

function buildP1DetailBlocks(violation) {
    const rawRuleId = String((violation && violation.rule_id) || "unknown");
    const message = String((violation && violation.message) || "").trim();
    const severityRaw = String((violation && violation.severity) || "warning");
    const severity = severityFilterKey(severityRaw);
    const lineNo = positiveLineOrZero(violation && violation.line);
    const fileName = basenamePath(violation && (violation.file || violation.file_name || violation.filename || violation.object));

    const ruleUpper = normalizeP1RuleId(rawRuleId);
    const msgLower = message.toLowerCase();

    let cause = message || "P1 정적 규칙 분석에서 개선이 필요한 코드 패턴이 감지되었습니다.";
    let impact = "코드 품질 및 유지보수성 저하 가능성이 있습니다.";
    let action = "규칙 의도에 맞게 로직을 정리하고 동일 패턴을 함께 점검하세요.";

    const exactTemplates = {
        "CLEAN-DUP-01": {
            cause: "동일/유사 코드가 반복되어 중복 패턴이 감지되었습니다.",
            impact: "수정 누락 가능성이 커지고 유지보수 비용이 증가할 수 있습니다.",
            action: "공통 로직을 함수/헬퍼로 추출해 중복 코드를 제거하세요.",
        },
        "CLEAN-DEAD-01": {
            cause: "도달 불가 또는 미사용 코드가 감지되었습니다.",
            impact: "가독성이 저하되고 코드 의도를 오해할 가능성이 있습니다.",
            action: "불필요 코드를 제거하고 참조/호출 영향 범위를 함께 점검하세요.",
        },
        "HARD-01": {
            cause: "하드코딩된 문자열/값 사용이 감지되었습니다.",
            impact: "환경 변경 시 수정 범위가 커지고 운영 유연성이 저하될 수 있습니다.",
            action: "상수 또는 Config 기반으로 분리하고 의미 있는 이름을 부여하세요.",
        },
        "HARD-02": {
            cause: "하드코딩된 값 사용 패턴이 감지되었습니다.",
            impact: "배포 환경별 조건 대응이 어려워지고 변경 리스크가 증가할 수 있습니다.",
            action: "값을 설정/상수화하고 변경 가능한 파라미터로 분리하세요.",
        },
        "HARD-03": {
            cause: "하드코딩 값 의존 패턴이 감지되었습니다.",
            impact: "운영 정책 변경 시 코드 수정이 반복되어 장애 가능성이 높아질 수 있습니다.",
            action: "Config/상수 테이블로 이관해 값 변경이 코드 수정 없이 가능하도록 정리하세요.",
        },
        "CFG-01": {
            cause: "config 계약 또는 키 정합성 불일치 가능성이 감지되었습니다.",
            impact: "런타임 설정 오동작으로 기능 실패가 발생할 수 있습니다.",
            action: "config 키/타입/기본값을 점검하고 누락 케이스에 대한 방어 분기를 추가하세요.",
        },
        "CFG-ERR-01": {
            cause: "config 로드/검증 오류 처리 누락 가능성이 감지되었습니다.",
            impact: "설정 오류가 연쇄 장애로 전파될 수 있습니다.",
            action: "config 오류 처리 경로를 명시하고 실패 시 안전한 기본 동작을 정의하세요.",
        },
        "STYLE-NAME-01": {
            cause: "명명 규칙 위반 가능성이 감지되었습니다.",
            impact: "코드 의도 파악이 어려워져 협업 비용이 증가할 수 있습니다.",
            action: "프로젝트 명명 규칙에 맞게 식별자 이름을 정리하세요.",
        },
        "STYLE-INDENT-01": {
            cause: "들여쓰기/정렬 규칙 위반 가능성이 감지되었습니다.",
            impact: "가독성이 저하되고 리뷰 효율이 떨어질 수 있습니다.",
            action: "일관된 들여쓰기 규칙으로 정리하고 블록 구조를 명확히 맞추세요.",
        },
        "STYLE-HEADER-01": {
            cause: "헤더/주석 스타일 규칙 위반 가능성이 감지되었습니다.",
            impact: "파일 목적/변경 이력 파악이 어려워질 수 있습니다.",
            action: "프로젝트 표준 헤더/주석 포맷을 적용하세요.",
        },
        "STD-01": {
            cause: "코딩 표준 규칙 위반 가능성이 감지되었습니다.",
            impact: "팀 내 일관성이 깨져 유지보수 효율이 저하될 수 있습니다.",
            action: "표준 가이드에 맞춰 코드 스타일과 구조를 정리하세요.",
        },
        "EXC-TRY-01": {
            cause: "예외 가능 구간에 대한 보호 처리 부족이 감지되었습니다.",
            impact: "실패가 상위 로직으로 전파되어 복구 지연이 발생할 수 있습니다.",
            action: "try-catch와 오류 로깅/복구 분기를 추가해 예외 경로를 명시적으로 처리하세요.",
        },
        "COMP-01": {
            cause: "복잡도 과다 패턴이 감지되었습니다.",
            impact: "이해/테스트 난이도가 올라가 결함 유입률이 증가할 수 있습니다.",
            action: "함수를 분리하고 분기 구조를 단순화해 복잡도를 낮추세요.",
        },
        "COMP-02": {
            cause: "분기 과밀 또는 과도한 복합 조건 패턴이 감지되었습니다.",
            impact: "수정 시 사이드이펙트 가능성이 커질 수 있습니다.",
            action: "조건식을 분해하고 조기 반환 패턴으로 로직 흐름을 단순화하세요.",
        },
        "PERF-01": {
            cause: "Callback 내부에서 delay 호출 패턴이 감지되었습니다.",
            impact: "콜백 처리 지연으로 이벤트 누락/응답성 저하가 발생해 안정성 이슈로 이어질 수 있습니다.",
            action: "Callback 내부 delay 호출을 제거하고, 비동기 스케줄링 또는 타이머 분리 구조로 전환하세요.",
        },
        "PERF-05": {
            cause: "dpSetTimed로 대체 가능한 호출 패턴이 감지되었습니다.",
            impact: "불필요한 호출 방식으로 인해 타이밍 제어 부정확/부하 증가가 발생할 수 있습니다.",
            action: "주기성/지연 호출은 dpSetTimed 기반으로 전환하고, 기존 호출 시점/간격을 함께 정리하세요.",
        },
        "SEC-01": {
            cause: "SQL/쿼리 문자열 구성 시 입력값 검증 부족 패턴이 감지되었습니다.",
            impact: "비정상 입력이 쿼리에 반영되어 보안 취약점으로 이어질 수 있습니다.",
            action: "입력값 검증/정규화와 파라미터화된 쿼리 사용으로 주입 위험을 차단하세요.",
        },
        "DB-01": {
            cause: "문자열 기반 SQL 조합 패턴이 감지되었습니다.",
            impact: "쿼리 가독성/안정성이 저하되고 입력값 결합 실수로 장애 위험이 증가할 수 있습니다.",
            action: "쿼리를 파라미터 바인딩 방식으로 전환하고 문자열 결합 SQL 작성을 줄이세요.",
        },
        "DB-02": {
            cause: "쿼리 주석/설명 누락 가능성이 감지되었습니다.",
            impact: "쿼리 의도 파악이 어려워 유지보수/장애 대응 시간이 증가할 수 있습니다.",
            action: "중요 쿼리 구간에 목적/조건을 설명하는 주석을 보강하고 규칙에 맞게 관리하세요.",
        },
        "SAFE-DIV-01": {
            cause: "0으로 나눗셈이 발생할 수 있는 연산 패턴이 감지되었습니다.",
            impact: "런타임 오류 또는 비정상 값 전파로 연쇄 장애가 발생할 수 있습니다.",
            action: "분모 0 가드 조건과 예외 분기 처리를 추가해 안전하게 계산하세요.",
        },
        "VAL-01": {
            cause: "입력/중간값 유효성 검증 부족 패턴이 감지되었습니다.",
            impact: "잘못된 값이 후속 로직으로 전파되어 오동작 가능성이 커질 수 있습니다.",
            action: "범위/형식/널 여부 검증을 명시적으로 추가하고 실패 분기를 정의하세요.",
        },
        "LOG-LEVEL-01": {
            cause: "로그 레벨 사용이 상황 대비 부적절한 패턴이 감지되었습니다.",
            impact: "운영 시 중요 이벤트 누락 또는 노이즈 증가로 모니터링 품질이 저하될 수 있습니다.",
            action: "상황에 맞는 로그 레벨을 재분류하고 핵심 이벤트는 일관된 레벨로 기록하세요.",
        },
        "LOG-DBG-01": {
            cause: "디버그 로그 과다/잔존 패턴이 감지되었습니다.",
            impact: "로그 노이즈 증가로 장애 원인 추적 효율이 저하될 수 있습니다.",
            action: "불필요한 디버그 로그를 제거하고 운영용 로그만 남기도록 정리하세요.",
        },
        "PERF-02": {
            cause: "반복/루프 구간 비효율 호출 패턴이 감지되었습니다.",
            impact: "불필요한 반복 호출로 응답 지연 및 자원 사용량이 증가할 수 있습니다.",
            action: "반복 구간 호출을 묶음 처리하고 호출 횟수를 최소화하세요.",
        },
        "PERF-02-WHERE-DPT-IN-01": {
            cause: "WHERE 절 DPT IN 사용 최적화 대상 패턴이 감지되었습니다.",
            impact: "조회 조건이 비효율적으로 구성되어 처리 시간이 증가할 수 있습니다.",
            action: "DPT IN 조건을 활용해 조회 범위를 최적화하고 불필요한 탐색을 줄이세요.",
        },
        "PERF-03": {
            cause: "지연/차단성 호출 패턴이 감지되었습니다.",
            impact: "이벤트 처리 스레드 지연으로 시스템 응답성이 저하될 수 있습니다.",
            action: "차단성 호출을 비동기 처리로 전환하고 호출 시점을 분리하세요.",
        },
        "PERF-03-ACTIVE-DELAY-01": {
            cause: "active 컨텍스트에서 delay 사용 패턴이 감지되었습니다.",
            impact: "실시간 이벤트 처리 지연으로 기능 안정성이 저하될 수 있습니다.",
            action: "active 경로에서 delay를 제거하고 타이머/스케줄러 기반 흐름으로 대체하세요.",
        },
        "PERF-EV-01": {
            cause: "이벤트 교환 호출 과다 패턴이 감지되었습니다.",
            impact: "이벤트 트래픽 증가로 처리 지연과 부하 상승이 발생할 수 있습니다.",
            action: "이벤트 교환 횟수를 줄이고 필요 이벤트만 선별해 전달하도록 정리하세요.",
        },
        "ACTIVE-01": {
            cause: "상태 변경 호출 전 Active/Enable 조건 확인 누락 가능성이 감지되었습니다.",
            impact: "비활성 상태에서도 변경 호출이 실행되어 예기치 않은 동작이 발생할 수 있습니다.",
            action: "상태 변경 전에 Active/Enable 가드 조건을 명시하고 false 경로 처리 로직을 추가하세요.",
        },
        "DUP-ACT-01": {
            cause: "동일 대상에 대한 중복 동작 처리(가드) 부재 가능성이 감지되었습니다.",
            impact: "불필요한 중복 호출로 성능 저하 및 상태 불일치 가능성이 증가할 수 있습니다.",
            action: "중복 방지 가드(변경 감지/플래그)와 조건 분기를 추가해 동일 동작 반복을 차단하세요.",
        },
        "PERF-DPSET-BATCH-01": {
            cause: "dpSet 배치화 미적용 패턴이 감지되었습니다.",
            impact: "개별 호출 반복으로 처리 시간이 증가할 수 있습니다.",
            action: "가능한 구간은 dpSet 배치 호출로 전환하세요.",
        },
        "PERF-DPGET-BATCH-01": {
            cause: "dpGet 배치화 미적용 패턴이 감지되었습니다.",
            impact: "개별 조회 반복으로 응답 지연이 발생할 수 있습니다.",
            action: "조회 구간을 배치 요청으로 묶어 I/O 비용을 줄이세요.",
        },
        "PERF-SETVALUE-BATCH-01": {
            cause: "setValue 반복 호출 패턴이 감지되었습니다.",
            impact: "호출 누적으로 불필요한 부하가 발생할 수 있습니다.",
            action: "setValue 호출을 배치 처리 가능한 방식으로 전환하세요.",
        },
        "PERF-SETMULTIVALUE-ADOPT-01": {
            cause: "다중 set 업데이트 패턴이 감지되었습니다.",
            impact: "반복 업데이트로 처리 효율이 저하될 수 있습니다.",
            action: "setMultiValue API를 적용해 다중 업데이트를 통합 처리하세요.",
        },
        "PERF-GETVALUE-BATCH-01": {
            cause: "getValue 반복 조회 패턴이 감지되었습니다.",
            impact: "반복 조회로 조회 지연과 자원 소모가 증가할 수 있습니다.",
            action: "getValue 호출을 배치/통합 조회 방식으로 전환하세요.",
        },
        "PERF-GETMULTIVALUE-ADOPT-01": {
            cause: "다중 get 조회 패턴이 감지되었습니다.",
            impact: "개별 조회 반복으로 성능 저하가 발생할 수 있습니다.",
            action: "getMultiValue API를 적용해 다중 조회를 통합 처리하세요.",
        },
        "PERF-AGG-01": {
            cause: "수동 집계/루프 기반 집계 패턴이 감지되었습니다.",
            impact: "연산 비용 증가로 처리 지연이 누적될 수 있습니다.",
            action: "집계 로직을 공통/배치 처리로 단순화해 반복 연산을 줄이세요.",
        },
    };

    const prefixTemplates = [
        ["PERF-", {
            cause: "반복 호출/업데이트 패턴으로 인한 비효율 가능성이 감지되었습니다.",
            impact: "불필요한 호출 누적으로 응답 지연 및 리소스 사용량 증가가 발생할 수 있습니다.",
            action: "반복 호출을 묶음 처리하거나 배치 방식으로 변경하고, 동일 구간 호출 횟수를 줄이세요.",
        }],
        ["SEC-", {
            cause: "입력값 검증 또는 보안 방어 로직이 충분하지 않은 패턴이 감지되었습니다.",
            impact: "비정상 입력으로 인한 오동작 또는 보안 취약점으로 이어질 수 있습니다.",
            action: "입력값 검증/정규화와 방어 로직을 추가하고, 외부 입력 경로를 우선 점검하세요.",
        }],
        ["DB-", {
            cause: "데이터 조회/갱신 쿼리 관리 규칙 위반 가능성이 감지되었습니다.",
            impact: "쿼리 변경 영향 추적이 어려워지고 운영 안정성이 저하될 수 있습니다.",
            action: "쿼리 작성 방식을 표준화하고 바인딩/주석/오류처리 규칙을 보강하세요.",
        }],
        ["SAFE-", {
            cause: "안전성 관련 보호 조건이 부족한 코드 패턴이 감지되었습니다.",
            impact: "예외 상황에서 런타임 오류나 예기치 않은 상태 전이가 발생할 수 있습니다.",
            action: "가드 조건과 실패 분기 처리를 보강하고, 예외 경로를 명시적으로 처리하세요.",
        }],
        ["VAL-", {
            cause: "값 유효성 검증이 누락되었거나 불충분한 패턴이 감지되었습니다.",
            impact: "잘못된 데이터 전파로 기능 오작동 및 디버깅 비용 증가가 발생할 수 있습니다.",
            action: "입력/중간값 검증을 추가하고 범위/형식 체크를 명확히 분리하세요.",
        }],
        ["LOG-", {
            cause: "로그 처리 규칙 위반 가능성이 감지되었습니다.",
            impact: "운영 이슈 추적성이 저하되어 장애 분석 시간이 증가할 수 있습니다.",
            action: "로그 레벨과 메시지 포맷을 규칙에 맞게 정리하고 핵심 분기 로그를 보완하세요.",
        }],
        ["CLEAN-", {
            cause: "코드 정리(클린업) 규칙 위반 가능성이 감지되었습니다.",
            impact: "가독성과 유지보수성이 저하될 수 있습니다.",
            action: "중복/미사용/불필요 코드를 정리하고 공통 로직으로 통합하세요.",
        }],
        ["HARD-", {
            cause: "하드코딩 지양 규칙 위반 가능성이 감지되었습니다.",
            impact: "환경/요구사항 변경 대응이 어려워질 수 있습니다.",
            action: "하드코딩 값을 설정/상수화하고 코드 의존도를 낮추세요.",
        }],
        ["CFG-", {
            cause: "설정(config) 정합성 규칙 위반 가능성이 감지되었습니다.",
            impact: "런타임 설정 오류로 기능 오작동이 발생할 수 있습니다.",
            action: "config 키/기본값/오류처리 분기를 점검해 설정 계약을 맞추세요.",
        }],
        ["STYLE-", {
            cause: "코딩 스타일 규칙 위반 가능성이 감지되었습니다.",
            impact: "협업 가독성과 일관성이 저하될 수 있습니다.",
            action: "팀 스타일 가이드에 맞게 명명/들여쓰기/헤더를 정리하세요.",
        }],
        ["EXC-", {
            cause: "예외 처리 규칙 위반 가능성이 감지되었습니다.",
            impact: "실패 전파로 장애 분석/복구 시간이 증가할 수 있습니다.",
            action: "예외 처리와 로그/복구 분기를 명시적으로 보강하세요.",
        }],
        ["ACTIVE-", {
            cause: "활성 상태/실행 조건 검증 규칙 위반 가능성이 감지되었습니다.",
            impact: "비활성 구간에서 동작이 수행되어 상태 불일치가 발생할 수 있습니다.",
            action: "Active/Enable 조건 가드와 실패 경로 처리를 명시적으로 추가하세요.",
        }],
        ["DUP-", {
            cause: "중복 동작 방지 규칙 위반 가능성이 감지되었습니다.",
            impact: "중복 호출 누적으로 성능 저하와 예기치 않은 동작이 발생할 수 있습니다.",
            action: "중복 방지 가드와 변경 감지 조건을 추가해 반복 동작을 줄이세요.",
        }],
        ["COMP-", {
            cause: "복잡도 관리 규칙 위반 가능성이 감지되었습니다.",
            impact: "코드 이해도 저하로 결함 유입 위험이 높아질 수 있습니다.",
            action: "함수 분리, 분기 단순화, 조기 반환으로 복잡도를 낮추세요.",
        }],
    ];

    const exact = exactTemplates[ruleUpper];
    if (exact) {
        cause = message || exact.cause;
        impact = exact.impact;
        action = exact.action;
    } else {
        for (const [prefix, tpl] of prefixTemplates) {
            if (ruleUpper.startsWith(prefix)) {
                cause = message || tpl.cause;
                impact = tpl.impact;
                action = tpl.action;
                break;
            }
        }
        if (!exact && ruleUpper === "UNKNOWN" && (msgLower.includes("성능") || msgLower.includes("update"))) {
            cause = message || "반복 호출/업데이트 패턴으로 인한 비효율 가능성이 감지되었습니다.";
            impact = "불필요한 호출 누적으로 응답 지연 및 리소스 사용량 증가가 발생할 수 있습니다.";
            action = "반복 호출을 묶음 처리하거나 배치 방식으로 변경하고, 동일 구간 호출 횟수를 줄이세요.";
        }
    }

    if (severity === "critical") {
        impact = `${impact} (긴급도: 치명, 즉시 수정 필요)`;
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleUpper || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `원인: ${truncateMiddle(cause, 160)}`,
        impact: `영향: ${truncateMiddle(impact, 160)}`,
        action: `권장조치: ${truncateMiddle(action, 120)} (근거: ${evidence})`,
        raw: "",
    };
}

function renderDetailDescriptionBlocks(container, blocks) {
    const title = document.createElement("p");
    title.className = "detail-description-title";
    const titleStrong = document.createElement("strong");
    titleStrong.textContent = "설명:";
    title.appendChild(titleStrong);
    container.appendChild(title);

    [blocks.cause, blocks.impact, stripDetailEvidence(blocks.action)].forEach((line) => {
        const p = document.createElement("p");
        p.className = "detail-description-line";
        p.textContent = line;
        container.appendChild(p);
    });
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
    updateCodeViewerHeaderMeta();
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
    updateCodeViewerHeaderMeta();
    return true;
}

function revealCodeViewerFocus() {
    if (!codeViewer) return;
    const focusShell = codeViewer.closest(".workspace-code-shell");
    if (focusShell) {
        focusShell.classList.remove("workspace-code-shell-focus");
        void focusShell.offsetWidth;
        focusShell.classList.add("workspace-code-shell-focus");
        if (codeViewerFocusTimer) {
            window.clearTimeout(codeViewerFocusTimer);
        }
        codeViewerFocusTimer = window.setTimeout(() => {
            focusShell.classList.remove("workspace-code-shell-focus");
        }, 1800);
        const rect = focusShell.getBoundingClientRect();
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        const isAboveViewport = rect.top < 70;
        const isBelowViewport = rect.bottom > viewportHeight - 24;
        if ((isAboveViewport || isBelowViewport) && typeof focusShell.scrollIntoView === "function") {
            focusShell.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
    }
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
    setActiveJumpRequestState("resolved", clampedLine);
    revealCodeViewerFocus();
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

function findReviewedTodoLineForViolation(violation) {
    const lines = Array.isArray(currentViewerLines) ? currentViewerLines : [];
    if (!lines.length) return 0;

    const explicitTodoLine = positiveLineOrZero(violation && (violation._reviewed_todo_line || violation.reviewed_todo_line));
    if (explicitTodoLine > 0) {
        return explicitTodoLine;
    }

    const blockIndexes = Array.isArray(violation && violation._reviewed_block_indexes)
        ? violation._reviewed_block_indexes
            .map((value) => Number.parseInt(value, 10))
            .filter((value) => Number.isFinite(value) && value > 0)
        : [];
    if (blockIndexes.length) {
        const todoLines = [];
        for (let idx = 0; idx < lines.length; idx += 1) {
            if (/^\/\/\s*>>TODO/i.test(String(lines[idx] || "").trim())) {
                todoLines.push(idx + 1);
            }
        }
        for (const blockIndex of blockIndexes) {
            const anchored = todoLines[blockIndex - 1];
            if (anchored > 0) {
                return anchored;
            }
        }
    }

    const issueId = String((violation && violation.issue_id) || "").trim();
    const ruleId = String((violation && violation.rule_id) || "").trim();
    const normalizedMessage = normalizeReviewedMessageKey(
        String((violation && (violation._reviewed_original_message || violation.message)) || "").trim(),
    );

    const findTodoAnchor = (startIndex) => {
        for (let idx = startIndex; idx >= 0; idx -= 1) {
            if (/^\/\/\s*>>TODO/i.test(String(lines[idx] || "").trim())) {
                return idx + 1;
            }
        }
        return 0;
    };

    if (issueId) {
        for (let idx = 0; idx < lines.length; idx += 1) {
            if (String(lines[idx] || "").includes(issueId)) {
                return findTodoAnchor(idx);
            }
        }
    }

    if (ruleId) {
        const ruleToken = `rule_id=${ruleId}`;
        for (let idx = 0; idx < lines.length; idx += 1) {
            if (String(lines[idx] || "").includes(ruleToken)) {
                return findTodoAnchor(idx);
            }
        }
    }

    if (normalizedMessage) {
        for (let idx = 0; idx < lines.length; idx += 1) {
            const normalizedLine = normalizeReviewedMessageKey(lines[idx]);
            if (
                normalizedLine
                && (
                    normalizedLine.includes(normalizedMessage)
                    || normalizedMessage.includes(normalizedLine)
                )
            ) {
                return findTodoAnchor(idx);
            }
        }
    }

    return 0;
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
    const safeViolation = applyPrecomputedJumpTarget(violation, String((violation && violation._jump_target_source) || "").trim());
    const sourceKey = sourceFilterKey(safeViolation && safeViolation.priority_origin);
    const isP2 = sourceKey === "p2";
    const isP1 = sourceKey === "p1";
    const targetFilePath = String((safeViolation && (safeViolation.file_path || safeViolation.file || safeViolation.file_name || safeViolation.filename)) || "");
    const fileHint = basenamePath(targetFilePath);
    const lineNo = positiveLineOrZero(safeViolation && safeViolation.line);
    const precomputedLine = positiveLineOrZero(safeViolation && safeViolation._jump_target_line);
    const jumpSource = String((safeViolation && safeViolation._jump_target_source) || (isP2 ? "source" : "")).trim().toLowerCase();
    const ruleId = String((safeViolation && safeViolation.rule_id) || "").toLowerCase();

    if (
        isP2
        && (
            ((!fileHint || !String(fileHint).trim()) && lineNo <= 0 && precomputedLine <= 0)
            || (ruleId === "ctrlppcheck.info" && lineNo <= 0 && precomputedLine <= 0)
        )
    ) {
        return { ok: false, reason: "no-locatable-position" };
    }

    if (isP2 && fileHint && !String(fileHint).toLowerCase().endsWith(".ctl")) {
        return { ok: false, reason: "invalid-target-file" };
    }

    const ensureViewerForTarget = async () => {
        const targetFile = targetFilePath || currentViewerFile || fileHint || basenamePath(currentViewerFile);
        if (!targetFile) {
            return { ok: false, reason: jumpSource === "source" ? "source-not-found" : "file-load-miss" };
        }
        if (jumpSource === "source" && !String(targetFile).toLowerCase().endsWith(".ctl")) {
            return { ok: false, reason: "invalid-target-file" };
        }
        const wantSource = jumpSource === "source";
        const wantReviewed = jumpSource === "reviewed";
        const currentFile = String(currentViewerFile || "");
        const shouldReload =
            currentFile !== targetFile
            || (wantSource && currentViewerSource !== "source")
            || (wantReviewed && currentViewerSource !== "reviewed")
            || (!currentViewerContent && currentFile === targetFile);
        if (!shouldReload) return { ok: true };
        try {
            await loadCodeViewer(targetFile, { preferSource: wantSource });
        } catch (_) {
            return { ok: false, reason: wantSource ? "load-source-failed" : "file-load-miss" };
        }
        if (wantSource && String(currentViewerSource || "") !== "source") {
            return { ok: false, reason: "source-not-found" };
        }
        await new Promise((resolve) => {
            window.requestAnimationFrame(() => resolve());
        });
        return { ok: true };
    };

    const retryOnce = async (reason) => {
        const retryable = reason === "reviewed-anchor-miss" || reason === "source-line-miss";
        if (!retryable || (safeViolation && safeViolation._jump_retry_done)) {
            return { ok: false, reason };
        }
        await new Promise((resolve) => {
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(resolve);
            });
        });
        return jumpCodeViewerToViolation({ ...safeViolation, _jump_retry_done: true });
    };

    if (isP1 || isP2 || jumpSource) {
        const viewerReady = await ensureViewerForTarget();
        if (!viewerReady.ok) {
            setActiveJumpRequestState("failed", precomputedLine || lineNo);
            return viewerReady;
        }
    }

    if (!currentViewerContent) {
        setActiveJumpRequestState("failed", precomputedLine || lineNo);
        return { ok: false, reason: "no-viewer" };
    }

    const isReviewed = currentViewerSource === "reviewed";
    const tryNearLine = () => {
        const targetLine = precomputedLine || lineNo;
        if (targetLine <= 0) return false;
        const maxLine = currentViewerLineCount();
        const clamped = maxLine > 0 ? Math.min(targetLine, maxLine) : targetLine;
        if (clamped <= 0) return false;
        return scrollCodeViewerToLine(clamped, { near: true });
    };

    if (precomputedLine > 0 && scrollCodeViewerToLine(precomputedLine, { near: jumpSource !== "source" })) {
        return { ok: true, reason: "hit-precomputed" };
    }

    if (isReviewed) {
        const reviewedTodoLine = findReviewedTodoLineForViolation(safeViolation);
        if (reviewedTodoLine > 0 && scrollCodeViewerToLine(reviewedTodoLine, { near: true })) {
            return { ok: true, reason: "hit-reviewed-todo" };
        }
    }

    if (isP2) {
        if (tryNearLine()) {
            return { ok: true, reason: "hit-line-near" };
        }
        if (scrollCodeViewerToMessage(safeViolation && safeViolation.message)) {
            return { ok: true, reason: "hit-message" };
        }
        setActiveJumpRequestState("failed", precomputedLine || lineNo);
        return retryOnce(isReviewed ? "reviewed-anchor-miss" : "source-line-miss");
    }

    if (!isReviewed && lineNo > 0 && scrollCodeViewerToLine(lineNo)) {
        return { ok: true, reason: "hit-line" };
    }

    if (scrollCodeViewerToMessage(safeViolation && safeViolation.message)) {
        return { ok: true, reason: "hit-message" };
    }

    if (tryNearLine()) {
        return { ok: true, reason: "hit-line-near" };
    }

    setActiveJumpRequestState("failed", precomputedLine || lineNo);
    return retryOnce(isReviewed ? "reviewed-anchor-miss" : "source-line-miss");
}

function pendingJumpLineForViolation(violation) {
    return positiveLineOrZero(
        violation
        && (
            violation._jump_target_line
            || violation._reviewed_todo_line
            || violation.line
        ),
    );
}

async function runWorkspaceSelection(violation, eventName, selectionToken) {
    const pendingLine = pendingJumpLineForViolation(violation);
    setActiveJumpRequestState("pending", pendingLine);
    showDetail(violation, eventName, { jumpPendingLine: pendingLine });
    const jumpResult = await jumpCodeViewerToViolation(violation);
    if (selectionToken !== workspaceSelectionToken) return;
    if (!jumpResult || !jumpResult.ok) {
        setActiveJumpRequestState("failed", pendingLine);
    }
    showDetail(violation, eventName, { jumpResult });
}

function createResultRow(rowData) {
    const source = rowData && rowData.source;
    const object = rowData && rowData.object;
    const severity = rowData && rowData.severity;
    const message = rowData && rowData.message;
    const onclick = rowData && rowData.onClick;
    const rowId = rowData && rowData.rowId;
    const row = document.createElement("tr");
    row.className = "result-item-row";
    if (rowId) {
        row.setAttribute("data-row-id", String(rowId));
    }

    const sourceCell = document.createElement("td");
    sourceCell.className = "result-cell result-cell-source";
    const sourceBadge = document.createElement("span");
    sourceBadge.className = `badge badge-${String(source || "").toLowerCase()}`;
    sourceBadge.textContent = String(source || "N/A");
    sourceCell.appendChild(sourceBadge);

    const objectCell = document.createElement("td");
    objectCell.className = "result-cell result-cell-object";
    const objectTitle = document.createElement("div");
    objectTitle.className = "result-object-title";
    objectTitle.textContent = object || "N/A";
    objectCell.appendChild(objectTitle);
    const objectMeta = document.createElement("div");
    objectMeta.className = "result-object-meta";
    const objectMetaParts = [];
    const sourceText = String(source || "").trim();
    const issueId = String((rowData && rowData.issueId) || "").trim();
    if (sourceText) objectMetaParts.push(sourceText);
    if (issueId) objectMetaParts.push(issueId);
    objectMeta.textContent = objectMetaParts.join(" · ");
    if (objectMeta.textContent) {
        objectCell.appendChild(objectMeta);
    }

    const severityCell = document.createElement("td");
    severityCell.className = "result-cell result-cell-severity";
    const severitySpan = document.createElement("span");
    const severityRaw = String(severity || "Info");
    const severityClassKey = severityFilterKey(severityRaw);
    severitySpan.className = `result-severity severity-${severityClassKey}`;
    severitySpan.textContent = normalizeSeverityKeyword(severityRaw);
    severityCell.appendChild(severitySpan);

    const messageCell = document.createElement("td");
    messageCell.className = "result-cell result-cell-message";
    const messageText = document.createElement("div");
    messageText.className = "result-message-text";
    messageText.textContent = message || "";
    messageCell.appendChild(messageText);
    const messageMeta = document.createElement("div");
    messageMeta.className = "result-message-meta";
    const metaParts = [];
    const lineNo = positiveLineOrZero(rowData && rowData.line);
    const primaryRuleId = Array.isArray(rowData && rowData.ruleIds) ? String(rowData.ruleIds[0] || "").trim() : "";
    if (lineNo > 0) metaParts.push(`line ${lineNo}`);
    if (primaryRuleId) metaParts.push(primaryRuleId);
    if (Number.parseInt(rowData && rowData.duplicateCount, 10) > 1) {
        metaParts.push(`중복 ${Number.parseInt(rowData.duplicateCount, 10)}건`);
    }
    messageMeta.textContent = metaParts.join(" · ");
    if (messageMeta.textContent) {
        messageCell.appendChild(messageMeta);
    }

    row.appendChild(sourceCell);
    row.appendChild(objectCell);
    row.appendChild(severityCell);
    row.appendChild(messageCell);
    row.onclick = async () => {
        const selectionToken = ++workspaceSelectionToken;
        markWorkspaceRowActive(rowId);
        activeRecommendationRowId = recommendationInsightByRowId.has(String(rowId || "").trim()) ? String(rowId || "").trim() : "";
        syncWorkspaceRowHighlight();
        navWorkspace.onclick();
        await new Promise((resolve) => {
            window.requestAnimationFrame(() => resolve());
        });
        if (typeof onclick === "function") {
            void onclick(selectionToken);
        }
    };
    return row;
}

function appendRow(source, object, severity, message, onclick) {
    resultBody.appendChild(createResultRow({ source, object, severity, message, onClick: onclick }));
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
    td.className = "result-spacer-cell";
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
            frag.appendChild(createResultRow(row));
        });
        resultBody.appendChild(frag);
        syncWorkspaceRowHighlight();
        return;
    }

    if (!rows.length) {
        resultBody.replaceChildren();
        resultTableVirtualState.renderedStart = 0;
        resultTableVirtualState.renderedEnd = 0;
        const emptyRow = document.createElement("tr");
        emptyRow.className = "result-empty-row";
        const emptyCell = document.createElement("td");
        emptyCell.colSpan = 4;
        emptyCell.className = "result-empty-state";
        emptyCell.textContent = "현재 필터 기준으로 표시할 결과가 없습니다. 왼쪽 필터를 풀거나 다른 추천 quick filter를 선택해 보세요.";
        emptyRow.appendChild(emptyCell);
        resultBody.appendChild(emptyRow);
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
        frag.appendChild(createResultRow(row));
    }
    frag.appendChild(createResultSpacerRow(Math.max(0, (rows.length - end) * rowHeight)));
    resultBody.replaceChildren(frag);
    syncWorkspaceRowHighlight();

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
    const flattenedP1 = [];
    p1Groups.forEach((group) => {
        (group.violations || []).forEach((v, index) => {
            const violation = { ...v, object: group.object };
            violation.file = violation.file || group.object;
            violation.file_path = violation.file_path || violation.file || group.object;
            violation.priority_origin = violation.priority_origin || "P1";
            const flatKey = String(violation.issue_id || `${violationDisplayFile(violation, group.object)}:${positiveLineOrZero(violation.line)}:${String(violation.rule_id || "")}:${index}`);
            flattenedP1.push({
                flatKey,
                violation,
                eventName: String(group.event || "Global"),
                rowObject: group.object,
                fileKey: violationResolvedFile(violation, group.object),
            });
        });
    });
    const mappingDiagnostics = {
        violation_total: flattenedP1.length,
        violation_unknown_rule_count: 0,
        violation_cfg_rule_count: 0,
        violation_cfg_alias_mapped_count: 0,
        violation_cfg_alias_unmapped_ids: new Set(),
        reviewed_block_total: 0,
        reviewed_unknown_rule_count: 0,
        reviewed_unknown_with_no_line_count: 0,
        reviewed_inferred_rule_count: 0,
        reviewed_inferred_match_success_count: 0,
        reviewed_inferred_match_ambiguous_count: 0,
        reviewed_unknown_after_infer_count: 0,
        review_only_grouped_row_count: 0,
        review_only_grouped_collapsed_count: 0,
        synced_message_mismatch_count: 0,
        synced_rule_message_conflict_samples: [],
    };
    flattenedP1.forEach((item) => {
        const rawRuleId = String(item && item.violation && item.violation.rule_id || "").trim();
        const normalizedRuleId = normalizeP1RuleId(rawRuleId);
        if (!rawRuleId || normalizedRuleId === "UNKNOWN") {
            mappingDiagnostics.violation_unknown_rule_count += 1;
        }
        if (/^cfg-/i.test(rawRuleId)) {
            mappingDiagnostics.violation_cfg_rule_count += 1;
            if (normalizedRuleId !== rawRuleId.toUpperCase()) {
                mappingDiagnostics.violation_cfg_alias_mapped_count += 1;
            } else {
                mappingDiagnostics.violation_cfg_alias_unmapped_ids.add(rawRuleId);
            }
        }
    });

    const byIssueId = new Map();
    const bySecondary = new Map();
    flattenedP1.forEach((item) => {
        const issueId = String(item.violation.issue_id || "").trim();
        if (issueId) {
            if (!byIssueId.has(issueId)) byIssueId.set(issueId, []);
            byIssueId.get(issueId).push(item);
        }
        const secKey = [
            fileIdentityKey(item.fileKey),
            positiveLineOrZero(item.violation.line),
            normalizeP1RuleId(item.violation.rule_id),
            String(item.violation.message || "").trim(),
        ].join("||");
        if (!bySecondary.has(secKey)) bySecondary.set(secKey, []);
        bySecondary.get(secKey).push(item);
    });

    const usedFlatKeys = new Set();
    const p1Rows = [];
    let syncedCount = 0;
    let reviewOnlyCount = 0;
    let violationOnlyCount = 0;
    const reviewOnlyGrouped = new Map();

    const pushP1Row = (baseViolation, eventName, syncState, originLabel, matchedItems = [], overrideMessage = "", syncReason = "") => {
        const lines = matchedItems
            .map((item) => positiveLineOrZero(item.violation && item.violation.line))
            .filter((line) => line > 0);
        const baseLines = Array.isArray(baseViolation._duplicate_lines) ? baseViolation._duplicate_lines : [];
        const uniqueLines = Array.from(new Set(lines.concat(baseLines).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
        const primaryLine = positiveLineOrZero(baseViolation._primary_line || baseViolation.line) || uniqueLines[0] || 0;
        const groupedRules = Array.from(
            new Set(matchedItems.map((item) => String(item.violation && item.violation.rule_id || "").trim()).filter(Boolean)),
        );
        const baseGroupedRules = Array.isArray(baseViolation._group_rule_ids) ? baseViolation._group_rule_ids : [];
        groupedRules.push(...baseGroupedRules.map((value) => String(value || "").trim()).filter(Boolean));
        if (!groupedRules.length && baseViolation.rule_id) groupedRules.push(String(baseViolation.rule_id));
        const groupedMessages = Array.from(
            new Set(matchedItems.map((item) => String(item.violation && item.violation.message || "").trim()).filter(Boolean)),
        );
        const baseGroupedMessages = Array.isArray(baseViolation._group_messages) ? baseViolation._group_messages : [];
        groupedMessages.push(...baseGroupedMessages.map((value) => String(value || "").trim()).filter(Boolean));
        if (!groupedMessages.length && overrideMessage) groupedMessages.push(overrideMessage);
        if (!groupedMessages.length && baseViolation.message) groupedMessages.push(String(baseViolation.message));
        const groupedIssues = Array.from(
            new Set(matchedItems.map((item) => String(item.violation && item.violation.issue_id || "").trim()).filter(Boolean)),
        );
        const baseGroupedIssues = Array.isArray(baseViolation._group_issue_ids) ? baseViolation._group_issue_ids : [];
        groupedIssues.push(...baseGroupedIssues.map((value) => String(value || "").trim()).filter(Boolean));
        if (!groupedIssues.length && baseViolation.issue_id) groupedIssues.push(String(baseViolation.issue_id));
        const duplicateCountFromBase = Number.parseInt(baseViolation._duplicate_count, 10);
        const duplicateCount = Number.isFinite(duplicateCountFromBase) && duplicateCountFromBase > 0
            ? duplicateCountFromBase
            : Math.max(1, matchedItems.length || 1);
        const groupingMode = String(baseViolation._grouping_mode || "reviewed_block");

        const enriched = {
            ...baseViolation,
            priority_origin: "P1",
            line: primaryLine || baseViolation.line || 0,
            _duplicate_count: duplicateCount,
            _duplicate_lines: uniqueLines,
            _primary_line: primaryLine,
            _grouping_mode: groupingMode,
            _group_rule_ids: Array.from(new Set(groupedRules)),
            _group_messages: Array.from(new Set(groupedMessages)),
            _group_issue_ids: Array.from(new Set(groupedIssues)),
            _sync_state: syncState,
            _sync_origin: originLabel,
            _sync_reason: syncReason || "",
        };
        const jumpReadyViolation = applyPrecomputedJumpTarget(enriched, "reviewed");
        const rowMessage = String(baseViolation.message || overrideMessage || "");
        p1Rows.push({
            rowId: `p1:${jumpReadyViolation.issue_id || `${jumpReadyViolation.object || "global"}:${jumpReadyViolation.line || 0}:${rowMessage}`}`,
            source: "P1",
            object: violationDisplayFile(baseViolation, "Global") || "Global",
            severity: baseViolation.severity || "Info",
            message: rowMessage,
            file: violationResolvedFile(baseViolation),
            line: primaryLine || baseViolation.line || 0,
            issueId: jumpReadyViolation.issue_id || "",
            duplicateCount,
            ruleIds: Array.from(new Set(groupedRules)),
            onClick: async (selectionToken) => {
                await runWorkspaceSelection(jumpReadyViolation, eventName || "Global", selectionToken);
            },
        });
    };

    // REVIEWED truth-first rows
    reviewedTodoCacheByFile.forEach((blocks, reviewedFile) => {
        const fileBlocks = Array.isArray(blocks) ? blocks : [];
        mappingDiagnostics.reviewed_block_total += fileBlocks.length;
        fileBlocks.forEach((block, idx) => {
            const meta = (block && block.meta && typeof block.meta === "object") ? block.meta : {};
            const issueId = String(meta.issue_id || "").trim();
            const ruleId = String(meta.rule_id || "").trim();
            const lineNo = positiveLineOrZero(meta.line || 0);
            const normalizedRuleId = normalizeP1RuleId(ruleId);
            const inferred = inferRuleIdFromReviewedBlock(block);
            const inferredRuleId = normalizeP1RuleId(inferred.inferredRuleId);
            if (inferredRuleId !== "UNKNOWN" && inferred.source !== "meta") {
                mappingDiagnostics.reviewed_inferred_rule_count += 1;
            }
            if (!ruleId || normalizedRuleId === "UNKNOWN") {
                mappingDiagnostics.reviewed_unknown_rule_count += 1;
                if (lineNo <= 0) {
                    mappingDiagnostics.reviewed_unknown_with_no_line_count += 1;
                }
            }
            const effectiveRuleId = normalizedRuleId !== "UNKNOWN" ? normalizedRuleId : inferredRuleId;
            const blockMessage = String(block.message || "").trim();
            const secondaryKey = [
                fileIdentityKey(meta.file || reviewedFile),
                lineNo,
                effectiveRuleId,
                blockMessage,
            ].join("||");

            let matched = [];
            let matchedReason = "";
            if (issueId && byIssueId.has(issueId)) {
                matched = (byIssueId.get(issueId) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                if (matched.length) matchedReason = "meta_exact";
            }
            if (!matched.length && (lineNo > 0 || ruleId || blockMessage) && bySecondary.has(secondaryKey)) {
                matched = (bySecondary.get(secondaryKey) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                if (matched.length) matchedReason = "secondary_exact";
            }
            if (!matched.length && effectiveRuleId !== "UNKNOWN") {
                const targetFile = fileIdentityKey(meta.file || reviewedFile);
                const targetLine = lineNo > 0 ? lineNo : positiveLineOrZero(block.todo_line);
                const inferredPrefix = p1RulePrefixGroup(effectiveRuleId);
                const proximityCandidates = flattenedP1.filter((item) => {
                    if (usedFlatKeys.has(item.flatKey)) return false;
                    if (fileIdentityKey(item.fileKey) !== targetFile) return false;
                    const itemRule = normalizeP1RuleId(item.violation.rule_id);
                    if (itemRule === "UNKNOWN") return false;
                    const isDpGetVsGetMultiConflict = (
                        (effectiveRuleId === "PERF-DPGET-BATCH-01" && itemRule === "PERF-GETMULTIVALUE-ADOPT-01")
                        || (effectiveRuleId === "PERF-GETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPGET-BATCH-01")
                    );
                    const isDpSetVsSetMultiConflict = (
                        (effectiveRuleId === "PERF-DPSET-BATCH-01" && itemRule === "PERF-SETMULTIVALUE-ADOPT-01")
                        || (effectiveRuleId === "PERF-SETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPSET-BATCH-01")
                    );
                    if (isDpGetVsGetMultiConflict || isDpSetVsSetMultiConflict) return false;
                    const itemPrefix = p1RulePrefixGroup(itemRule);
                    if (!(itemRule === effectiveRuleId || itemPrefix === inferredPrefix)) return false;
                    const itemLine = positiveLineOrZero(item.violation.line);
                    if (targetLine <= 0 || itemLine <= 0) return false;
                    return Math.abs(itemLine - targetLine) <= 25;
                });
                if (proximityCandidates.length === 1) {
                    matched = proximityCandidates;
                    matchedReason = "inferred_proximity";
                    mappingDiagnostics.reviewed_inferred_match_success_count += 1;
                } else if (proximityCandidates.length > 1) {
                    mappingDiagnostics.reviewed_inferred_match_ambiguous_count += 1;
                }
            }

            if (matched.length) {
                matched.forEach((item) => usedFlatKeys.add(item.flatKey));
                const top = matched[0];
                const representative = {
                    ...top.violation,
                    file: top.violation.file || reviewedFile,
                    file_path: top.violation.file_path || top.violation.file || reviewedFile,
                    object: top.violation.object || top.rowObject || reviewedFile,
                    message: top.violation.message || blockMessage,
                    line: positiveLineOrZero(top.violation.line) || lineNo || positiveLineOrZero(block.todo_line),
                    rule_id: top.violation.rule_id || effectiveRuleId || ruleId,
                    issue_id: top.violation.issue_id || issueId,
                    severity: top.violation.severity || block.severity || "Info",
                    _reviewed_todo_line: positiveLineOrZero(block.todo_line),
                    _reviewed_block_indexes: [idx + 1],
                    _reviewed_original_message: blockMessage || "",
                };
                if (normalizeReviewedMessageKey(blockMessage) && normalizeReviewedMessageKey(top.violation.message || "") && normalizeReviewedMessageKey(blockMessage) !== normalizeReviewedMessageKey(top.violation.message || "")) {
                    mappingDiagnostics.synced_message_mismatch_count += 1;
                    if (mappingDiagnostics.synced_rule_message_conflict_samples.length < 10) {
                        mappingDiagnostics.synced_rule_message_conflict_samples.push({
                            file: basenamePath(top.violation.file || reviewedFile),
                            line: positiveLineOrZero(top.violation.line),
                            rule_id: normalizeP1RuleId(top.violation.rule_id),
                            violation_message: String(top.violation.message || ""),
                            reviewed_message: String(blockMessage || ""),
                        });
                    }
                }
                pushP1Row(representative, top.eventName || "Global", "synced", "mixed", matched, "", matchedReason);
                syncedCount += 1;
            } else {
                const state = issueId ? "review-only" : "partial";
                const displayMessage = blockMessage || "REVIEWED TODO 항목";
                const reviewFile = basenamePath(meta.file || reviewedFile);
                const reviewKey = [
                    fileIdentityKey(reviewFile),
                    normalizeReviewedMessageKey(displayMessage),
                ].join("||");
                if (!reviewOnlyGrouped.has(reviewKey)) {
                    reviewOnlyGrouped.set(reviewKey, {
                        file: reviewFile,
                        message: displayMessage,
                        severity: block.severity || "Info",
                        lines: [],
                        todoLines: [],
                        issueIds: [],
                        ruleIds: [],
                        states: new Set(),
                        blockIndexes: [],
                    });
                }
                const grouped = reviewOnlyGrouped.get(reviewKey);
                if (lineNo > 0) grouped.lines.push(lineNo);
                if (positiveLineOrZero(block.todo_line) > 0) grouped.todoLines.push(positiveLineOrZero(block.todo_line));
                const syntheticIssueId = issueId || `REVIEW-ONLY-${reviewedFile}-${idx + 1}`;
                grouped.issueIds.push(syntheticIssueId);
                grouped.ruleIds.push(effectiveRuleId || "UNKNOWN");
                grouped.states.add(state);
                grouped.blockIndexes.push(idx + 1);
                reviewOnlyCount += 1;
                if ((effectiveRuleId || "UNKNOWN") === "UNKNOWN") {
                    mappingDiagnostics.reviewed_unknown_after_infer_count += 1;
                }
            }
        });
    });

    reviewOnlyGrouped.forEach((grouped) => {
        const uniqueLines = Array.from(new Set((grouped.lines || []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
        const uniqueTodoLines = Array.from(new Set((grouped.todoLines || []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
        const uniqueIssues = Array.from(new Set((grouped.issueIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
        const uniqueRules = Array.from(new Set((grouped.ruleIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
        const uniqueBlocks = Array.from(new Set((grouped.blockIndexes || []).map((n) => Number.parseInt(n, 10)).filter((n) => Number.isFinite(n) && n > 0))).sort((a, b) => a - b);
        const state = grouped.states.has("partial") ? "partial" : "review-only";
        mappingDiagnostics.review_only_grouped_row_count += 1;
        mappingDiagnostics.review_only_grouped_collapsed_count += Math.max(0, uniqueIssues.length - 1);
        const synthetic = {
            priority_origin: "P1",
            issue_id: uniqueIssues[0] || `REVIEW-ONLY-${grouped.file || "UNKNOWN"}-1`,
            rule_id: uniqueRules[0] || "UNKNOWN",
            severity: grouped.severity || "Info",
            message: grouped.message || "REVIEWED TODO 항목",
            file: grouped.file || "",
            object: grouped.file || "Global",
            line: uniqueLines[0] || 0,
            _grouping_mode: "review_only_message",
            _group_rule_ids: uniqueRules,
            _group_messages: [grouped.message || "REVIEWED TODO 항목"],
            _group_issue_ids: uniqueIssues,
            _duplicate_count: Math.max(1, uniqueIssues.length),
            _duplicate_lines: uniqueLines,
            _primary_line: uniqueLines[0] || 0,
            _reviewed_todo_line: uniqueTodoLines[0] || 0,
            _reviewed_todo_lines: uniqueTodoLines,
            _reviewed_original_message: grouped.message || "REVIEWED TODO 항목",
            _reviewed_block_indexes: uniqueBlocks,
        };
        pushP1Row(synthetic, "Global", state, "reviewed", [], grouped.message || "REVIEWED TODO 항목", "review_only");
    });

    // Violation-only rows are intentionally hidden from default list to keep REVIEWED truth-first UX.
    const leftovers = flattenedP1.filter((item) => !usedFlatKeys.has(item.flatKey));
    violationOnlyCount = leftovers.length;

    if (p1Rows.length > 0) {
        console.debug("[P1 sync]", {
            synced_count: syncedCount,
            review_only_count: reviewOnlyCount,
            violation_only_count: violationOnlyCount,
            rows: p1Rows.length,
        });
        console.debug("[P1 mapping diagnostics]", {
            ...mappingDiagnostics,
            violation_cfg_alias_unmapped_ids: Array.from(mappingDiagnostics.violation_cfg_alias_unmapped_ids).sort(),
        });
    }
    nextRows.push(...p1Rows);

    p2List.forEach((v) => {
        const objectName = String(v.object || "Global");
        const fileFromPayload = violationDisplayFile(v);
        const fileFromObject = /\.ctl$/i.test(objectName) ? basenamePath(objectName) : "";
        const fileHint = fileFromPayload || fileFromObject;
        const displayObject = fileHint || objectName || "Global";
        const p2Violation = {
            ...v,
            object: displayObject,
            file: String(v.file_path || v.file || fileHint || ""),
            file_path: String(v.file_path || v.file || fileHint || ""),
            priority_origin: v.priority_origin || "P2",
            issue_id: String(v.issue_id || `P2::${fileHint || displayObject}:${String(v.rule_id || "")}:${positiveLineOrZero(v.line)}`),
        };
        const jumpReadyP2Violation = applyPrecomputedJumpTarget(p2Violation, "source");
        const p2Localized = buildP2LocalizedMessage(p2Violation);
        nextRows.push({
            rowId: `p2:${jumpReadyP2Violation.issue_id || `${jumpReadyP2Violation.object || "global"}:${jumpReadyP2Violation.line || 0}:${p2Localized.shortText}`}`,
            source: jumpReadyP2Violation.priority_origin || "P2",
            object: jumpReadyP2Violation.object || "Global",
            severity: jumpReadyP2Violation.severity || jumpReadyP2Violation.type || "Info",
            message: p2Localized.shortText,
            file: String(jumpReadyP2Violation.file_path || jumpReadyP2Violation.file || ""),
            line: positiveLineOrZero(jumpReadyP2Violation.line),
            issueId: jumpReadyP2Violation.issue_id || "",
            duplicateCount: 1,
            ruleIds: [String(jumpReadyP2Violation.rule_id || "").trim()].filter(Boolean),
            onClick: async (selectionToken) => {
                await runWorkspaceSelection(jumpReadyP2Violation, "Global", selectionToken);
            },
        });
    });

    workspaceRowIndex = nextRows;
    analysisInsights = deriveAnalysisInsights(nextRows);
}

function showDetail(violation, eventName, options = {}) {
    violationDetail.replaceChildren();
    renderInspectorSelectionMeta(violation, options);
    const detailSourceKey = sourceFilterKey(violation.priority_origin || "P1");
    const divider = document.createElement("div");
    divider.className = "detail-divider";
    violationDetail.appendChild(divider);
    const isP1 = detailSourceKey === "p1";
    const isP2 = detailSourceKey === "p2";
    if (isP2) {
        renderDetailDescriptionBlocks(violationDetail, buildP2DetailBlocks(violation));
    } else if (isP1) {
        renderDetailDescriptionBlocks(violationDetail, buildP1DetailBlocks(violation));
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
        appendDetailNote(violationDetail, jumpMsg, "detail-note-warning");
    }

    const aiMatch = findAiMatchForViolation(violation, eventName);
    const aiStatus = String((aiMatch && aiMatch.status) || "Pending");
    const hasAiSuggestion = !!(aiMatch && aiStatus !== "Ignored");
    const sourceKey = sourceFilterKey(violation.priority_origin || "P1");
    const canShowAiPanel = sourceKey === "p1" || sourceKey === "p2";
    resetInspectorTabsForViolation({ hasAiSuggestion: hasAiSuggestion || canShowAiPanel, preferAi: activeInspectorTab === "ai" });

    if (hasAiSuggestion) {
        hideAiEmptyState();
        aiCard.style.display = "block";
        aiReviewExpanded = false;
        setAiReviewText(aiMatch.review);
        const btnAiAccept = document.getElementById("btn-ai-accept");
        const btnAiDiff = document.getElementById("btn-ai-diff");
        const btnAiSourceApply = document.getElementById("btn-ai-source-apply");
        const btnAiIgnore = document.getElementById("btn-ai-ignore");
        const btnAiMoreLocal = document.getElementById("btn-ai-more");
        const aiKey = makeAiCardKey(violation, eventName, aiMatch);
        aiCard.dataset.aiKey = aiKey;
        if (activeDiffModalKey && activeDiffModalKey !== aiKey) {
            closeDiffModal();
        }
        aiMoreMenuOpen = false;
        syncAiMoreMenuUi();
        function handleProposalSelect(proposalId, explicitBundle = null) {
            const latestBundle = explicitBundle || autofixProposalCache.get(aiKey) || null;
            if (!latestBundle || !Array.isArray(latestBundle.proposals)) return;
            latestBundle.active_proposal_id = String(proposalId || "");
            autofixProposalCache.set(aiKey, latestBundle);
            const active = getActiveAutofixProposal(latestBundle);
            const gen = String((active && active.generator_type) || "unknown").toUpperCase();
            const score = Number.parseInt((active && active.compare_score && active.compare_score.total) || 0, 10) || 0;
            syncAiPanel(latestBundle, `선택 후보: ${gen} · 점수 ${score}`, "#1565c0");
        }

        function syncAiPanel(bundle = null, statusMessage = null, statusColor = "") {
            const activeProposal = getActiveAutofixProposal(bundle);
            const accepted = String((aiMatch && aiMatch.status) || "Pending") === "Accepted";
            renderAiSummaryList(buildAiSummaryLines(violation, aiMatch, activeProposal));
            setAutofixDiffPanel(activeProposal ? activeProposal.unified_diff : "");
            setAutofixValidationPanel(
                activeProposal ? formatAutofixValidationSummary(activeProposal) : "",
                { ok: activeProposal ? !hasAutofixValidationErrors(activeProposal) : true },
            );
            renderAutofixComparePanel(bundle, (proposalId) => handleProposalSelect(proposalId));
            if (activeDiffModalKey === aiKey && bundle) {
                renderDiffModal(bundle, violation, (proposalId, selectedBundle) => handleProposalSelect(proposalId, selectedBundle));
            }

            if (btnAiAccept) {
                btnAiAccept.disabled = accepted;
                btnAiAccept.textContent = accepted ? "REVIEWED 적용 완료" : "REVIEWED 적용";
                btnAiAccept.style.opacity = accepted ? "0.7" : "1";
            }
            if (btnAiDiff) {
                btnAiDiff.disabled = false;
                btnAiDiff.textContent = "변경 내용 보기";
                btnAiDiff.style.opacity = "1";
            }
            if (btnAiSourceApply) {
                btnAiSourceApply.disabled = accepted || !activeProposal;
                btnAiSourceApply.textContent = accepted ? "적용 완료" : "Source 적용";
                btnAiSourceApply.style.opacity = (!accepted && activeProposal) ? "1" : "0.7";
            }
            if (btnAiIgnore) {
                btnAiIgnore.disabled = accepted;
                btnAiIgnore.style.display = "inline-flex";
                btnAiIgnore.style.opacity = accepted ? "0.7" : "1";
            }
            if (btnAiMoreLocal) {
                btnAiMoreLocal.disabled = false;
                btnAiMoreLocal.style.opacity = "1";
            }

            if (statusMessage === null) {
                setAiStatusInline(accepted ? "적용 완료" : "", accepted ? "#2e7d32" : "");
            } else {
                setAiStatusInline(statusMessage, statusColor || "");
            }
        }

        const cachedAutofixBundle = autofixProposalCache.get(aiKey) || null;
        syncAiPanel(cachedAutofixBundle);

        if (btnAiMoreLocal) {
            btnAiMoreLocal.onclick = () => {
                aiMoreMenuOpen = !aiMoreMenuOpen;
                syncAiMoreMenuUi();
            };
        }

        if (btnAiDiff) {
            btnAiDiff.onclick = async () => {
                const boundKey = aiKey;
                let bundle = autofixProposalCache.get(boundKey) || null;
                let proposal = getActiveAutofixProposal(bundle);
                if (!proposal) {
                    btnAiDiff.disabled = true;
                    btnAiDiff.textContent = "준비 중...";
                    setAiStatusInline("변경안을 준비 중입니다.", "#556070");
                    try {
                        bundle = await prepareAutofixProposal(violation, eventName, aiMatch);
                        if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                        autofixProposalCache.set(boundKey, bundle);
                        proposal = getActiveAutofixProposal(bundle);
                        syncAiPanel(bundle, `변경안 준비 완료${proposal ? ` · ${String((proposal.generator_type || "llm")).toUpperCase()}` : ""}`, "#1565c0");
                    } catch (err) {
                        if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                        const msg = String((err && err.message) || err || "autofix prepare failed");
                        syncAiPanel(autofixProposalCache.get(boundKey) || null, `변경안 준비 실패: ${msg}`, "#c62828");
                        return;
                    } finally {
                        if ((aiCard.dataset.aiKey || "") === boundKey) {
                            btnAiDiff.textContent = "변경 내용 보기";
                            btnAiDiff.disabled = false;
                        }
                    }
                }
                bundle = autofixProposalCache.get(boundKey) || bundle;
                if (!bundle) return;
                openDiffModal(bundle, violation, boundKey, (proposalId, selectedBundle) => handleProposalSelect(proposalId, selectedBundle));
            };
        }

        if (btnAiSourceApply) {
            btnAiSourceApply.onclick = async () => {
                const boundKey = aiKey;
                let bundle = autofixProposalCache.get(boundKey) || null;
                let proposal = getActiveAutofixProposal(bundle);
                btnAiSourceApply.disabled = true;
                btnAiSourceApply.textContent = "적용 중...";
                if (btnAiDiff) btnAiDiff.disabled = true;
                if (btnAiAccept) btnAiAccept.disabled = true;
                if (btnAiIgnore) btnAiIgnore.disabled = true;
                setAiStatusInline("Source 변경을 적용 중입니다.", "#556070");
                try {
                    if (!proposal) {
                        bundle = await prepareAutofixProposal(violation, eventName, aiMatch);
                        if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                        autofixProposalCache.set(boundKey, bundle);
                        proposal = getActiveAutofixProposal(bundle);
                    }
                    if (!proposal) throw new Error("autofix proposal is missing");
                    const result = await applyAutofixProposal(proposal, violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    const mergedProposal = { ...(proposal || {}), ...(result || {}) };
                    let mergedBundle = bundle;
                    if (mergedBundle && Array.isArray(mergedBundle.proposals)) {
                        mergedBundle.proposals = mergedBundle.proposals.map((item) =>
                            String(item.proposal_id) === String(mergedProposal.proposal_id) ? mergedProposal : item
                        );
                    } else {
                        mergedBundle = normalizeAutofixBundle(mergedProposal);
                    }
                    autofixProposalCache.set(boundKey, mergedBundle);
                    aiMatch.status = "Accepted";
                    syncAiPanel(mergedBundle, "Source 적용 완료", "#2e7d32");
                    const resultFile = violationResolvedFile(result, proposal && proposal.file);
                    if (resultFile && sameFileIdentity(currentViewerFile, resultFile)) {
                        try {
                            await loadCodeViewer(resultFile || currentViewerFile, { preferSource: true });
                        } catch (_) {
                            // fail-soft
                        }
                    }
                } catch (err) {
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    const msg = String((err && err.message) || err || "autofix apply failed");
                    const payload = (err && err.payload) || {};
                    const validationSummary = formatAutofixValidationSummary(payload);
                    syncAiPanel(autofixProposalCache.get(boundKey) || bundle, `Source 적용 실패: ${msg}`, "#c62828");
                    setAutofixValidationPanel(validationSummary || msg, { ok: false });
                }
            };
        }

        if (btnAiAccept) {
            btnAiAccept.onclick = async () => {
                const boundKey = aiKey;
                btnAiAccept.disabled = true;
                btnAiAccept.textContent = "적용 중...";
                if (btnAiSourceApply) btnAiSourceApply.disabled = true;
                if (btnAiDiff) btnAiDiff.disabled = true;
                if (btnAiIgnore) btnAiIgnore.disabled = true;
                setAiStatusInline("REVIEWED 주석을 적용 중입니다.", "#556070");
                try {
                    const result = await applyAiSuggestion(violation, eventName, aiMatch);
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    aiMatch.status = "Accepted";
                    const appliedBlocks = positiveLineOrZero(result && result.applied_blocks);
                    syncAiPanel(
                        autofixProposalCache.get(boundKey) || null,
                        appliedBlocks > 0 ? `REVIEWED 적용 완료 · 블록 ${appliedBlocks}개` : "REVIEWED 적용 완료",
                        "#2e7d32",
                    );
                    const resultFile = violationResolvedFile(result, violationResolvedFile(violation));
                    if (resultFile && sameFileIdentity(currentViewerFile, resultFile)) {
                        try {
                            await loadCodeViewer(resultFile || currentViewerFile);
                        } catch (_) {
                            // fail-soft
                        }
                    }
                } catch (err) {
                    if ((aiCard.dataset.aiKey || "") !== boundKey) return;
                    const msg = String((err && err.message) || err || "AI review apply failed");
                    syncAiPanel(autofixProposalCache.get(boundKey) || null, `REVIEWED 적용 실패: ${msg}`, "#c62828");
                }
            };
        }

        if (btnAiIgnore) {
            btnAiIgnore.onclick = () => {
                aiMatch.status = "Ignored";
                aiCard.style.display = "none";
                aiCard.dataset.aiKey = "";
                aiMoreMenuOpen = false;
                syncAiMoreMenuUi();
                closeDiffModal();
                setInspectorTab("detail", false);
                setAiStatusInline("");
                setAutofixDiffPanel("");
                setAutofixValidationPanel("");
            };
        }
    } else {
        aiReviewExpanded = false;
        aiMoreMenuOpen = false;
        syncAiMoreMenuUi();
        closeDiffModal();
        setAiReviewText("");
        setAiStatusInline("");
        setAutofixDiffPanel("");
        setAutofixValidationPanel("");
        if (canShowAiPanel) {
            const empty = describeAiUnavailable(violation, eventName);
            renderAiEmptyState(empty.title, empty.detail);
        } else {
            hideAiEmptyState();
            aiCard.style.display = "none";
            aiCard.dataset.aiKey = "";
        }
    }
}
function renderWorkspace(options = {}) {
    workspaceRenderToken += 1;
    workspaceFilteredRows = (workspaceRowIndex || []).filter((row) => shouldRenderRow(row.source, row.severity) && rowMatchesRecommendationFilter(row));
    workspaceAnalysisInsights = deriveAnalysisInsights(workspaceFilteredRows);
    workspaceRecommendationInsightByRowId = buildRecommendationInsightIndex(workspaceAnalysisInsights);
    if (activeWorkspaceRowId && !(workspaceFilteredRows || []).some((row) => String(row.rowId || "") === String(activeWorkspaceRowId))) {
        activeWorkspaceRowId = "";
    }
    if ((options && options.resetScroll !== false) && resultTableWrap) {
        resultTableWrap.scrollTop = 0;
    }
    renderWorkspaceQuickFilter();
    renderWorkspaceFilterSummary();
    queueResultTableWindowRender(true);
}

function getSelectedFiles() {
    return Array.from(fileList.querySelectorAll("input[type='checkbox'][data-file]"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.getAttribute("data-file"));
}

function getSelectedInputSources() {
    return sessionInputSources.map((item) => ({
        type: String(item.type || ""),
        value: String(item.value || ""),
    }));
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
    renderExternalInputSources();
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
    const phase = String(progress.phase || "");
    const etaMs = timing.eta_ms;
    const elapsedMs = timing.elapsed_ms;

    let phaseLabel = "";
    if (phase === "queued") phaseLabel = "대기";
    else if (phase === "read_source") phaseLabel = "파일 로드";
    else if (phase === "heuristic_review") phaseLabel = "정적 분석";
    else if (phase === "ctrlpp_check") phaseLabel = "CtrlppCheck";
    else if (phase === "live_ai_review") phaseLabel = "Live AI";
    else if (phase === "write_reports") phaseLabel = "리포트 작성";
    else if (phase === "analyze_file_done") phaseLabel = "파일 완료";
    else if (phase === "analyze_file_failed") phaseLabel = "파일 실패";

    if (analyzeProgressStatus) {
        const head = status === "queued" ? "분석 대기 중..." : status === "running" ? "분석 중..." : status === "completed" ? "분석 완료" : "분석 실패";
        const parts = [head];
        if (currentFile) parts.push(currentFile);
        if (phaseLabel) parts.push(phaseLabel);
        analyzeProgressStatus.textContent = parts.join(" · ");
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
        ai_review_statuses: payload.ai_review_statuses || [],
        output_dir: payload.output_dir || "",
        metrics: payload.metrics || {},
        report_jobs: payload.report_jobs || {},
    };
    viewerContentCache.clear();
    workspaceRowIndex = [];
    analysisInsights = {
        dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
        recommendations: [],
    };
    functionScopeCacheByFile.clear();
    autofixProposalCache.clear();
    setActiveJumpRequestState("idle", 0);
    setAutofixDiffPanel("");
    setAutofixValidationPanel("");
    closeDiffModal();
    const selected = getSelectedFiles();
    await prepareFunctionScopeCacheForSelectedFiles(selected);
    buildWorkspaceRowIndex();

    updateDashboard();
    renderWorkspace();
    updateExcelJobUiFromAnalysis();
    updateAiContextHelpText();
    await loadLatestVerificationProfile();
    navWorkspace.onclick();

    const firstViewerTarget = selected[0] || String(((sessionInputSources[0] || {}).value) || "");
    if (firstViewerTarget) {
        void loadCodeViewer(firstViewerTarget).catch(() => { });
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
        const input_sources = getSelectedInputSources();
        const ai_model_name = enableLiveAi ? (selectedAiModel || (aiModelSelect && aiModelSelect.value) || "") : "";
        const totalRequestedCount = selected_files.length + input_sources.length;

        if (btnAnalyze) {
            btnAnalyze.disabled = true;
            btnAnalyze.textContent = "분석 중...";
        }
        setAnalyzeProgressVisible(true);
        updateAnalyzeProgressUi({
            status: "queued",
            progress: {
                total_files: totalRequestedCount,
                completed_files: 0,
                failed_files: 0,
                percent: 0,
                current_file: "",
                phase: "queued",
            },
            timing: { elapsed_ms: 0, eta_ms: null },
        });

        const response = await fetch("/api/analyze/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mode: "AI 보조",
                selected_files,
                input_sources,
                allow_raw_txt: allowRawTxt,
                enable_ctrlppcheck: enableCtrlppcheck,
                enable_live_ai: enableLiveAi,
                ai_model_name: ai_model_name || undefined,
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
    if (workspaceQuickFilterClear) {
        workspaceQuickFilterClear.addEventListener("click", () => clearRecommendationWorkspaceFilter());
    }
    renderWorkspaceQuickFilter();
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
    if (diffModalBackdrop) {
        diffModalBackdrop.addEventListener("click", closeDiffModal);
    }
    if (diffModalClose) {
        diffModalClose.addEventListener("click", closeDiffModal);
    }
    if (diffModalViewSplit) {
        diffModalViewSplit.addEventListener("click", () => setDiffModalView("split"));
    }
    if (diffModalViewUnified) {
        diffModalViewUnified.addEventListener("click", () => setDiffModalView("unified"));
    }
    if (liveAiToggle) {
        liveAiToggle.addEventListener("change", syncAiContextToggle);
    }
    if (aiModelSelect) {
        aiModelSelect.addEventListener("change", () => {
            selectedAiModel = String(aiModelSelect.value || "");
        });
    }
    if (aiContextToggle) {
        aiContextToggle.addEventListener("change", updateAiContextHelpText);
    }
    if (btnAddExternalFiles && externalFileInput) {
        btnAddExternalFiles.addEventListener("click", () => externalFileInput.click());
        externalFileInput.addEventListener("change", async () => {
            try {
                await stageExternalInputs(externalFileInput.files, "files");
            } catch (err) {
                alert(`외부 파일 추가 실패: ${String((err && err.message) || err || "")}`);
            } finally {
                externalFileInput.value = "";
            }
        });
    }
    if (btnAddExternalFolder && externalFolderInput) {
        btnAddExternalFolder.addEventListener("click", () => externalFolderInput.click());
        externalFolderInput.addEventListener("change", async () => {
            try {
                await stageExternalInputs(externalFolderInput.files, "folder");
            } catch (err) {
                alert(`폴더 선택 실패: ${String((err && err.message) || err || "")}`);
            } finally {
                externalFolderInput.value = "";
            }
        });
    }
    syncAiContextToggle();
    updateExcelJobUiFromAnalysis();
    updateDashboard();
    await loadLatestVerificationProfile();
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

window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && diffModal && !diffModal.classList.contains("hidden")) {
        closeDiffModal();
    }
});
