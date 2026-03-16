import { createAutofixAiController } from "./renderer/autofix-ai.js";
import { createCodeViewerController } from "./renderer/code-viewer.js";
import { createDetailPanelController } from "./renderer/detail-panel.js";
import { createDashboardPanelsController } from "./renderer/dashboard-panels.js";
import { createRulesManageController } from "./renderer/rules-manage.js";
import { createWorkspaceController } from "./renderer/workspace-view.js";
import {
    basenamePath,
    buildFunctionScopes,
    compactUiText,
    countChar,
    escapeHtml,
    fileIdentityKey,
    findScopeForLine,
    inferRuleIdFromReviewedBlock,
    isLikelyFunctionKeyword,
    normalizeInsightToken,
    normalizeP1RuleId,
    normalizeReviewedMessageKey,
    parseReviewedMetaLine,
    parseReviewedSeverity,
    parseReviewedTodoBlocks,
    parseUnifiedDiffForSplit,
    positiveLineOrZero,
    sameFileIdentity,
    scoreSeverityWeight,
    scoreSourceWeight,
    stripDetailEvidence,
    summarizeRuleCluster,
    truncateMiddle,
    truncateUiText,
    violationDisplayFile,
    violationResolvedFile,
} from "./renderer/utils.js";

let analysisData = {
    summary: { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
    violations: { P1: [], P2: [], P3: [] },
    ai_review_statuses: [],
    output_dir: "",
    metrics: {},
    report_jobs: {},
    report_paths: {},
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
const operationsCompare = document.getElementById("operations-compare");
const rulesHealthCompare = document.getElementById("rules-health-compare");
const analysisDiffCompare = document.getElementById("analysis-diff-compare");
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
const aiComparePreview = document.getElementById("ai-compare-preview");
const aiPrimaryActions = document.querySelector(".ai-primary-actions");
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
const excelDownloadToggle = document.getElementById("excel-download-toggle");
const excelDownloadPanel = document.getElementById("excel-download-panel");
const excelDownloadList = document.getElementById("excel-download-list");
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
let excelDownloadsExpanded = false;
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
let latestRulesHealthPayload = null;
let rulesManageOpen = false;
let rulesManageLoading = false;
let rulesManageSaving = false;
let rulesManageRows = [];
let rulesManageDraftById = new Map();
let rulesManageEditorMode = "edit";
let rulesManageEditorRuleId = "";
let rulesManageEditorDraft = null;
let rulesManageStatusMessage = "";
let analysisDiffRunOptions = [];
let selectedAnalysisDiffLatest = "";
let selectedAnalysisDiffPrevious = "";
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

const dom = {
    aiCard,
    aiComparePreview,
    aiMoreActions,
    aiPanelWrap,
    aiPrimaryActions,
    aiReviewToggleBtn,
    aiSummaryList,
    aiText,
    aiTextFull,
    btnAiMore,
    analysisDiffCompare,
    diffModal,
    diffModalAfter,
    diffModalBackdrop,
    diffModalBefore,
    diffModalCandidates,
    diffModalClose,
    diffModalMeta,
    diffModalSplit,
    diffModalSummary,
    diffModalText,
    diffModalTitle,
    diffModalViewSplit,
    diffModalViewUnified,
    codeViewer,
    criticalText,
    dedupeSummary,
    fileList,
    filterMatrix,
    inspectorSelectionMeta,
    operationsCompare,
    priorityRecommendations,
    resultBody,
    resultTableWrap,
    rulesHealthCompare,
    scoreBar,
    scoreText,
    totalText,
    violationDetailPanel,
    violationDetail,
    verificationBadge,
    verificationProfileCard,
    warningText,
    workspaceFilterSummaryText,
    workspaceQuickFilter,
    workspaceQuickFilterClear,
    workspaceQuickFilterText,
    aiCompareButtons,
    aiCompareMeta,
    aiDiffPanel,
    aiDiffText,
    aiValidationPanel,
    aiValidationText,
};

const state = {
    get analysisData() { return analysisData; },
    set analysisData(value) { analysisData = value; },
    get analysisInsights() { return analysisInsights; },
    set analysisInsights(value) { analysisInsights = value; },
    get activeJumpRequestState() { return activeJumpRequestState; },
    set activeJumpRequestState(value) { activeJumpRequestState = value; },
    get activeInspectorTab() { return activeInspectorTab; },
    set activeInspectorTab(value) { activeInspectorTab = value; },
    get activeRecommendationRowId() { return activeRecommendationRowId; },
    set activeRecommendationRowId(value) { activeRecommendationRowId = value; },
    get activeWorkspaceFlashTimer() { return activeWorkspaceFlashTimer; },
    set activeWorkspaceFlashTimer(value) { activeWorkspaceFlashTimer = value; },
    get activeWorkspaceRowId() { return activeWorkspaceRowId; },
    set activeWorkspaceRowId(value) { activeWorkspaceRowId = value; },
    get aiMoreMenuOpen() { return aiMoreMenuOpen; },
    set aiMoreMenuOpen(value) { aiMoreMenuOpen = !!value; },
    get aiReviewExpanded() { return aiReviewExpanded; },
    set aiReviewExpanded(value) { aiReviewExpanded = !!value; },
    get autofixProposalCache() { return autofixProposalCache; },
    get codeViewerFocusTimer() { return codeViewerFocusTimer; },
    set codeViewerFocusTimer(value) { codeViewerFocusTimer = value; },
    get currentHighlightedLine() { return currentHighlightedLine; },
    set currentHighlightedLine(value) { currentHighlightedLine = value; },
    get currentHighlightedLineNear() { return currentHighlightedLineNear; },
    set currentHighlightedLineNear(value) { currentHighlightedLineNear = value; },
    get currentViewerContent() { return currentViewerContent; },
    set currentViewerContent(value) { currentViewerContent = value; },
    get currentViewerFile() { return currentViewerFile; },
    set currentViewerFile(value) { currentViewerFile = value; },
    get currentViewerHeaderLines() { return currentViewerHeaderLines; },
    set currentViewerHeaderLines(value) { currentViewerHeaderLines = value; },
    get currentViewerLines() { return currentViewerLines; },
    set currentViewerLines(value) { currentViewerLines = value; },
    get currentViewerResolvedName() { return currentViewerResolvedName; },
    set currentViewerResolvedName(value) { currentViewerResolvedName = value; },
    get currentViewerSource() { return currentViewerSource; },
    set currentViewerSource(value) { currentViewerSource = value; },
    get filterControls() { return filterControls; },
    get flashedWorkspaceRowId() { return flashedWorkspaceRowId; },
    set flashedWorkspaceRowId(value) { flashedWorkspaceRowId = value; },
    get latestRulesHealthPayload() { return latestRulesHealthPayload; },
    set latestRulesHealthPayload(value) { latestRulesHealthPayload = value; },
    get recommendationWorkspaceFilter() { return recommendationWorkspaceFilter; },
    set recommendationWorkspaceFilter(value) { recommendationWorkspaceFilter = value; },
    get recommendationInsightByRowId() { return recommendationInsightByRowId; },
    set recommendationInsightByRowId(value) { recommendationInsightByRowId = value; },
    get resultTableRenderQueued() { return resultTableRenderQueued; },
    set resultTableRenderQueued(value) { resultTableRenderQueued = !!value; },
    get rulesManageDraftById() { return rulesManageDraftById; },
    set rulesManageDraftById(value) { rulesManageDraftById = value; },
    get rulesManageEditorDraft() { return rulesManageEditorDraft; },
    set rulesManageEditorDraft(value) { rulesManageEditorDraft = value; },
    get rulesManageEditorMode() { return rulesManageEditorMode; },
    set rulesManageEditorMode(value) { rulesManageEditorMode = value; },
    get rulesManageEditorRuleId() { return rulesManageEditorRuleId; },
    set rulesManageEditorRuleId(value) { rulesManageEditorRuleId = value; },
    get rulesManageLoading() { return rulesManageLoading; },
    set rulesManageLoading(value) { rulesManageLoading = value; },
    get rulesManageOpen() { return rulesManageOpen; },
    set rulesManageOpen(value) { rulesManageOpen = value; },
    get rulesManageRows() { return rulesManageRows; },
    set rulesManageRows(value) { rulesManageRows = value; },
    get rulesManageSaving() { return rulesManageSaving; },
    set rulesManageSaving(value) { rulesManageSaving = value; },
    get rulesManageStatusMessage() { return rulesManageStatusMessage; },
    set rulesManageStatusMessage(value) { rulesManageStatusMessage = value; },
    get sessionInputSources() { return sessionInputSources; },
    set sessionInputSources(value) { sessionInputSources = value; },
    get workspaceAnalysisInsights() { return workspaceAnalysisInsights; },
    set workspaceAnalysisInsights(value) { workspaceAnalysisInsights = value; },
    get workspaceFilteredRows() { return workspaceFilteredRows; },
    set workspaceFilteredRows(value) { workspaceFilteredRows = value; },
    get workspaceRecommendationInsightByRowId() { return workspaceRecommendationInsightByRowId; },
    set workspaceRecommendationInsightByRowId(value) { workspaceRecommendationInsightByRowId = value; },
    get workspaceRenderToken() { return workspaceRenderToken; },
    set workspaceRenderToken(value) { workspaceRenderToken = value; },
    get workspaceRowIndex() { return workspaceRowIndex; },
    set workspaceRowIndex(value) { workspaceRowIndex = value; },
    get workspaceSelectionToken() { return workspaceSelectionToken; },
    set workspaceSelectionToken(value) { workspaceSelectionToken = value; },
    get analysisDiffRunOptions() { return analysisDiffRunOptions; },
    set analysisDiffRunOptions(value) { analysisDiffRunOptions = value; },
    get selectedAnalysisDiffLatest() { return selectedAnalysisDiffLatest; },
    set selectedAnalysisDiffLatest(value) { selectedAnalysisDiffLatest = value; },
    get selectedAnalysisDiffPrevious() { return selectedAnalysisDiffPrevious; },
    set selectedAnalysisDiffPrevious(value) { selectedAnalysisDiffPrevious = value; },
};

const caches = {
    functionScopeCacheByFile,
    reviewedTodoCacheByFile,
    viewerContentCache,
};

const virtualState = {
    codeViewerVirtualState,
    resultTableVirtualState,
    get codeViewerWindowRenderQueued() { return codeViewerWindowRenderQueued; },
    set codeViewerWindowRenderQueued(value) { codeViewerWindowRenderQueued = !!value; },
};

const codeViewerController = createCodeViewerController({
    dom,
    state,
    caches,
    virtualState,
    helpers: {
        buildRecommendationWorkspaceFilterText: () => buildRecommendationWorkspaceFilterText(),
        sourceFilterKey: (value) => sourceFilterKey(value),
    },
});

const {
    applyPrecomputedJumpTarget,
    attachCodeViewerVirtualScrollHandler,
    buildCodeViewerHeader,
    buildCodeViewerStatusText,
    cacheFunctionScopesForFile,
    clearCodeViewerHighlight,
    createCodeLineRow,
    createHeaderChip,
    fetchFileContentPayload,
    getCodeViewerLineAreaOffset,
    getFunctionScopeFor,
    getViewerLineHeight,
    highlightCodeViewerLine,
    jumpCodeViewerToViolation,
    loadCodeViewer,
    pendingJumpLineForViolation,
    prepareFunctionScopeCacheForSelectedFiles,
    queueCodeViewerWindowRender,
    renderCodeViewerContent,
    renderCodeViewerWindow,
    resolveFunctionScopeForViolation,
    resolveReviewedJumpLineFromCache,
    revealCodeViewerFocus,
    scrollCodeViewerToLine,
    scrollCodeViewerToMessage,
    setActiveJumpRequestState,
    setCodeViewerText,
    updateCodeViewerHeaderMeta,
} = codeViewerController;

const detailPanelController = createDetailPanelController({
    dom,
    state,
    helpers: {
        severityFilterKey: (value) => severityFilterKey(value),
    },
});

const {
    appendDetailFact: detailAppendDetailFact,
    appendDetailNote: detailAppendDetailNote,
    buildP1DetailBlocks: detailBuildP1DetailBlocks,
    buildP2DetailBlocks: detailBuildP2DetailBlocks,
    buildP2LocalizedMessage: detailBuildP2LocalizedMessage,
    renderDetailDescriptionBlocks: detailRenderDescriptionBlocks,
    renderInspectorSelectionMeta: detailRenderInspectorSelectionMeta,
} = detailPanelController;

const workspaceController = createWorkspaceController({
    dom,
    state,
    caches,
    virtualState,
    helpers: {
        applyPrecomputedJumpTarget,
        buildP2LocalizedMessage: (violation) => detailBuildP2LocalizedMessage(violation),
        jumpCodeViewerToViolation,
        loadCodeViewer,
        navWorkspace: () => navWorkspace.onclick && navWorkspace.onclick(),
        normalizeSeverityKeyword: (value) => normalizeSeverityKeyword(value),
        pendingJumpLineForViolation,
        pickHigherSeverity: (left, right) => pickHigherSeverity(left, right),
        renderExternalInputSources,
        setActiveJumpRequestState: (status, line) => setActiveJumpRequestState(status, line),
        severityFilterKey: (value) => severityFilterKey(value),
        showDetail: (violation, eventName, options = {}) => showDetail(violation, eventName, options),
        sourceFilterKey: (value) => sourceFilterKey(value),
        updateCodeViewerHeaderMeta,
    },
});

const {
    buildRecommendationWorkspaceFilterText: workspaceBuildRecommendationWorkspaceFilterText,
    buildWorkspaceRowIndex: workspaceBuildWorkspaceRowIndex,
    createResultRow: workspaceCreateResultRow,
    findRecommendationInsightForViolation: workspaceFindRecommendationInsightForViolation,
    getFilterState: workspaceGetFilterState,
    getSelectedFiles: workspaceGetSelectedFiles,
    getSelectedInputSources: workspaceGetSelectedInputSources,
    initFilterControls: workspaceInitFilterControls,
    loadFiles: workspaceLoadFiles,
    queueResultTableWindowRender: workspaceQueueResultTableWindowRender,
    renderAnalysisInsights: workspaceRenderAnalysisInsights,
    renderFileList: workspaceRenderFileList,
    renderWorkspace: workspaceRenderWorkspace,
    renderWorkspaceFilterSummary: workspaceRenderWorkspaceFilterSummary,
    renderWorkspaceQuickFilter: workspaceRenderWorkspaceQuickFilter,
    renderWorkspaceWindow: workspaceRenderWorkspaceWindow,
    rowMatchesRecommendationFilter: workspaceRowMatchesRecommendationFilter,
    runWorkspaceSelection: workspaceRunWorkspaceSelection,
} = workspaceController;

const rulesManageController = createRulesManageController({
    state,
    helpers: {
        loadRulesHealth: () => loadRulesHealth(),
        renderRulesHealth: () => renderRulesHealth(latestRulesHealthPayload, ""),
    },
});

const {
    loadRulesList: rulesLoadRulesList,
    renderRulesManagePanel: rulesRenderRulesManagePanel,
    saveRulesManageUpdates: rulesSaveRulesManageUpdates,
} = rulesManageController;

const autofixAiController = createAutofixAiController({
    dom,
    state,
    helpers: {
        appendDetailNote: (container, text, tone = "") => appendDetailNote(container, text, tone),
        buildAfterRowsFromProposal: (proposal) => buildAfterRowsFromProposal(proposal),
        buildIssueContextRows: (violation, radius = 3) => buildIssueContextRows(violation, radius),
        buildIssueContextRowsWithLines: (lines, targetLine, violation, radius = 4, loadError = "", options = {}) =>
            buildIssueContextRowsWithLines(lines, targetLine, violation, radius, loadError, options),
        buildP1DetailBlocks: (violation) => detailBuildP1DetailBlocks(violation),
        buildP2DetailBlocks: (violation) => detailBuildP2DetailBlocks(violation),
        buildReviewContextRows: (aiMatch) => buildReviewContextRows(aiMatch),
        compactUiText: (value, maxLength = 120) => compactUiText(value, maxLength),
        createComparePreviewColumn: (title, rows, kindClass = "") => createComparePreviewColumn(title, rows, kindClass),
        describeAiUnavailable: (violation, eventName) => describeAiUnavailable(violation, eventName),
        extractReviewCodeBlock: (reviewText) => extractReviewCodeBlock(reviewText),
        fetchFileContentPayload: (fileName, options = {}) => fetchFileContentPayload(fileName, options),
        findAiMatchForViolation: (violation, eventName) => findAiMatchForViolation(violation, eventName),
        getAiRequestOptions: () => ({
            enableLiveAi: !!(liveAiToggle && liveAiToggle.checked),
            aiModelName: selectedAiModel || (aiModelSelect && aiModelSelect.value) || "",
            aiWithContext: !!(aiContextToggle && aiContextToggle.checked),
        }),
        isCtrlppEnabled: () => !!(ctrlppToggle && ctrlppToggle.checked),
        jumpFailureMessage: (result) => jumpFailureMessage(result),
        isMultiAggregationRule: (ruleId) => isMultiAggregationRule(ruleId),
        isPlaceholderLikeReviewCode: (text) => isPlaceholderLikeReviewCode(text),
        loadCodeViewer: (fileName, options = {}) => loadCodeViewer(fileName, options),
        positiveLineOrZero: (value) => positiveLineOrZero(value),
        renderDetailDescriptionBlocks: (container, blocks) => detailRenderDescriptionBlocks(container, blocks),
        renderInspectorSelectionMeta: (violation, options = {}) => detailRenderInspectorSelectionMeta(violation, options),
        resetInspectorTabsForViolation: (options = {}) => resetInspectorTabsForViolation(options),
        resolveDiffAnchorLine: (sourceLines, violation, aiMatch, fileName = "") => resolveDiffAnchorLine(sourceLines, violation, aiMatch, fileName),
        reviewHasGroupedExample: (ruleId, reviewText) => reviewHasGroupedExample(ruleId, reviewText),
        sameFileIdentity: (left, right) => sameFileIdentity(left, right),
        setAutofixValidationPanel: (text, options = {}) => setAutofixValidationPanel(text, options),
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        sourceFilterKey: (value) => sourceFilterKey(value),
        upsertAiReview: (reviewItem) => upsertAiReview(reviewItem),
        upsertAiReviewStatus: (statusItem) => upsertAiReviewStatus(statusItem),
        violationDisplayFile: (primary, fallback = "") => violationDisplayFile(primary, fallback),
        violationResolvedFile: (result, fallback = "") => violationResolvedFile(result, fallback),
    },
});

const {
    clearAiComparePreview: autofixClearAiComparePreview,
    closeDiffModal: autofixCloseDiffModal,
    hideAiEmptyState: autofixHideAiEmptyState,
    openDiffModal: autofixOpenDiffModal,
    renderAiEmptyState: autofixRenderAiEmptyState,
    setAutofixDiffPanel: autofixSetAutofixDiffPanel,
    setAiActionHint: autofixSetAiActionHint,
    setDiffModalView: autofixSetDiffModalView,
    setAiReviewText: autofixSetAiReviewText,
    setAiStatusInline: autofixSetAiStatusInline,
    showDetail: autofixShowDetail,
    syncAiMoreMenuUi: autofixSyncAiMoreMenuUi,
} = autofixAiController;

function closeDiffModal() {
    return autofixCloseDiffModal();
}

function openDiffModal(bundle, violation, aiMatch, eventName = "Global", aiKey = "", onSelectProposal = null) {
    return autofixOpenDiffModal(bundle, violation, aiMatch, eventName, aiKey, onSelectProposal);
}

function setAutofixDiffPanel(text) {
    return autofixSetAutofixDiffPanel(text);
}

function setDiffModalView(view) {
    return autofixSetDiffModalView(view);
}

const dashboardPanelsController = createDashboardPanelsController({
    dom,
    state,
    helpers: {
        loadRulesList: (force = false) => rulesLoadRulesList(force),
        renderAnalysisInsights: () => workspaceRenderAnalysisInsights(),
        renderRulesManagePanel: (host) => rulesRenderRulesManagePanel(host),
    },
});

const {
    loadAnalysisDiffRuns,
    loadLatestAnalysisDiff,
    loadLatestOperationalResults,
    loadLatestVerificationProfile,
    loadRulesHealth,
    loadSelectedAnalysisDiff,
    renderAnalysisDiffCompare,
    renderOperationsCompare,
    renderRulesHealth,
    updateDashboard,
    updateVerificationBadge,
    updateVerificationProfileCard,
} = dashboardPanelsController;

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
            aiContextHelp.textContent = "";
            aiContextHelp.title = "Live AI is disabled, so MCP context is not available.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }
        if (!withContext) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "Turn on AI context to use MCP-backed context with Live AI.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }

        const timings = (analysisData && analysisData.metrics && analysisData.metrics.timings_ms) || {};
        const mcpMs = Number(timings.mcp_context);
        if (Number.isFinite(mcpMs) && mcpMs > 0) {
            aiContextHelp.classList.remove("is-hidden");
            aiContextHelp.textContent = `MCP ${Math.round(mcpMs)}ms`;
            aiContextHelp.title = `MCP ?얜챶???遺욧퍕????뺣즲??됰뮸??덈뼄 (${Math.round(mcpMs)}ms). ??쎈솭 ???癒?짗??곗쨮 ??몄셽??몃빍??`;
        } else {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "?브쑴苑???MCP ?얜챶????遺욧퍕??몃빍?? MCP ??뺤쒔揶쎛 ??얘탢????쎈솭??롢늺 ?癒?짗??곗쨮 ??몄셽??몃빍??";
            aiContextHelp.classList.add("is-hidden");
        }
    }
}

function renderExternalInputSources() {
    if (externalInputSummary) {
        externalInputSummary.textContent = sessionInputSources.length
            ? `Session inputs ${sessionInputSources.length}`
            : "No session inputs";
    }
    if (!externalInputList) return;
    externalInputList.replaceChildren();
    sessionInputSources.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = "external-input-chip";
        const label = document.createElement("span");
        const itemTypeLabel = item.type === "folder_path" ? "Folder" : "File";
        label.textContent = itemTypeLabel + " - " + (item.label || basenamePath(item.value));
        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.textContent = "x";
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
    aiModelSelect.innerHTML = '<option value="">疫꿸퀡??筌뤴뫀??/option>';
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
            const errorText = String(payload.error || "??쇳뒄??Ollama 筌뤴뫀???筌≪뼚? 筌륁궢六??щ빍??");
            aiContextHelp.textContent = "筌뤴뫀???怨밴묶: fallback";
            aiContextHelp.title = errorText + " 疫꿸퀡??筌뤴뫀??fallback???????몃빍??";
        }
    } catch (err) {
        aiModelCatalogLoaded = false;
        aiModelSelect.disabled = true;
        if (aiContextHelp && liveAiToggle && liveAiToggle.checked) {
            const message = String((err && err.message) || err || "");
            aiContextHelp.textContent = "筌뤴뫀???怨밴묶: 鈺곌퀬????쎈솭";
            aiContextHelp.title = "筌뤴뫀??筌뤴뫖以?鈺곌퀬????쎈솭: " + message;
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
        throw new Error(payload.error || ("Failed to stage external inputs (" + response.status + ")"));
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

function renderAiEmptyState(title, detail, diagnostic = null) {
    return autofixRenderAiEmptyState(title, detail, diagnostic);
}

function hideAiEmptyState() {
    return autofixHideAiEmptyState();
}

function syncAiMoreMenuUi() {
    return autofixSyncAiMoreMenuUi();
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

function ensureAiActionHintNode() {
    let node = document.getElementById("ai-action-hint");
    if (!node && aiPrimaryActions && aiCard) {
        node = document.createElement("div");
        node.id = "ai-action-hint";
        node.className = "ai-action-hint";
        aiPrimaryActions.insertAdjacentElement("afterend", node);
    }
    return node;
}

function setAiStatusInline(message, color = "") {
    return autofixSetAiStatusInline(message, color);
}

function setAiActionHint(message, tone = "") {
    return autofixSetAiActionHint(message, tone);
}

function clearAiComparePreview() {
    return autofixClearAiComparePreview();
}

function extractReviewCodeBlock(reviewText) {
    const raw = String(reviewText || "");
    const match = raw.match(/```(?:[\w#+.-]+)?\s*([\s\S]*?)```/);
    if (match && String(match[1] || "").trim()) {
        return String(match[1] || "").trim();
    }
    return "";
}

function buildIssueContextRows(violation, radius = 3) {
    const targetLine = positiveLineOrZero((violation && violation.line) || 0);
    const lines = Array.isArray(currentViewerLines) ? currentViewerLines : [];
    if (!targetLine || !lines.length) {
        const fallback = compactUiText(String((violation && violation.message) || "").trim(), 220) || "?醫뤾문 ??곷뭼???癒?궚 ?꾨뗀諭?筌띘살뵭???븍뜄???? 筌륁궢六??щ빍??";
        return [{ lineNo: positiveLineOrZero(targetLine), text: fallback, kind: "change-old" }];
    }
    const start = Math.max(1, targetLine - Math.max(1, radius));
    const end = Math.min(lines.length, targetLine + Math.max(1, radius));
    const rows = [];
    for (let lineNo = start; lineNo <= end; lineNo += 1) {
        rows.push({
            lineNo,
            text: String(lines[lineNo - 1] || ""),
            kind: lineNo === targetLine ? "change-old" : "context",
        });
    }
    return rows;
}

function estimateLineByMessage(lines, message) {
    const safeLines = Array.isArray(lines) ? lines : [];
    const tokenSource = String(message || "").toLowerCase().replace(/[^a-z0-9_]+/g, " ").trim();
    if (!safeLines.length || !tokenSource) return 0;
    const tokens = tokenSource.split(/\s+/).filter((item) => item.length >= 4).slice(0, 3);
    if (!tokens.length) return 0;
    for (let idx = 0; idx < safeLines.length; idx += 1) {
        const line = String(safeLines[idx] || "").toLowerCase();
        if (tokens.some((token) => line.includes(token))) return idx + 1;
    }
    return 0;
}

function buildIssueContextRowsWithLines(lines, targetLine, violation, radius = 4, loadError = "", options = {}) {
    const safeLines = Array.isArray(lines) ? lines : [];
    const allowMessageEstimate = !(options && options.disableMessageEstimate);
    const preferredLine = positiveLineOrZero(targetLine)
        || (allowMessageEstimate ? estimateLineByMessage(safeLines, violation && violation.message) : 0);
    if (!safeLines.length) {
        const fallback = loadError
            ? `?癒?궚 source 嚥≪뮆諭???쎈솭: ${loadError}`
            : "?癒?궚 source ?꾨뗀諭띄몴??븍뜄???? 筌륁궢六??щ빍??";
        return [{ lineNo: 0, text: fallback, kind: "placeholder" }];
    }
    if (preferredLine <= 0) {
        return [{ lineNo: 0, text: "line ?類ｋ궖??筌≪뼚? 筌륁궢鍮??袁⑷퍥 筌띘살뵭 ?????遺용튋 ??쑨?놂쭕???볥궗??몃빍??", kind: "placeholder" }];
    }
    const start = Math.max(1, preferredLine - Math.max(1, radius));
    const end = Math.min(safeLines.length, preferredLine + Math.max(1, radius));
    const rows = [];
    for (let lineNo = start; lineNo <= end; lineNo += 1) {
        rows.push({
            lineNo,
            text: String(safeLines[lineNo - 1] || ""),
            kind: lineNo === preferredLine ? "change-old" : "context",
        });
    }
    return rows;
}

function isPlaceholderLikeReviewCode(text) {
    const raw = String(text || "").trim();
    if (!raw) return true;
    const lowered = raw.toLowerCase();
    const lineCount = raw.split(/\r?\n/).length;
    const placeholderPatterns = [
        /todo/i,
        /placeholder/i,
        /reviewed/i,
        /generated/i,
        /no\s+details?/i,
        /minimal/,
    ];
    const looksPlaceholder = placeholderPatterns.some((re) => re.test(lowered));
    const hasCodeShape = /[{}();=]/.test(raw) || /\b(if|for|while|return|setvalue|getvalue|dpset|dpget)\b/i.test(raw);
    return looksPlaceholder && (!hasCodeShape || lineCount <= 3);
}

function anchorTokensForViolation(violation, aiMatch) {
    const ruleId = String(((violation && violation.rule_id) || (aiMatch && aiMatch.parent_rule_id) || "").trim()).toUpperCase();
    const message = String((violation && violation.message) || "").toLowerCase();
    const tokenSet = new Set();
    if (ruleId.includes("SETMULTIVALUE")) {
        tokenSet.add("setmultivalue");
        tokenSet.add("setvalue");
    }
    if (ruleId.includes("GETMULTIVALUE")) {
        tokenSet.add("getmultivalue");
        tokenSet.add("getvalue");
    }
    if (ruleId.includes("DPSET")) {
        tokenSet.add("dpset");
        tokenSet.add("dpsettimed");
    }
    if (ruleId.includes("DPGET")) {
        tokenSet.add("dpget");
    }
    if (message.includes("setvalue")) tokenSet.add("setvalue");
    if (message.includes("getvalue")) tokenSet.add("getvalue");
    if (message.includes("dpset")) tokenSet.add("dpset");
    if (message.includes("dpget")) tokenSet.add("dpget");
    return Array.from(tokenSet);
}

function findAnchorLineByTokens(lines, tokens) {
    const safeLines = Array.isArray(lines) ? lines : [];
    const safeTokens = Array.isArray(tokens) ? tokens.filter(Boolean).map((item) => String(item).toLowerCase()) : [];
    if (!safeLines.length || !safeTokens.length) return 0;
    for (let i = 0; i < safeLines.length; i += 1) {
        const line = String(safeLines[i] || "").toLowerCase();
        if (!line.trim() || line.trim().startsWith("//")) continue;
        if (safeTokens.some((token) => line.includes(token))) {
            return i + 1;
        }
    }
    return 0;
}

function resolveDiffAnchorLine(sourceLines, violation, aiMatch, fileName = "") {
    const directLine = positiveLineOrZero((violation && violation.line) || 0);
    if (directLine > 0) return directLine;
    const parentLine = positiveLineOrZero((aiMatch && aiMatch.parent_line) || 0);
    if (parentLine > 0) return parentLine;
    const byMessage = estimateLineByMessage(sourceLines, violation && violation.message);
    if (byMessage > 0) return byMessage;
    const tokenLine = findAnchorLineByTokens(sourceLines, anchorTokensForViolation(violation, aiMatch));
    if (tokenLine > 0) {
        const scope = getFunctionScopeFor(fileName, tokenLine);
        if (scope && positiveLineOrZero(scope.start) > 0) {
            return positiveLineOrZero(scope.start);
        }
        return tokenLine;
    }
    return 0;
}

function buildReviewContextRows(aiMatch) {
    const reviewText = String((aiMatch && aiMatch.review) || "").trim();
    const codeBlock = extractReviewCodeBlock(reviewText);
    const preferredText = codeBlock || reviewText || "P3 揶쏆뮇苑????용뮞?紐? 筌≪뼚? 筌륁궢六??щ빍??";
    const lines = preferredText.split(/\r?\n/);
    return lines.map((line, index) => ({
        lineNo: codeBlock ? index + 1 : 0,
        text: String(line || ""),
        kind: codeBlock ? "change-new" : index === 0 ? "change-new" : "context",
    }));
}

function buildAfterRowsFromProposal(proposal) {
    const diffText = String((proposal && proposal.unified_diff) || "").trim();
    if (!diffText) return [];
    const parsed = parseUnifiedDiffForSplit(diffText);
    if (Array.isArray(parsed.afterRows) && parsed.afterRows.length) {
        return parsed.afterRows;
    }
    return [];
}

function createComparePreviewColumn(title, rows, kindClass = "") {
    const column = document.createElement("div");
    column.className = `ai-compare-preview-column ${kindClass}`.trim();
    const heading = document.createElement("strong");
    heading.className = "ai-compare-preview-title";
    heading.textContent = title;
    column.appendChild(heading);
    const body = document.createElement("div");
    body.className = "ai-compare-preview-body";
    const safeRows = Array.isArray(rows) && rows.length
        ? rows
        : [{ lineNo: 0, text: "??쑨???類ｋ궖??餓Β??쑵釉?쭪? 筌륁궢六??щ빍??", kind: "placeholder" }];
    safeRows.slice(0, 6).forEach((row) => {
        body.appendChild(createDiffPaneLine(row.lineNo, row.text, row.kind));
    });
    column.appendChild(body);
    return column;
}

function setAutofixValidationPanel(text, { ok = true } = {}) {
    if (!aiValidationPanel || !aiValidationText) return;
    const msg = String(text || "");
    aiValidationText.textContent = msg;
    aiValidationPanel.style.display = msg ? "block" : "none";
    aiValidationText.classList.toggle("ai-validation-text-ok", !!ok);
    aiValidationText.classList.toggle("ai-validation-text-error", !ok);
}

function isMultiAggregationRule(ruleId) {
    const rule = String(ruleId || "").trim().toUpperCase();
    return rule === "PERF-SETMULTIVALUE-ADOPT-01"
        || rule === "PERF-GETMULTIVALUE-ADOPT-01"
        || rule === "PERF-DPSET-BATCH-01"
        || rule === "PERF-DPGET-BATCH-01";
}

function extractReviewCodeBlocks(reviewText) {
    const raw = String(reviewText || "");
    const blocks = [];
    const regex = /```(?:[\w#+.-]+)?\s*([\s\S]*?)```/gi;
    let match;
    while ((match = regex.exec(raw)) !== null) {
        const block = String((match && match[1]) || "").trim();
        if (block) blocks.push(block);
    }
    return blocks;
}

function reviewHasGroupedExample(ruleId, reviewText) {
    const rule = String(ruleId || "").trim().toUpperCase();
    const blocks = extractReviewCodeBlocks(reviewText).map((item) => item.toLowerCase());
    if (!rule || !blocks.length) return false;
    if (rule === "PERF-SETMULTIVALUE-ADOPT-01") return blocks.some((block) => block.includes("setmultivalue("));
    if (rule === "PERF-GETMULTIVALUE-ADOPT-01") return blocks.some((block) => block.includes("getmultivalue("));
    if (rule === "PERF-DPSET-BATCH-01") {
        return blocks.some((block) => /dpset\s*\(([\s\S]*?)\);/i.test(block) && ((block.match(/,/g) || []).length >= 3));
    }
    if (rule === "PERF-DPGET-BATCH-01") {
        return blocks.some((block) => /dpget\s*\(([\s\S]*?)\);/i.test(block) && ((block.match(/,/g) || []).length >= 3));
    }
    return false;
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

function isReviewOnlyLikeViolation(violation) {
    const source = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const issueId = String((violation && violation.issue_id) || "").trim().toUpperCase();
    const lineNo = positiveLineOrZero((violation && violation.line) || 0);
    return source === "P1" && (lineNo <= 0 || issueId.startsWith("REVIEW-ONLY-"));
}

function findAiLinkedItemForViolation(items, violation, eventName) {
    const collection = Array.isArray(items) ? items : [];
    const exact = collection.find((item) => aiStatusMatchesViolation(item, violation, eventName)) || null;
    if (exact) return exact;
    if (!isReviewOnlyLikeViolation(violation)) return null;

    const selectedFile = violationResolvedFile(violation);
    const selectedSource = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const selectedRule = String((violation && violation.rule_id) || "").trim();
    const selectedEvent = String(eventName || "Global");
    const selectedLine = positiveLineOrZero((violation && violation.line) || 0);
    if (!selectedRule) return null;

    const candidates = collection.filter((item) => {
        if (!item || typeof item !== "object") return false;
        const parentFile = violationResolvedFile(item);
        if (selectedFile && parentFile && !sameFileIdentity(selectedFile, parentFile)) return false;
        const parentSource = String(item.parent_source || "").trim().toUpperCase();
        if (selectedSource && parentSource && selectedSource !== parentSource) return false;
        const parentRule = String(item.parent_rule_id || "").trim();
        if (!parentRule || parentRule !== selectedRule) return false;
        const parentEvent = String(item.event || "Global");
        if (selectedEvent && parentEvent && selectedEvent !== parentEvent) return false;
        return true;
    });
    if (!candidates.length) return null;
    if (candidates.length === 1) return candidates[0];

    return candidates
        .map((item, idx) => ({ item, idx }))
        .sort((a, b) => {
            const aLine = positiveLineOrZero(a.item.parent_line || 0);
            const bLine = positiveLineOrZero(b.item.parent_line || 0);
            const aHasLine = aLine > 0 ? 1 : 0;
            const bHasLine = bLine > 0 ? 1 : 0;
            if (aHasLine !== bHasLine) return bHasLine - aHasLine;
            const aDistance = selectedLine > 0 && aLine > 0 ? Math.abs(aLine - selectedLine) : 999999;
            const bDistance = selectedLine > 0 && bLine > 0 ? Math.abs(bLine - selectedLine) : 999999;
            if (aDistance !== bDistance) return aDistance - bDistance;
            return b.idx - a.idx;
        })[0].item;
}

function findAiMatchForViolation(violation, eventName) {
    return findAiLinkedItemForViolation((analysisData.violations && analysisData.violations.P3) || [], violation, eventName);
}

function findAiStatusForViolation(violation, eventName) {
    return findAiLinkedItemForViolation(analysisData.ai_review_statuses || [], violation, eventName);
}

function aiStatusDisplayLabel(status) {
    const key = String(status || "").trim().toLowerCase();
    if (key === "generated") return "Generated";
    if (key === "failed") return "??밴쉐 ??쎈솭";
    if (key === "skipped") return "??밴쉐 ??뽰뇚";
    return key || "??곸벉";
}

function aiReasonDisplayMeta(reason) {
    const key = String(reason || "").trim();
    if (key === "generated") {
        return {
            title: "AI review was generated for this finding.",
            detail: "A matching P3 review is available for the selected issue.",
            label: "Generated",
        };
    }
    if (key === "mock_generated") {
        return {
            title: "A mock AI review was generated.",
            detail: "Live AI was not used, but a mock review is available for preview.",
            label: "Mock generated",
        };
    }
    if (key === "timeout") {
        return {
            title: "AI review generation timed out.",
            detail: "Live AI did not respond in time, so no P3 review was attached.",
            label: "Timed out",
        };
    }
    if (key === "response_parse_failed") {
        return {
            title: "AI review response could not be parsed.",
            detail: "The AI returned a response, but it was not in a usable format.",
            label: "Parse failed",
        };
    }
    if (key === "fail_soft_skip") {
        return {
            title: "AI review was skipped in fail-soft mode.",
            detail: "Live AI was unavailable, so the app continued without attaching a P3 review.",
            label: "fail-soft skip",
        };
    }
    if (key === "empty_response") {
        return {
            title: "AI returned an empty response.",
            detail: "No review content was returned for this finding.",
            label: "Empty response",
        };
    }
    if (key === "severity_filtered") {
        return {
            title: "P3 generation was skipped by severity filter.",
            detail: "This issue did not meet the threshold for generating a P3 review.",
            label: "Severity filtered",
        };
    }
    if (key === "priority_limited") {
        return {
            title: "P3 generation was skipped by priority limits.",
            detail: "Another nearby parent review took precedence over this issue.",
            label: "Priority limited",
        };
    }
    return {
        title: "No AI review metadata is available.",
        detail: "A matching P3 status could not be found for this issue.",
        label: key || "Unknown",
    };
}

function collectNearbyP3Candidates(violation, eventName) {
    const source = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const selectedRule = String((violation && violation.rule_id) || "").trim();
    const selectedLine = positiveLineOrZero((violation && violation.line) || 0);
    const selectedFile = violationResolvedFile(violation);
    const selectedEvent = String(eventName || "Global");
    const candidates = Array.isArray(analysisData.violations && analysisData.violations.P3) ? analysisData.violations.P3 : [];
    return candidates.filter((item) => {
        if (!item || typeof item !== "object") return false;
        const parentFile = violationResolvedFile(item);
        if (selectedFile && parentFile && !sameFileIdentity(selectedFile, parentFile)) return false;
        const parentSource = String(item.parent_source || "").trim().toUpperCase();
        if (source && parentSource && source !== parentSource) return false;
        const parentEvent = String(item.event || "Global");
        if (selectedEvent && parentEvent && selectedEvent !== parentEvent) return false;
        return true;
    }).sort((a, b) => {
        const aRule = String(a.parent_rule_id || "").trim();
        const bRule = String(b.parent_rule_id || "").trim();
        const aLine = positiveLineOrZero(a.parent_line || 0);
        const bLine = positiveLineOrZero(b.parent_line || 0);
        const aRuleMatch = aRule && selectedRule && aRule === selectedRule ? 0 : 1;
        const bRuleMatch = bRule && selectedRule && bRule === selectedRule ? 0 : 1;
        const aDistance = selectedLine > 0 && aLine > 0 ? Math.abs(aLine - selectedLine) : 999999;
        const bDistance = selectedLine > 0 && bLine > 0 ? Math.abs(bLine - selectedLine) : 999999;
        return aRuleMatch - bRuleMatch || aDistance - bDistance;
    });
}

function buildAiUnavailableDiagnostic(violation, eventName) {
    const aiStatus = findAiStatusForViolation(violation, eventName);
    const nearbyCandidates = collectNearbyP3Candidates(violation, eventName);
    const nearby = nearbyCandidates[0] || null;
    const sourceKey = sourceFilterKey(violation && violation.priority_origin);
    const status = String((aiStatus && aiStatus.status) || "").trim();
    const reason = String((aiStatus && aiStatus.reason) || "").trim();
    const reasonMeta = aiReasonDisplayMeta(reason);
    let classification = "not_found";
    let classificationLabel = "Not found";
    let matchLabel = "?怨뚭퍙??P3 ??곸벉";
    let matchHint = "";

    if (aiStatus) {
        classification = status || "not_found";
        classificationLabel = aiStatusDisplayLabel(status);
        if (status === "generated" && nearby) {
            classification = "not_matched";
            classificationLabel = "筌띲끉臾???쎈솭";
            matchLabel = "P3 ??밴쉐?? exact parent 筌띲끉臾???쎈솭";
            matchHint = `?袁⑤궖 P3 parent_rule_id=${String(nearby.parent_rule_id || "-")}, selected rule_id=${String((violation && violation.rule_id) || "-")}`;
        } else if (status === "generated") {
            matchLabel = "status??generated筌왖筌?exact P3 ??곸벉";
        } else {
            matchLabel = "P3 matched";
        }
    } else if (nearby) {
        classification = "not_matched";
        classificationLabel = "筌띲끉臾???쎈솭";
        matchLabel = "Nearby P3 found for another parent";
        matchHint = `?袁⑤궖 P3 parent_rule_id=${String(nearby.parent_rule_id || "-")}, selected rule_id=${String((violation && violation.rule_id) || "-")}`;
    } else {
        classification = "not_found";
        classificationLabel = "Not found";
        matchLabel = sourceKey === "p2" ? "?怨뚭퍙??P3 ?癒?뮉 status ??곸벉" : "P3/status 筌뤴뫀紐???곸벉";
    }

    return {
        classification,
        classification_label: classificationLabel,
        status,
        status_label: aiStatusDisplayLabel(status),
        reason,
        reason_label: reasonMeta.label,
        title: reasonMeta.title,
        detail: reasonMeta.detail,
        selected_source: String((violation && violation.priority_origin) || "P1"),
        selected_issue_id: String((violation && violation.issue_id) || "-"),
        selected_rule_id: String((violation && violation.rule_id) || "-"),
        selected_line: positiveLineOrZero((violation && violation.line) || 0) || "-",
        parent_issue_id: String(((aiStatus || nearby || {}).parent_issue_id) || "-"),
        parent_rule_id: String(((aiStatus || nearby || {}).parent_rule_id) || "-"),
        parent_line: positiveLineOrZero(((aiStatus || nearby || {}).parent_line) || 0) || "-",
        selected_cap: positiveLineOrZero(((aiStatus || {}).selected_cap) || 0) || 0,
        selected_rank: positiveLineOrZero(((aiStatus || {}).selected_rank) || 0) || 0,
        match_label: matchLabel,
        match_hint: matchHint,
    };
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
    const diagnostic = buildAiUnavailableDiagnostic(violation, eventName);
    if (!(liveAiToggle && liveAiToggle.checked)) {
        return {
            title: "AI review is currently disabled.",
            detail: "Enable Live AI to request a P3 review for this finding.",
            diagnostic,
        };
    }
    return {
        title: diagnostic.title,
        detail: diagnostic.detail,
        diagnostic,
    };
}

function setAiReviewText(reviewText) {
    return autofixSetAiReviewText(reviewText);
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

function excelFilesFromAnalysis() {
    const reportPaths = (analysisData && analysisData.report_paths) || {};
    return Array.isArray(reportPaths.excel) ? reportPaths.excel.filter(Boolean).map((name) => String(name)) : [];
}

function isExcelSupportAvailable() {
    const metrics = (analysisData && analysisData.metrics) || {};
    const optionalDependencies = (metrics && metrics.optional_dependencies) || {};
    const openpyxl = (optionalDependencies && optionalDependencies.openpyxl) || {};
    return openpyxl.available !== false;
}

function makeExcelDownloadUrl(name) {
    const outputDir = String((analysisData && analysisData.output_dir) || "").trim();
    const fileName = String(name || "").trim();
    if (!outputDir || !fileName) return "";
    const query = new URLSearchParams();
    query.set("output_dir", outputDir);
    query.set("name", fileName);
    return `/api/report/excel/download?${query.toString()}`;
}

function triggerExcelDownload(name) {
    const url = makeExcelDownloadUrl(name);
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    link.download = String(name || "report.xlsx");
    document.body.appendChild(link);
    link.click();
    link.remove();
}

function shortenExcelDownloadName(name, maxLength = 48) {
    const raw = String(name || "report.xlsx").trim();
    const compact = raw.replace(/^CodeReview_Submission_/, "");
    if (compact.length <= maxLength) {
        return compact;
    }
    const head = Math.max(18, Math.floor((maxLength - 1) / 2));
    const tail = Math.max(12, maxLength - head - 1);
    return `${compact.slice(0, head)}...${compact.slice(-tail)}`;
}

function setExcelDownloadsExpanded(expanded) {
    excelDownloadsExpanded = !!expanded;
    if (excelDownloadToggle) {
        excelDownloadToggle.setAttribute("aria-expanded", excelDownloadsExpanded ? "true" : "false");
    }
    if (excelDownloadPanel) {
        const hasFiles = !!excelFilesFromAnalysis().length;
        excelDownloadPanel.hidden = !hasFiles || !excelDownloadsExpanded;
    }
}

function renderExcelDownloadList() {
    if (!excelDownloadList) return;
    excelDownloadList.innerHTML = "";
    if (!((analysisData && analysisData.output_dir) || "").trim()) {
        if (excelDownloadToggle) {
            excelDownloadToggle.hidden = true;
        }
        setExcelDownloadsExpanded(false);
        return;
    }
    const files = excelFilesFromAnalysis();
    if (!files.length) {
        if (excelDownloadToggle) {
            excelDownloadToggle.hidden = true;
        }
        setExcelDownloadsExpanded(false);
        return;
    }
    if (excelDownloadToggle) {
        excelDownloadToggle.hidden = false;
        excelDownloadToggle.textContent = `Excel ${files.length}`;
        excelDownloadToggle.title = `${files.length} Excel files ready to download`;
    }
    files.forEach((name) => {
        const item = document.createElement("div");
        item.className = "excel-download-item";
        item.title = String(name || "");
        const label = document.createElement("span");
        label.className = "excel-download-name";
        label.textContent = shortenExcelDownloadName(name);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "excel-download-button";
        button.textContent = "Download";
        button.title = String(name || "");
        button.addEventListener("click", () => triggerExcelDownload(name));
        item.appendChild(label);
        item.appendChild(button);
        excelDownloadList.appendChild(item);
    });
    setExcelDownloadsExpanded(excelDownloadsExpanded);
}

function updateExcelJobUiFromAnalysis() {
    const excel = excelJobsFromAnalysis();
    const excelFiles = excelFilesFromAnalysis();
    const excelAvailable = isExcelSupportAvailable();
    const pending = Number.parseInt(excel.pending_count || 0, 10) || 0;
    const running = Number.parseInt(excel.running_count || 0, 10) || 0;
    const completed = Number.parseInt(excel.completed_count || 0, 10) || 0;
    const failed = Number.parseInt(excel.failed_count || 0, 10) || 0;
    const total = (Array.isArray(excel.jobs) ? excel.jobs.length : 0);
    const hasSession = !!(analysisData && analysisData.output_dir);
    if (flushExcelBtn) {
        flushExcelBtn.disabled = !hasSession || !excelAvailable || (total === 0 && excelFiles.length === 0);
        flushExcelBtn.textContent = (pending > 0 || running > 0) ? "Excel 野껉퀗????밴쉐" : "Excel 野껉퀗????밴쉐";
    }
    if (!hasSession) {
        setExcelJobStatus("");
        renderExcelDownloadList();
        return;
    }
    if (!excelAvailable) {
        setExcelJobStatus("openpyxl ?袁⑹뒄", "#ffcdd2");
        renderExcelDownloadList();
        return;
    }
    if (total === 0 && excelFiles.length === 0) {
        setExcelJobStatus("", "");
        renderExcelDownloadList();
        return;
    }
    if (excelFiles.length > 0 && pending === 0 && running === 0 && failed === 0) {
        setExcelJobStatus(`Excel ${excelFiles.length} files ready`, "#c8e6c9");
        renderExcelDownloadList();
        return;
    }
    const statusParts = [`Excel ${completed}/${total}`];
    if (pending > 0) statusParts.push(`??疫?${pending}`);
    if (running > 0) statusParts.push(`??쎈뻬 ${running}`);
    if (failed > 0) statusParts.push(`??쎈솭 ${failed}`);
    const color = failed > 0 ? "#ffcdd2" : (pending > 0 || running > 0) ? "#fff59d" : "#c8e6c9";
    setExcelJobStatus(statusParts.join(" | "), color);
    renderExcelDownloadList();
}

function jumpFailureMessage(jumpResult) {
    if (!jumpResult || jumpResult.ok) return "";
    const reason = String(jumpResult.reason || "");
    if (reason === "reviewed-anchor-miss") {
        return "REVIEWED TODO ?됰뗀以????묽??筌≪뼚? 筌륁궢鍮??????꾨뗀李???袁⑺뒄嚥???猷??? 筌륁궢六??щ빍??";
    }
    if (reason === "source-line-miss") {
        return "?癒?궚 source 疫꿸퀣? 餓?甕곕뜇?뉒몴?筌≪뼚? 筌륁궢鍮???륁뵠??깆뵠????猷????묐뻬??? 筌륁궢六??щ빍??";
    }
    if (reason === "file-load-miss") {
        return "???????뵬????쇰뻻 ?븍뜄???? 筌륁궢鍮??꾨뗀諭띌뀎怨쀫선 ??猷???袁⑥┷??? 筌륁궢六??щ빍??";
    }
    if (reason === "no-locatable-position") {
        return "??????? ?袁⑺뒄 ?類ｋ궖(line/file)揶쎛 ??곷선 餓???猷????묐뻬??? ??녿뮸??덈뼄.";
    }
    if (reason === "load-source-failed") {
        return "P2???癒?궚 .ctl 疫꿸퀣?????source 嚥≪뮆諭???쎈솭 ??餓???猷??餓λ쵎???됰뮸??덈뼄.";
    }
    if (reason === "source-not-found") {
        return "????.ctl source ???뵬??筌≪뼚? 筌륁궢鍮?餓???猷????묐뻬??????곷뮸??덈뼄.";
    }
    if (reason === "invalid-target-file") {
        return "P2 ????????????뵬??.ctl ?類ㅻ뻼???袁⑤빍??곴퐣 ?袁⑺뒄 ??猷????묐뻬??? ??녿릭??щ빍??";
    }
    if (reason === "cross-file") {
        return "?袁⑹삺 ??뽯뻻 ???뵬???醫뤾문????곷뭼 ???뵬???????袁⑺뒄 ??猷????묐뻬??? ??녿릭??щ빍??";
    }
    if (reason === "load-failed") {
        return "?醫뤾문????곷뭼 ???뵬???븍뜄???? 筌륁궢鍮??袁⑺뒄 ??猷????묐뻬??? 筌륁궢六??щ빍??";
    }
    if (reason === "no-viewer") {
        return "???뵬 ??곸뒠???袁⑹춦 ?븍뜄???? ??녿툡 ?袁⑺뒄 ??猷????묐뻬??? 筌륁궢六??щ빍?? ??긱걹 ???뵬 筌뤴뫖以?癒?퐣 ???뵬???믪눘? ?醫뤾문??뤾쉭??";
    }
    if (reason === "no-match-reviewed") {
        return "REVIEWED.txt 疫꿸퀣? 筌롫뗄?놅쭪?/??깆뵥 筌띲끉臾????쎈솭??됰뮸??덈뼄. (域뱀눘????륁뵠??깆뵠????釉?";
    }
    return "?袁⑹삺 ??뽯뻻 餓λ쵐???꾨뗀諭띌뀎怨쀫선 疫꿸퀣???곗쨮 ?袁⑺뒄??筌≪뼚? 筌륁궢六??щ빍??";
}

function getRulesManageUpdates() {
    return rulesManageRows
        .filter((row) => rulesManageDraftById.has(row.id) && rulesManageDraftById.get(row.id) !== !!row.enabled)
        .map((row) => ({ id: row.id, enabled: !!rulesManageDraftById.get(row.id) }));
}

function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
}

function createEmptyRuleDraft() {
    const nextOrder = rulesManageRows.reduce((maxValue, row) => Math.max(maxValue, Number(row.order || 0)), 0) + 10;
    return {
        id: "",
        order: nextOrder,
        enabled: true,
        file_types: ["Client", "Server"],
        rule_id: "",
        item: "",
        detector: {
            kind: "regex",
            pattern: "",
            flags: ["MULTILINE"],
        },
        finding: {
            severity: "Warning",
            message: "",
        },
        meta: {},
    };
}

function startNewRuleDraft() {
    rulesManageEditorMode = "create";
    rulesManageEditorRuleId = "";
    rulesManageEditorDraft = createEmptyRuleDraft();
    rulesManageStatusMessage = "Started a new rule draft.";
}

function loadRuleIntoEditor(ruleId) {
    const target = rulesManageRows.find((row) => String(row.id || "") === String(ruleId || ""));
    if (!target) return;
    rulesManageEditorMode = "edit";
    rulesManageEditorRuleId = String(target.id || "");
    rulesManageEditorDraft = deepClone({
        id: target.id,
        order: target.order,
        enabled: !!target.enabled,
        file_types: Array.isArray(target.file_types) ? target.file_types : ["Client", "Server"],
        rule_id: target.rule_id,
        item: target.item,
        detector: target.detector || { kind: target.detector_kind || "regex" },
        finding: target.finding || { severity: target.severity || "Warning", message: target.message || "" },
        meta: target.meta || {},
    });
}

function ensureRuleEditorState() {
    if (rulesManageEditorDraft) return;
    if (rulesManageRows.length) {
        loadRuleIntoEditor(rulesManageEditorRuleId || rulesManageRows[0].id);
        return;
    }
    startNewRuleDraft();
}

function readRuleEditorForm(form) {
    const detectorText = form.querySelector('[name="detector_json"]').value.trim() || "{}";
    const metaText = form.querySelector('[name="meta_json"]').value.trim() || "{}";
    let detector;
    let meta;
    try {
        detector = JSON.parse(detectorText);
    } catch (err) {
        throw new Error("detector JSON ?類ㅻ뻼????而?몴?? ??녿뮸??덈뼄.");
    }
    try {
        meta = JSON.parse(metaText);
    } catch (err) {
        throw new Error("meta JSON ?類ㅻ뻼????而?몴?? ??녿뮸??덈뼄.");
    }
    if (!detector || typeof detector !== "object" || Array.isArray(detector)) {
        throw new Error("detector JSON?? 揶쏆빘猿??鍮???몃빍??");
    }
    if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
        throw new Error("meta JSON?? 揶쏆빘猿??鍮???몃빍??");
    }
    const fileTypes = [];
    if (form.querySelector('[name="file_type_client"]').checked) fileTypes.push("Client");
    if (form.querySelector('[name="file_type_server"]').checked) fileTypes.push("Server");
    return {
        id: form.querySelector('[name="id"]').value.trim(),
        order: Number(form.querySelector('[name="order"]').value || 0),
        enabled: !!form.querySelector('[name="enabled"]').checked,
        file_types: fileTypes,
        rule_id: form.querySelector('[name="rule_id"]').value.trim(),
        item: form.querySelector('[name="item"]').value.trim(),
        detector,
        finding: {
            severity: form.querySelector('[name="severity"]').value.trim(),
            message: form.querySelector('[name="message"]').value.trim(),
        },
        meta,
    };
}

function applyRulesManagePayload(payload) {
    if (payload && Array.isArray(payload.rules)) {
        rulesManageRows = payload.rules;
        rulesManageDraftById = new Map(rulesManageRows.map((row) => [row.id, !!row.enabled]));
        if (rulesManageEditorMode === "create") {
            startNewRuleDraft();
        } else if (rulesManageEditorRuleId) {
            loadRuleIntoEditor(rulesManageEditorRuleId);
        } else if (rulesManageRows.length) {
            loadRuleIntoEditor(rulesManageRows[0].id);
        }
    }
}

function triggerRulesImport(mode) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.addEventListener("change", async () => {
        const file = input.files && input.files[0];
        if (!file) return;
        const text = await file.text();
        let payload;
        try {
            payload = JSON.parse(text);
        } catch (err) {
            rulesManageStatusMessage = "揶쎛?紐꾩궎疫?JSON ?類ㅻ뻼????而?몴?? ??녿뮸??덈뼄.";
            renderRulesHealth(latestRulesHealthPayload, "");
            return;
        }
        const rules = Array.isArray(payload) ? payload : (Array.isArray(payload.rules) ? payload.rules : []);
        if (!rules.length) {
            rulesManageStatusMessage = "揶쎛?紐꾩궞 rules 獄쏄퀣肉????곷뮸??덈뼄.";
            renderRulesHealth(latestRulesHealthPayload, "");
            return;
        }
        rulesManageSaving = true;
        renderRulesHealth(latestRulesHealthPayload, "");
        try {
            const response = await fetch("/api/rules/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode, rules }),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(result.error || `域뱀뮇??揶쎛?紐꾩궎疫???쎈솭 (${response.status})`);
            }
            applyRulesManagePayload(result);
            rulesManageStatusMessage = `揶쎛?紐꾩궎疫??袁⑥┷ (${Number(result.imported_count || 0)}揶? ${String(result.mode || mode)})`;
            await loadRulesHealth();
        } catch (err) {
            rulesManageStatusMessage = (err && err.message) || String(err);
            renderRulesHealth(latestRulesHealthPayload, "");
        } finally {
            rulesManageSaving = false;
            renderRulesHealth(latestRulesHealthPayload, "");
        }
    });
    input.click();
}

async function exportRulesManagePayload() {
    try {
        const response = await fetch("/api/rules/export");
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `域뱀뮇???????용┛ ??쎈솭 (${response.status})`);
        }
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `p1_rules_export_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 0);
        rulesManageStatusMessage = "域뱀뮇???????용┛ ?袁⑥┷";
        renderRulesHealth(latestRulesHealthPayload, "");
    } catch (err) {
        rulesManageStatusMessage = (err && err.message) || String(err);
        renderRulesHealth(latestRulesHealthPayload, "");
    }
}

async function saveRuleEditorForm(form) {
    if (rulesManageSaving) return;
    let rule;
    try {
        rule = readRuleEditorForm(form);
    } catch (err) {
        rulesManageStatusMessage = (err && err.message) || String(err);
        renderRulesHealth(latestRulesHealthPayload, "");
        return;
    }
    rulesManageSaving = true;
    renderRulesHealth(latestRulesHealthPayload, "");
    try {
        const endpoint = rulesManageEditorMode === "create" ? "/api/rules/create" : "/api/rules/replace";
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rule }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `域뱀뮇????????쎈솭 (${response.status})`);
        }
        applyRulesManagePayload(payload);
        rulesManageEditorMode = "edit";
        rulesManageEditorRuleId = String((payload.rule || {}).id || rule.id || "");
        loadRuleIntoEditor(rulesManageEditorRuleId);
        rulesManageStatusMessage = "域뱀뮇???????袁⑥┷";
        await loadRulesHealth();
    } catch (err) {
        rulesManageStatusMessage = (err && err.message) || String(err);
        renderRulesHealth(latestRulesHealthPayload, "");
    } finally {
        rulesManageSaving = false;
        renderRulesHealth(latestRulesHealthPayload, "");
    }
}

async function deleteCurrentRule() {
    if (rulesManageSaving || rulesManageEditorMode !== "edit" || !rulesManageEditorRuleId) return;
    rulesManageSaving = true;
    renderRulesHealth(latestRulesHealthPayload, "");
    try {
        const response = await fetch("/api/rules/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: rulesManageEditorRuleId }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `域뱀뮇????????쎈솭 (${response.status})`);
        }
        applyRulesManagePayload(payload);
        if (rulesManageRows.length) {
            loadRuleIntoEditor(rulesManageRows[0].id);
        } else {
            startNewRuleDraft();
        }
        rulesManageStatusMessage = "域뱀뮇???????袁⑥┷";
        await loadRulesHealth();
    } catch (err) {
        rulesManageStatusMessage = (err && err.message) || String(err);
        renderRulesHealth(latestRulesHealthPayload, "");
    } finally {
        rulesManageSaving = false;
        renderRulesHealth(latestRulesHealthPayload, "");
    }
}

function renderRulesManageEditor(panel) {
    ensureRuleEditorState();
    const draft = rulesManageEditorDraft || createEmptyRuleDraft();

    const wrap = document.createElement("div");
    wrap.className = "rules-manage-editor";

    const heading = document.createElement("div");
    heading.className = "rules-manage-editor-heading";
    heading.textContent = rulesManageEditorMode === "create" ? "??域뱀뮇???臾믨쉐" : `域뱀뮇???紐꾩춿: ${draft.id || "-"}`;
    wrap.appendChild(heading);

    if (rulesManageStatusMessage) {
        const status = document.createElement("div");
        status.className = "rules-manage-status";
        status.textContent = rulesManageStatusMessage;
        wrap.appendChild(status);
    }

    const form = document.createElement("form");
    form.className = "rules-manage-form";
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        void saveRuleEditorForm(form);
    });

    const fileTypeSet = new Set(Array.isArray(draft.file_types) ? draft.file_types : []);
    form.innerHTML = `
        <label class="rules-manage-field"><span>ID</span><input name="id" value="${escapeHtml(draft.id || "")}" ${rulesManageEditorMode === "edit" ? "readonly" : ""}></label>
        <label class="rules-manage-field"><span>Rule ID</span><input name="rule_id" value="${escapeHtml(draft.rule_id || "")}"></label>
        <label class="rules-manage-field"><span>Item</span><input name="item" value="${escapeHtml(draft.item || "")}"></label>
        <label class="rules-manage-field"><span>Order</span><input name="order" type="number" value="${Number(draft.order || 0)}"></label>
        <label class="rules-manage-field rules-manage-field-inline"><span>Enabled</span><input name="enabled" type="checkbox" ${draft.enabled ? "checked" : ""}></label>
        <div class="rules-manage-field">
            <span>File Types</span>
            <label class="rules-manage-checkbox"><input name="file_type_client" type="checkbox" ${fileTypeSet.has("Client") ? "checked" : ""}>Client</label>
            <label class="rules-manage-checkbox"><input name="file_type_server" type="checkbox" ${fileTypeSet.has("Server") ? "checked" : ""}>Server</label>
        </div>
        <label class="rules-manage-field"><span>Severity</span><input name="severity" value="${escapeHtml((((draft.finding || {}).severity) || ""))}"></label>
        <label class="rules-manage-field rules-manage-field-wide"><span>Message</span><textarea name="message" rows="3">${escapeHtml((((draft.finding || {}).message) || ""))}</textarea></label>
        <label class="rules-manage-field rules-manage-field-wide"><span>Detector JSON</span><textarea name="detector_json" rows="8">${escapeHtml(JSON.stringify(draft.detector || {}, null, 2))}</textarea></label>
        <label class="rules-manage-field rules-manage-field-wide"><span>Meta JSON</span><textarea name="meta_json" rows="5">${escapeHtml(JSON.stringify(draft.meta || {}, null, 2))}</textarea></label>
    `;

    const formActions = document.createElement("div");
    formActions.className = "rules-manage-actions";

    const submitButton = document.createElement("button");
    submitButton.type = "submit";
    submitButton.className = "rules-manage-button rules-manage-button-primary";
    submitButton.textContent = rulesManageSaving ? "Saving..." : (rulesManageEditorMode === "create" ? "Create Rule" : "Save Changes");
    submitButton.disabled = rulesManageSaving;

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "rules-manage-button";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = rulesManageSaving || rulesManageEditorMode !== "edit" || !rulesManageEditorRuleId;
    deleteButton.addEventListener("click", () => {
        void deleteCurrentRule();
    });

    formActions.append(submitButton, deleteButton);
    form.appendChild(formActions);
    wrap.appendChild(form);
    panel.appendChild(wrap);
}

function renderRulesManagePanel(host) {
    return rulesRenderRulesManagePanel(host);
}

async function loadRulesList(force = false) {
    return rulesLoadRulesList(force);
}

async function saveRulesManageUpdates() {
    return rulesSaveRulesManageUpdates();
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
        reasons.push("Critical issue concentration");
    } else if (severityKey === "warning") {
        reasons.push("Warning-heavy cluster");
    }

    if (duplicateCount >= 4) {
        reasons.push(`Duplicate overlap ${duplicateCount}`);
    }
    if (hotspotIssueCount >= 3) {
        reasons.push(`${String((item && (item.hotspotObject || item.target)) || "target")} hotspot ${hotspotIssueCount}`);
    }
    if (dominantRuleCount >= 2) {
        reasons.push(`${String((item && item.dominantRuleFamily) || "RULE")} rule concentration ${dominantRuleCount}`);
    }
    if (ruleBreadth >= 3) {
        reasons.push(`Rule breadth ${ruleBreadth}`);
    }
    if (sourceKey === "p1") {
        reasons.push("Heuristic findings need attention");
    } else if (sourceKey === "p2") {
        reasons.push("Ctrlpp findings need attention");
    } else if (sourceKey === "p3") {
        reasons.push("AI review suggests a follow-up");
    }

    return reasons.slice(0, 3).join(" | ") || "No recommendation details available";
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
    const prefix = mode === "rule_family" ? "Rule focus" : "Hotspot focus";
    const dedupe = (workspaceAnalysisInsights && workspaceAnalysisInsights.dedupe) || {};
    const topRecommendation = Array.isArray(workspaceAnalysisInsights && workspaceAnalysisInsights.recommendations)
        ? workspaceAnalysisInsights.recommendations[0]
        : null;
    const comparison = buildWorkspaceFilterComparisonSummary();
    workspaceQuickFilter.classList.remove("hidden");
    workspaceQuickFilterText.textContent = `${prefix}: ${label}${source ? ` | ${source.toUpperCase()}` : ""} | rows ${dedupe.displayedRowCount || 0} | issues ${dedupe.rawIssueCount || 0}${topRecommendation ? ` | Top ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` | ${comparison.banner}` : ""}`;
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
    const prefix = mode === "rule_family" ? "Rule family" : "Hotspot";
    return `${prefix}: ${label}${source ? ` | ${source.toUpperCase()}` : ""}`;
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
        banner: `?袁⑷퍥 ??????${currentRows}/${overallRows} 夷???곷뭼 ${currentIssues}/${overallIssues} 夷?${rowDelta}??${issueDelta}椰???뽰뇚`,
        detail: `?袁⑷퍥 野껉퀗??${overallRows}??${overallIssues}椰?餓??袁⑹삺 ${currentRows}??${currentIssues}椰꾨?彛???뽯뻻??몃빍?? ${rowDelta}??${issueDelta}椰꾨똻???袁り숲嚥???뽰뇚??뤿???щ빍??`,
    };
}

function appendDetailFact(container, label, value) {
    return detailAppendDetailFact(container, label, value);
}

function appendDetailNote(container, text, tone = "") {
    return detailAppendDetailNote(container, text, tone);
}

function renderInspectorSelectionMeta(violation, options = {}) {
    return detailRenderInspectorSelectionMeta(violation, options);
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
            dedupeSummary.textContent = "?브쑴苑???餓λ쵎???類ｂ봺 野껉퀗?드첎? ??뽯뻻??몃빍??";
        } else {
            dedupeSummary.className = "";
            dedupeSummary.innerHTML = `
                <div class="review-insight-stats">
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">Raw issues</div>
                        <div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div>
                    </div>
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">Visible rows</div>
                        <div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div>
                    </div>
                    <div class="review-insight-stat">
                        <div class="review-insight-stat-label">Collapsed duplicates</div>
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
            priorityRecommendations.textContent = "?브쑴苑????怨쀪퐨 ??륁젟 ?곕뗄荑????뽯뻻??몃빍??";
        } else {
            priorityRecommendations.className = "priority-list";
            priorityRecommendations.replaceChildren();
            const frag = document.createDocumentFragment();
            recommendations.forEach((item, idx) => {
                const card = document.createElement("div");
                card.className = "priority-item";
                card.tabIndex = 0;
                card.setAttribute("role", "button");
                card.setAttribute("aria-label", `${idx + 1}. ${String(item.target || "")} recommendation`);
                if (item && item.representativeRow && item.representativeRow.rowId) {
                    card.setAttribute("data-row-id", String(item.representativeRow.rowId));
                }
                card.innerHTML = `
                    <div class="priority-item-header">
                        <div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div>
                        <div class="priority-item-score">Score ${escapeHtml(item.score)}</div>
                    </div>
                    <div class="priority-item-meta">
                        ${escapeHtml(String(item.source).toUpperCase())} | ${escapeHtml(String(item.severity || "Info"))} | rows ${escapeHtml(item.rowCount)} | duplicates ${escapeHtml(item.duplicateCount)}
                    </div>
                    <div class="priority-item-meta">
                        hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)} | rule ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)} | breadth ${escapeHtml(item.ruleBreadth || 0)}
                    </div>
                    <div class="priority-item-reason">${escapeHtml(item.reason || "No recommendation details available")}</div>
                    <div class="priority-item-actions">
                        <button type="button" class="priority-chip priority-chip-hotspot">View hotspot</button>
                        <button type="button" class="priority-chip priority-chip-rule">View rule</button>
                    </div>
                    <div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "No lead message available"))}</div>
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
    return workspaceInitFilterControls();
}

function getFilterState() {
    return workspaceGetFilterState();
}

function buildWorkspaceFilterSummaryText() {
    const filters = getFilterState();
    const sourceLabels = [
        filters.sources.p1 ? "P1" : "",
        filters.sources.p2 ? "P2" : "",
    ].filter(Boolean);
    const severityLabels = [
        filters.severities.critical ? "Critical" : "",
        filters.severities.warning ? "Warning" : "",
        filters.severities.info ? "?類ｋ궖" : "",
    ].filter(Boolean);
    const recommendationText = buildRecommendationWorkspaceFilterText();
    const comparison = buildWorkspaceFilterComparisonSummary();
    const parts = [
        `???뮞 ${sourceLabels.length ? sourceLabels.join(", ") : "??곸벉"}`,
        `??而??${severityLabels.length ? severityLabels.join(", ") : "??곸벉"}`,
    ];
    if (recommendationText) {
        parts.push(recommendationText);
    } else {
        parts.push("?곕뗄荑??袁り숲 ??곸벉");
    }
    if (comparison.banner && recommendationText) {
        parts.push(comparison.banner);
    }
    return parts.join(" 夷?");
}

function renderWorkspaceFilterSummary() {
    return workspaceRenderWorkspaceFilterSummary();
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
    const raw = String(rawSeverity || "").trim();
    if (!raw) return "Info";
    const sev = raw.toLowerCase();
    if (sev === "critical") return "Critical";
    if (sev === "warning") return "Warning";
    if (sev === "high") return "High";
    if (sev === "medium") return "Medium";
    if (sev === "low") return "Low";
    if (sev === "info" || sev === "information") return "Info";
    if (sev === "error") return "Error";
    if (sev === "fatal") return "Fatal";
    if (sev === "performance") return "Performance";
    if (sev === "style") return "Style";
    if (sev === "portability") return "Portability";
    return raw;
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
    out = out.replace(/^Uninitialized variable:\s*(.+)$/i, "?λ뜃由?遺얜┷筌왖 ??? 癰궰?? $1");
    out = out.replace(
        /^It is potentially a safety issue to use the function\s+(.+)$/i,
        "??λ땾 $1 ????? ?醫롮삺?怨몄뵥 ??됱읈????곷뭼揶쎛 ??????됰뮸??덈뼄",
    );
    out = out.replace(
        /^It is really neccessary to use the function\s+(.+)$/i,
        "??λ땾 $1 ??????類ｌ춾 ?袁⑹뒄??? 野꺜?醫뤿릭?紐꾩뒄",
    );
    out = out.replace(
        /^It is really necessary to use the function\s+(.+)$/i,
        "??λ땾 $1 ??????類ｌ춾 ?袁⑹뒄??? 野꺜?醫뤿릭?紐꾩뒄",
    );
    out = out.replace(
        /^Cppcheck cannot find all the include files \(use --check-config for details\)$/i,
        "Cppcheck揶쎛 ??? include ???뵬??筌≪뼚? 筌륁궢六??щ빍??(--check-config嚥??怨멸쉭 ?類ㅼ뵥)",
    );
    return out;
}

function localizeCtrlppByRuleId(ruleId, message, verbose) {
    const id = String(ruleId || "").toLowerCase();
    const msg = String(message || "");
    const details = String(verbose || "");
    const mapping = [
        { keys: ["uninitializedvariable", "uninitvar"], text: "?λ뜃由?遺얜┷筌왖 ??? 癰궰??????揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["nullpointer", "nullpointerdereference"], text: "????????臾롫젏 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["checklibrarynoreturn", "noreturn"], text: "獄쏆꼹?싧첎???됱뇚 筌ｌ꼶???袁⑥뵭 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["memleak", "resourceleak"], text: "筌롫뗀?덄뵳??癒?뜚 ??곸젫 ?袁⑥뵭 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["unusedfunction", "unusedvariable"], text: "沃섎챷沅???꾨뗀諭???λ땾/癰궰??揶쎛 ??釉??뤿선 ??됰뮸??덈뼄." },
        { keys: ["syntaxerror", "parseerror"], text: "?얜챶苡??닌됎???살첒 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["bufferaccessoutofbounds", "outofbounds"], text: "獄쏄퀣肉?甕곌쑵??野껋럡???λ뜃???臾롫젏 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["useafterfree"], text: "??곸젫???癒?뜚 ?臾롫젏(use-after-free) 揶쎛?關苑????됰뮸??덈뼄." },
        { keys: ["shadowvariable", "shadowedvariable"], text: "癰궰??域밸챶???shadowing)嚥??紐낅립 ??곕짗 揶쎛?關苑????됰뮸??덈뼄." },
    ];
    for (const entry of mapping) {
        if (entry.keys.some((k) => id.includes(k))) return entry.text;
    }
    if (id === "ctrlppcheck.info") {
        const localized = localizeCtrlppMessage(msg || details);
        return localized || "CtrlppCheck ?類ｋ궖??筌롫뗄?놅쭪???낅빍??";
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
        return name ? `?????${name}揶쎛 null??????됰선 ?臾롫젏 ????살첒 揶쎛?關苑????됰뮸??덈뼄.` : "null ??????臾롫젏 揶쎛?關苑????됰뮸??덈뼄.";
    }
    const callMatch = text.match(/function\s+([A-Za-z_][A-Za-z0-9_]*)/i);
    if (callMatch) return `??λ땾 ${callMatch[1]} ?紐꾪뀱?봔?癒?퐣 ??됱읈????됱뇚 筌ｌ꼶???癒????袁⑹뒄??몃빍??`;
    const varMatch = text.match(/variable:\s*([A-Za-z_][A-Za-z0-9_]*)/i);
    if (varMatch) return `癰궰??${varMatch[1]} ?????袁⑸퓠 ?λ뜃由???醫륁뒞??野꺜筌앹빘???袁⑹뒄??몃빍??`;
    return "";
}

function buildP2LocalizedMessage(violation) {
    const ruleId = String((violation && violation.rule_id) || "");
    const rawMessage = String((violation && violation.message) || "").trim();
    const verbose = String((violation && violation.verbose) || "").trim();
    const byRule = localizeCtrlppByRuleId(ruleId, rawMessage, verbose);
    const byPattern = localizeCtrlppByPattern(rawMessage || verbose);
    const localizedText = byRule || byPattern || (rawMessage ? `(P2) ${truncateMiddle(rawMessage, 180)}` : "P2 message unavailable");
    const shortText = truncateMiddle(localizedText.replace(/^\(P2\)\s*/i, ""), 80) || "P2 message unavailable";
    return { shortText, localizedText, rawText: rawMessage || verbose || "" };
}

function buildP2DetailBlocks(violation) {
    const ruleId = String((violation && violation.rule_id) || "unknown");
    const severity = String((violation && (violation.severity || violation.type)) || "information").toLowerCase();
    const lineNo = positiveLineOrZero(violation && violation.line);
    const fileName = basenamePath(violation && (violation.file || violation.file_name || violation.filename));
    const localized = buildP2LocalizedMessage(violation);

    const cause = localized.localizedText || "P2 ?類ㅼ읅 ?브쑴苑?癒?퐣 ?袁る퓮 ?醫륁깈揶쎛 揶쏅Ŋ???뤿???щ빍??";
    const impactMap = {
        error: "??쎈뻬 餓???살첒 ?癒?뮉 ??됱읈???얜챷?ｆ에???곷선筌?揶쎛?關苑???誘る뮸??덈뼄.",
        warning: "疫꿸퀡????됱젟???醫?癰귣똻???????揶쎛?關苑????됰뮸??덈뼄.",
        performance: "?源낅뮟 ?????癒?뮉 ?븍뜇釉?酉釉??귐딅꺖???????獄쏆뮇源??????됰뮸??덈뼄.",
        information: "筌앸맩????살첒???袁⑤빍筌왖筌??꾨뗀諭???됱춳 揶쏆뮇苑???袁⑹뒄??????됰뮸??덈뼄.",
        style: "揶쎛??녾쉐/?????????롮쨮 ?醫?癰귣똻????쑴???筌앹빓???????됰뮸??덈뼄.",
        portability: "??띻펾/甕곌쑴??筌△뫁??癒?퐣 ??덉삂 筌△뫁?졾첎? 獄쏆뮇源??????됰뮸??덈뼄.",
    };
    const impact = impactMap[severity] || "?꾨뗀諭???됱춳 獄???됱젟?源녿퓠 ?봔?類ㅼ읅 ?怨밸샨????됱뱽 ????됰뮸??덈뼄.";

    let action = "?온???꾨뗀諭?癒?퐣 ??낆젾揶?野꺜筌? ??됱뇚 筌ｌ꼶?? 獄쏆꼹?싧첎??類ㅼ뵥???곕떽???랁???덉뵬 ???쉘????ｍ뜞 ?癒???뤾쉭??";
    const lowerRule = ruleId.toLowerCase();
    if (lowerRule.includes("uninitialized")) {
        action = "癰궰???醫롫섧 ???λ뜃由겼첎誘れ뱽 筌뤿굞???랁??????袁⑸퓠 ?λ뜃由??野껋럥以덄몴?癰귣똻???뤾쉭??";
    } else if (lowerRule.includes("null")) {
        action = "??????紐껊굶 ??????null 野꺜??? ??쎈솭 ?브쑨由?筌ｌ꼶?곭몴??곕떽???뤾쉭??";
    } else if (lowerRule.includes("noreturn")) {
        action = "??λ땾 獄쏆꼹?싧첎誘れ뱽 ?類ㅼ뵥??랁???쎈솭 ??嚥≪뮄??癰귣벀??嚥≪뮇彛???곕떽???뤾쉭??";
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleId || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `?癒?뵥: ${cause}`,
        impact: `?怨밸샨: ${impact}`,
        action: `亦낅슣?ｈ?怨쀭뒄: ${action} (域뱀눊援? ${evidence})`,
        raw: localized.rawText ? `?癒?? ${truncateMiddle(localized.rawText, 180)}` : "",
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

    let cause = message || "P1 ?類ㅼ읅 域뱀뮇???브쑴苑?癒?퐣 揶쏆뮇苑???袁⑹뒄???꾨뗀諭????쉘??揶쏅Ŋ???뤿???щ빍??";
    let impact = "?꾨뗀諭???됱춳 獄??醫?癰귣똻???????揶쎛?關苑????됰뮸??덈뼄.";
    let action = "域뱀뮇????롫즲??筌띿쉳苡?嚥≪뮇彛???類ｂ봺??랁???덉뵬 ???쉘????ｍ뜞 ?癒???뤾쉭??";

    const exactTemplates = {
        "CLEAN-DUP-01": {
            cause: "??덉뵬/?醫롪텢 ?꾨뗀諭뜹첎? 獄쏆꼶???뤿선 餓λ쵎?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??륁젟 ?袁⑥뵭 揶쎛?關苑???뚣끉????醫?癰귣똻????쑴???筌앹빓???????됰뮸??덈뼄.",
            action: "?⑤벏??嚥≪뮇彛????λ땾/???곫에??곕뗄???餓λ쵎???꾨뗀諭띄몴???볤탢??뤾쉭??",
        },
        "CLEAN-DEAD-01": {
            cause: "?袁⑤뼎 ?븍뜃? ?癒?뮉 沃섎챷沅???꾨뗀諭뜹첎? 揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쎛??녾쉐??????롫┷???꾨뗀諭???롫즲????쎈퉸??揶쎛?關苑????됰뮸??덈뼄.",
            action: "?븍뜇釉???꾨뗀諭띄몴???볤탢??랁?筌〓챷???紐꾪뀱 ?怨밸샨 甕곕뗄?욅몴???ｍ뜞 ?癒???뤾쉭??",
        },
        "HARD-01": {
            cause: "??롫굡?꾨뗀逾???얜챷???揶??????揶쏅Ŋ???뤿???щ빍??",
            impact: "??띻펾 癰궰野?????륁젟 甕곕뗄?욃첎? ?뚣끉?????곸겫 ?醫롫염?源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "?怨몃땾 ?癒?뮉 Config 疫꿸퀡而??곗쨮 ?브쑬???랁???? ??덈뮉 ??已???봔??釉?紐꾩뒄.",
        },
        "HARD-02": {
            cause: "??롫굡?꾨뗀逾??揶????????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "獄쏄퀬猷???띻펾癰?鈺곌퀗援????臾믪뵠 ????????癰궰野??귐딅뮞??? 筌앹빓???????됰뮸??덈뼄.",
            action: "揶쏅?????쇱젟/?怨몃땾?酉釉??癰궰野?揶쎛?館釉????뵬沃섎챸苑ｆ에??브쑬???뤾쉭??",
        },
        "HARD-03": {
            cause: "??롫굡?꾨뗀逾?揶???뤵????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??곸겫 ?類ㅼ퐠 癰궰野????꾨뗀諭???륁젟??獄쏆꼶???뤿선 ?關釉?揶쎛?關苑???誘る툡筌?????됰뮸??덈뼄.",
            action: "Config/?怨몃땾 ???뵠?됰뗀以??????揶?癰궰野껋럩???꾨뗀諭???륁젟 ??곸뵠 揶쎛?館釉?袁⑥쨯 ?類ｂ봺??뤾쉭??",
        },
        "CFG-01": {
            cause: "config ?④쑴鍮??癒?뮉 ???類λ????븍뜆?ょ㎉?揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?怨?????쇱젟 ??삳짗?臾믪몵嚥?疫꿸퀡????쎈솭揶쎛 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "config ??????疫꿸퀡??첎誘れ뱽 ?癒???랁??袁⑥뵭 ?냈??곷뮞??????獄쎻뫗堉??브쑨由곁몴??곕떽???뤾쉭??",
        },
        "CFG-ERR-01": {
            cause: "config 嚥≪뮆諭?野꺜筌???살첒 筌ｌ꼶???袁⑥뵭 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쇱젟 ??살첒揶쎛 ?怨쀫뇵 ?關釉룡에??袁る솁??????됰뮸??덈뼄.",
            action: "config ??살첒 筌ｌ꼶??野껋럥以덄몴?筌뤿굞???랁???쎈솭 ????됱읈??疫꿸퀡????덉삂???類ㅼ벥??뤾쉭??",
        },
        "STYLE-NAME-01": {
            cause: "筌뤿굝梨?域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?꾨뗀諭???롫즲 ???툢????????죬 ?臾믩씜 ??쑴???筌앹빓???????됰뮸??덈뼄.",
            action: "?袁⑥쨮??븍뱜 筌뤿굝梨?域뱀뮇???筌띿쉳苡???명????已???類ｂ봺??뤾쉭??",
        },
        "STYLE-INDENT-01": {
            cause: "??쇰연?怨뚮┛/?類ｌ졊 域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쎛??녾쉐??????롫┷???귐됰윮 ??μ몛????λ선筌?????됰뮸??덈뼄.",
            action: "???????쇰연?怨뚮┛ 域뱀뮇???곗쨮 ?類ｂ봺??랁??됰뗀以??닌듼쒐몴?筌뤿굟???筌띿쉸??紐꾩뒄.",
        },
        "STYLE-HEADER-01": {
            cause: "??삳쐭/雅뚯눘苑??????域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "???뵬 筌뤴뫗??癰궰野????????툢????????춳 ????됰뮸??덈뼄.",
            action: "?袁⑥쨮??븍뱜 ??? ??삳쐭/雅뚯눘苑???????怨몄뒠??뤾쉭??",
        },
        "STD-01": {
            cause: "?꾨뗀逾???? 域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?? ??????源놁뵠 繹먥뫁議??醫?癰귣똻????μ몛??????롫쭍 ????됰뮸??덈뼄.",
            action: "??? 揶쎛??諭??筌띿쉸???꾨뗀諭??????⑤궢 ?닌듼쒐몴??類ｂ봺??뤾쉭??",
        },
        "EXC-TRY-01": {
            cause: "??됱뇚 揶쎛???닌덉퍢??????癰귣똾??筌ｌ꼶???봔鈺곌퉮??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쎈솭揶쎛 ?怨몄맄 嚥≪뮇彛??곗쨮 ?袁る솁??뤿선 癰귣벀??筌왖?怨쀬뵠 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "try-catch?? ??살첒 嚥≪뮄??癰귣벀???브쑨由곁몴??곕떽?????됱뇚 野껋럥以덄몴?筌뤿굞??怨몄몵嚥?筌ｌ꼶???뤾쉭??",
        },
        "COMP-01": {
            cause: "癰귣벊????⑥눖?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??꾨퉸/???뮞????뽰뵠?袁? ???ゅ첎? 野껉퀬釉??醫롮뿯?쒖쥙??筌앹빓???????됰뮸??덈뼄.",
            action: "??λ땾???브쑬???랁??브쑨由??닌듼쒐몴???λ떄?酉鍮?癰귣벊??袁? ????紐꾩뒄.",
        },
        "COMP-02": {
            cause: "?브쑨由??⑥눖? ?癒?뮉 ?⑥눖猷??癰귣벏鍮 鈺곌퀗援????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??륁젟 ???????뽰뵠??됰뱜 揶쎛?關苑???뚣끉彛?????됰뮸??덈뼄.",
            action: "鈺곌퀗援??뱀뱽 ?브쑵鍮??랁?鈺곌퀗由?獄쏆꼹?????쉘??곗쨮 嚥≪뮇彛??癒?カ????λ떄?酉釉?紐꾩뒄.",
        },
        "PERF-01": {
            cause: "Callback ????癒?퐣 delay ?紐꾪뀱 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?꾩뮆媛?筌ｌ꼶??筌왖?怨쀬몵嚥???源???袁⑥뵭/?臾먮뼗??????? 獄쏆뮇源????됱젟????곷뭼嚥???곷선筌?????됰뮸??덈뼄.",
            action: "Callback ??? delay ?紐꾪뀱????볤탢??랁? ??쑬猷욄묾????餓κ쑬彛??癒?뮉 ???????브쑬???닌듼쒏에??袁れ넎??뤾쉭??",
        },
        "PERF-05": {
            cause: "dpSetTimed嚥???筌?揶쎛?館釉??紐꾪뀱 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?븍뜇釉?酉釉??紐꾪뀱 獄쎻뫗???곗쨮 ?紐낅퉸 ????而???뽯선 ?봔?類μ넇/?봔??筌앹빓?揶쎛 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "雅뚯눊由??筌왖???紐꾪뀱?? dpSetTimed 疫꿸퀡而??곗쨮 ?袁れ넎??랁? 疫꿸퀣???紐꾪뀱 ??뽰젎/揶쏄쑨爰????ｍ뜞 ?類ｂ봺??뤾쉭??",
        },
        "SEC-01": {
            cause: "SQL/?묒눖???얜챷????닌딄쉐 ????낆젾揶?野꺜筌??봔鈺????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쑴?????낆젾???묒눖???獄쏆꼷???뤿선 癰귣똻釉??띯뫁鍮?癒?몵嚥???곷선筌?????됰뮸??덈뼄.",
            action: "??낆젾揶?野꺜筌??類?뇣?遺? ???뵬沃섎챸苑?遺얜쭆 ?묒눖???????곗쨮 雅뚯눘???袁る퓮??筌△뫀???뤾쉭??",
        },
        "DB-01": {
            cause: "?얜챷???疫꿸퀡而?SQL 鈺곌퀬鍮 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?묒눖??揶쎛??녾쉐/??됱젟?源놁뵠 ????롫┷????낆젾揶?野껉퀬鍮 ??쇰땾嚥??關釉??袁る퓮??筌앹빓???????됰뮸??덈뼄.",
            action: "?묒눖?곭몴????뵬沃섎챸苑?獄쏅뗄???獄쎻뫗???곗쨮 ?袁れ넎??랁??얜챷???野껉퀬鍮 SQL ?臾믨쉐??餓κ쑴??紐꾩뒄.",
        },
        "DB-02": {
            cause: "?묒눖??雅뚯눘苑???살구 ?袁⑥뵭 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?묒눖????롫즲 ???툢????????醫?癰귣똻???關釉???????볦퍢??筌앹빓???????됰뮸??덈뼄.",
            action: "餓λ쵐???묒눖???닌덉퍢??筌뤴뫗??鈺곌퀗援????살구??롫뮉 雅뚯눘苑??癰귣떯而??랁?域뱀뮇???筌띿쉳苡??온?귐뗫릭?紐꾩뒄.",
        },
        "SAFE-DIV-01": {
            cause: "0??곗쨮 ??롫땽??됱뵠 獄쏆뮇源??????덈뮉 ?怨쀪텦 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?怨?????살첒 ?癒?뮉 ??쑴???揶??袁る솁嚥??怨쀫뇵 ?關釉룟첎? 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "?브쑬??0 揶쎛??鈺곌퀗援붹???됱뇚 ?브쑨由?筌ｌ꼶?곭몴??곕떽?????됱읈??띿쓺 ?④쑴沅??뤾쉭??",
        },
        "VAL-01": {
            cause: "??낆젾/餓λ쵌而쇿첎??醫륁뒞??野꺜筌??봔鈺????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??롢걵??揶쏅????袁⑸꺗 嚥≪뮇彛??곗쨮 ?袁る솁??뤿선 ??삳짗??揶쎛?關苑???뚣끉彛?????됰뮸??덈뼄.",
            action: "甕곕뗄???類ㅻ뻼/????? 野꺜筌앹빘??筌뤿굞??怨몄몵嚥??곕떽???랁???쎈솭 ?브쑨由곁몴??類ㅼ벥??뤾쉭??",
        },
        "LOG-LEVEL-01": {
            cause: "嚥≪뮄????덇볼 ??????怨뱀넺 ?????봔?怨몄쟿?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??곸겫 ??餓λ쵐????源???袁⑥뵭 ?癒?뮉 ?紐꾩뵠筌?筌앹빓?嚥?筌뤴뫀??怨뺤춦 ??됱춳??????롫쭍 ????됰뮸??덈뼄.",
            action: "?怨뱀넺??筌띿쉶??嚥≪뮄????덇볼?????뉒몴?묐릭?????뼎 ??源?紐껊뮉 ???????덇볼嚥?疫꿸퀡以??뤾쉭??",
        },
        "LOG-DBG-01": {
            cause: "?遺얠쒔域?嚥≪뮄???⑥눖???遺욍????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "嚥≪뮄???紐꾩뵠筌?筌앹빓?嚥??關釉??癒?뵥 ?곕뗄????μ몛??????롫쭍 ????됰뮸??덈뼄.",
            action: "?븍뜇釉?酉釉??遺얠쒔域?嚥≪뮄?뉒몴???볤탢??랁???곸겫??嚥≪뮄?뉛쭕???ｋ┛?袁⑥쨯 ?類ｂ봺??뤾쉭??",
        },
        "PERF-02": {
            cause: "獄쏆꼶???룐뫂遊??닌덉퍢 ??쑵????紐꾪뀱 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?븍뜇釉?酉釉?獄쏆꼶???紐꾪뀱嚥??臾먮뼗 筌왖??獄??癒?뜚 ?????깆뵠 筌앹빓???????됰뮸??덈뼄.",
            action: "獄쏆꼶???닌덉퍢 ?紐꾪뀱???얜씈??筌ｌ꼶???랁??紐꾪뀱 ??쏅땾??筌ㅼ뮇??酉釉?紐꾩뒄.",
        },
        "PERF-02-WHERE-DPT-IN-01": {
            cause: "WHERE ??DPT IN ????筌ㅼ뮇??????????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "鈺곌퀬??鈺곌퀗援????쑵???μ읅??곗쨮 ?닌딄쉐??뤿선 筌ｌ꼶????볦퍢??筌앹빓???????됰뮸??덈뼄.",
            action: "DPT IN 鈺곌퀗援????뽰뒠??鈺곌퀬??甕곕뗄?욅몴?筌ㅼ뮇??酉釉???븍뜇釉?酉釉??癒?퉳??餓κ쑴??紐꾩뒄.",
        },
        "PERF-03": {
            cause: "筌왖??筌△뫀????紐꾪뀱 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??源??筌ｌ꼶????살쟿??筌왖?怨쀬몵嚥???뽯뮞???臾먮뼗?源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "筌△뫀????紐꾪뀱????쑬猷욄묾?筌ｌ꼶?곫에??袁れ넎??랁??紐꾪뀱 ??뽰젎???브쑬???뤾쉭??",
        },
        "PERF-03-ACTIVE-DELAY-01": {
            cause: "active ?뚢뫂???쎈뱜?癒?퐣 delay ???????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쇰뻻揶???源??筌ｌ꼶??筌왖?怨쀬몵嚥?疫꿸퀡????됱젟?源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "active 野껋럥以?癒?퐣 delay????볤탢??랁??????????餓κ쑬??疫꿸퀡而??癒?カ??곗쨮 ??筌ｋ똾釉?紐꾩뒄.",
        },
        "PERF-EV-01": {
            cause: "??源???대????紐꾪뀱 ?⑥눖?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??源???紐껋삋??筌앹빓?嚥?筌ｌ꼶??筌왖?怨뚮궢 ?봔???怨몃뱟??獄쏆뮇源??????됰뮸??덈뼄.",
            action: "??源???대?????쏅땾??餓κ쑴?졿??袁⑹뒄 ??源?紐껋춸 ?醫딇???袁⑤뼎??롫즲嚥??類ｂ봺??뤾쉭??",
        },
        "ACTIVE-01": {
            cause: "?怨밴묶 癰궰野??紐꾪뀱 ??Active/Enable 鈺곌퀗援??類ㅼ뵥 ?袁⑥뵭 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쑵????怨밴묶?癒?퐣??癰궰野??紐꾪뀱????쎈뻬??뤿선 ??뉖┛燁???? ??덉삂??獄쏆뮇源??????됰뮸??덈뼄.",
            action: "?怨밴묶 癰궰野??袁⑸퓠 Active/Enable 揶쎛??鈺곌퀗援??筌뤿굞???랁?false 野껋럥以?筌ｌ꼶??嚥≪뮇彛???곕떽???뤾쉭??",
        },
        "DUP-ACT-01": {
            cause: "??덉뵬 ???怨몃퓠 ????餓λ쵎????덉삂 筌ｌ꼶??揶쎛?? ?봔??揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?븍뜇釉?酉釉?餓λ쵎???紐꾪뀱嚥??源낅뮟 ????獄??怨밴묶 ?븍뜆?ょ㎉?揶쎛?關苑??筌앹빓???????됰뮸??덈뼄.",
            action: "餓λ쵎??獄쎻뫗? 揶쎛??癰궰野?揶쏅Ŋ?/???삋域??? 鈺곌퀗援??브쑨由곁몴??곕떽?????덉뵬 ??덉삂 獄쏆꼶???筌△뫀???뤾쉭??",
        },
        "PERF-DPSET-BATCH-01": {
            cause: "dpSet 獄쏄퀣???沃섎챷??????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쏆뮆???紐꾪뀱 獄쏆꼶???곗쨮 筌ｌ꼶????볦퍢??筌앹빓???????됰뮸??덈뼄.",
            action: "揶쎛?館釉??닌덉퍢?? dpSet 獄쏄퀣???紐꾪뀱嚥??袁れ넎??뤾쉭??",
        },
        "PERF-DPGET-BATCH-01": {
            cause: "dpGet 獄쏄퀣???沃섎챷??????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쏆뮆??鈺곌퀬??獄쏆꼶???곗쨮 ?臾먮뼗 筌왖?怨쀬뵠 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "鈺곌퀬???닌덉퍢??獄쏄퀣???遺욧퍕??곗쨮 ?얜씈堉?I/O ??쑴???餓κ쑴??紐꾩뒄.",
        },
        "PERF-SETVALUE-BATCH-01": {
            cause: "setValue 獄쏆꼶???紐꾪뀱 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?紐꾪뀱 ?袁⑹읅??곗쨮 ?븍뜇釉?酉釉??봔??? 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "setValue ?紐꾪뀱??獄쏄퀣??筌ｌ꼶??揶쎛?館釉?獄쎻뫗???곗쨮 ?袁れ넎??뤾쉭??",
        },
        "PERF-SETMULTIVALUE-ADOPT-01": {
            cause: "??쇱㉦ set ??낅쑓??꾨뱜 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "獄쏆꼶????낅쑓??꾨뱜嚥?筌ｌ꼶????μ몛??????롫쭍 ????됰뮸??덈뼄.",
            action: "setMultiValue API???怨몄뒠????쇱㉦ ??낅쑓??꾨뱜?????? 筌ｌ꼶???뤾쉭??",
        },
        "PERF-GETVALUE-BATCH-01": {
            cause: "getValue 獄쏆꼶??鈺곌퀬?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "獄쏆꼶??鈺곌퀬?뜻에?鈺곌퀬??筌왖?怨뚮궢 ?癒?뜚 ???걟揶쎛 筌앹빓???????됰뮸??덈뼄.",
            action: "getValue ?紐꾪뀱??獄쏄퀣?????? 鈺곌퀬??獄쎻뫗???곗쨮 ?袁れ넎??뤾쉭??",
        },
        "PERF-GETMULTIVALUE-ADOPT-01": {
            cause: "??쇱㉦ get 鈺곌퀬?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쏆뮆??鈺곌퀬??獄쏆꼶???곗쨮 ?源낅뮟 ????? 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "getMultiValue API???怨몄뒠????쇱㉦ 鈺곌퀬?띄몴????? 筌ｌ꼶???뤾쉭??",
        },
        "PERF-AGG-01": {
            cause: "??롫짗 筌욌쵌???룐뫂遊?疫꿸퀡而?筌욌쵌?????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "?怨쀪텦 ??쑴??筌앹빓?嚥?筌ｌ꼶??筌왖?怨쀬뵠 ?袁⑹읅??????됰뮸??덈뼄.",
            action: "筌욌쵌??嚥≪뮇彛???⑤벏??獄쏄퀣??筌ｌ꼶?곫에???λ떄?酉鍮?獄쏆꼶???怨쀪텦??餓κ쑴??紐꾩뒄.",
        },
    };

    const prefixTemplates = [
        ["PERF-", {
            cause: "獄쏆꼶???紐꾪뀱/??낅쑓??꾨뱜 ???쉘??곗쨮 ?紐낅립 ??쑵???揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?븍뜇釉?酉釉??紐꾪뀱 ?袁⑹읅??곗쨮 ?臾먮뼗 筌왖??獄??귐딅꺖???????筌앹빓?揶쎛 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "獄쏆꼶???紐꾪뀱???얜씈??筌ｌ꼶???띻탢??獄쏄퀣??獄쎻뫗???곗쨮 癰궰野껋?釉?? ??덉뵬 ?닌덉퍢 ?紐꾪뀱 ??쏅땾??餓κ쑴??紐꾩뒄.",
        }],
        ["SEC-", {
            cause: "??낆젾揶?野꺜筌??癒?뮉 癰귣똻釉?獄쎻뫗堉?嚥≪뮇彛???겸뫖???? ??? ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쑴?????낆젾??곗쨮 ?紐낅립 ??삳짗???癒?뮉 癰귣똻釉??띯뫁鍮?癒?몵嚥???곷선筌?????됰뮸??덈뼄.",
            action: "??낆젾揶?野꺜筌??類?뇣?遺? 獄쎻뫗堉?嚥≪뮇彛???곕떽???랁? ?紐? ??낆젾 野껋럥以덄몴??怨쀪퐨 ?癒???뤾쉭??",
        }],
        ["DB-", {
            cause: "?怨쀬뵠??鈺곌퀬??揶쏄퉮???묒눖???온??域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?묒눖??癰궰野??怨밸샨 ?곕뗄?????????????곸겫 ??됱젟?源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "?묒눖???臾믨쉐 獄쎻뫗???????酉釉??獄쏅뗄???雅뚯눘苑???살첒筌ｌ꼶??域뱀뮇???癰귣떯而??뤾쉭??",
        }],
        ["SAFE-", {
            cause: "??됱읈???온??癰귣똾??鈺곌퀗援???봔鈺곌퉲釉??꾨뗀諭????쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??됱뇚 ?怨뱀넺?癒?퐣 ?怨?????살첒????뉖┛燁???? ?怨밴묶 ?袁⑹뵠揶쎛 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "揶쎛??鈺곌퀗援붹???쎈솭 ?브쑨由?筌ｌ꼶?곭몴?癰귣떯而??랁? ??됱뇚 野껋럥以덄몴?筌뤿굞??怨몄몵嚥?筌ｌ꼶???뤾쉭??",
        }],
        ["VAL-", {
            cause: "揶??醫륁뒞??野꺜筌앹빘???袁⑥뵭??뤿?椰꾧퀡援??븍뜆?먬겫袁る립 ???쉘??揶쏅Ŋ???뤿???щ빍??",
            impact: "??롢걵???怨쀬뵠???袁る솁嚥?疫꿸퀡????쇱삂??獄??遺얠쒔繹???쑴??筌앹빓?揶쎛 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "??낆젾/餓λ쵌而쇿첎?野꺜筌앹빘???곕떽???랁?甕곕뗄???類ㅻ뻼 筌ｋ똾寃뺟몴?筌뤿굟????브쑬???뤾쉭??",
        }],
        ["LOG-", {
            cause: "嚥≪뮄??筌ｌ꼶??域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??곸겫 ??곷뭼 ?곕뗄??源놁뵠 ????롫┷???關釉??브쑴苑???볦퍢??筌앹빓???????됰뮸??덈뼄.",
            action: "嚥≪뮄????덇볼??筌롫뗄?놅쭪? ?????域뱀뮇???筌띿쉳苡??類ｂ봺??랁????뼎 ?브쑨由?嚥≪뮄?뉒몴?癰귣똻???뤾쉭??",
        }],
        ["CLEAN-", {
            cause: "?꾨뗀諭??類ｂ봺(????? 域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "揶쎛??녾쉐???醫?癰귣똻??源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "餓λ쵎??沃섎챷沅???븍뜇釉???꾨뗀諭띄몴??類ｂ봺??랁??⑤벏??嚥≪뮇彛??곗쨮 ??????뤾쉭??",
        }],
        ["HARD-", {
            cause: "??롫굡?꾨뗀逾?筌왖??域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??띻펾/?遺쎈럡??鍮?癰궰野????臾믪뵠 ??????춳 ????됰뮸??덈뼄.",
            action: "??롫굡?꾨뗀逾?揶쏅?????쇱젟/?怨몃땾?酉釉???꾨뗀諭???뤵?袁? ????紐꾩뒄.",
        }],
        ["CFG-", {
            cause: "??쇱젟(config) ?類λ???域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?怨?????쇱젟 ??살첒嚥?疫꿸퀡????쇱삂??덉뵠 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "config ??疫꿸퀡??첎???살첒筌ｌ꼶???브쑨由곁몴??癒?????쇱젟 ?④쑴鍮??筌띿쉸??紐꾩뒄.",
        }],
        ["STYLE-", {
            cause: "?꾨뗀逾??????域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?臾믩씜 揶쎛??녾쉐??????源놁뵠 ????롫쭍 ????됰뮸??덈뼄.",
            action: "?? ?????揶쎛??諭??筌띿쉳苡?筌뤿굝梨???쇰연?怨뚮┛/??삳쐭???類ｂ봺??뤾쉭??",
        }],
        ["EXC-", {
            cause: "??됱뇚 筌ｌ꼶??域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쎈솭 ?袁る솁嚥??關釉??브쑴苑?癰귣벀????볦퍢??筌앹빓???????됰뮸??덈뼄.",
            action: "??됱뇚 筌ｌ꼶??? 嚥≪뮄??癰귣벀???브쑨由곁몴?筌뤿굞??怨몄몵嚥?癰귣떯而??뤾쉭??",
        }],
        ["ACTIVE-", {
            cause: "??뽮쉐 ?怨밴묶/??쎈뻬 鈺곌퀗援?野꺜筌?域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "??쑵????닌덉퍢?癒?퐣 ??덉삂????묐뻬??뤿선 ?怨밴묶 ?븍뜆?ょ㎉?? 獄쏆뮇源??????됰뮸??덈뼄.",
            action: "Active/Enable 鈺곌퀗援?揶쎛??? ??쎈솭 野껋럥以?筌ｌ꼶?곭몴?筌뤿굞??怨몄몵嚥??곕떽???뤾쉭??",
        }],
        ["DUP-", {
            cause: "餓λ쵎????덉삂 獄쎻뫗? 域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "餓λ쵎???紐꾪뀱 ?袁⑹읅??곗쨮 ?源낅뮟 ????? ??뉖┛燁???? ??덉삂??獄쏆뮇源??????됰뮸??덈뼄.",
            action: "餓λ쵎??獄쎻뫗? 揶쎛??? 癰궰野?揶쏅Ŋ? 鈺곌퀗援???곕떽???獄쏆꼶????덉삂??餓κ쑴??紐꾩뒄.",
        }],
        ["COMP-", {
            cause: "癰귣벊????온??域뱀뮇???袁⑥뺘 揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??",
            impact: "?꾨뗀諭???꾨퉸??????롮쨮 野껉퀬釉??醫롮뿯 ?袁る퓮???誘る툡筌?????됰뮸??덈뼄.",
            action: "??λ땾 ?브쑬?? ?브쑨由???λ떄?? 鈺곌퀗由?獄쏆꼹???곗쨮 癰귣벊??袁? ????紐꾩뒄.",
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
        if (!exact && ruleUpper === "UNKNOWN" && (msgLower.includes("?源낅뮟") || msgLower.includes("update"))) {
            cause = message || "獄쏆꼶???紐꾪뀱/??낅쑓??꾨뱜 ???쉘??곗쨮 ?紐낅립 ??쑵???揶쎛?關苑??揶쏅Ŋ???뤿???щ빍??";
            impact = "?븍뜇釉?酉釉??紐꾪뀱 ?袁⑹읅??곗쨮 ?臾먮뼗 筌왖??獄??귐딅꺖???????筌앹빓?揶쎛 獄쏆뮇源??????됰뮸??덈뼄.";
            action = "獄쏆꼶???紐꾪뀱???얜씈??筌ｌ꼶???띻탢??獄쏄퀣??獄쎻뫗???곗쨮 癰궰野껋?釉?? ??덉뵬 ?닌덉퍢 ?紐꾪뀱 ??쏅땾??餓κ쑴??紐꾩뒄.";
        }
    }

    if (severity === "critical") {
        impact = `${impact} (疫뀀떯??? 燁살꼶梨? 筌앸맩????륁젟 ?袁⑹뒄)`;
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleUpper || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `?癒?뵥: ${truncateMiddle(cause, 160)}`,
        impact: `?怨밸샨: ${truncateMiddle(impact, 160)}`,
        action: `亦낅슣?ｈ?怨쀭뒄: ${truncateMiddle(action, 120)} (域뱀눊援? ${evidence})`,
        raw: "",
    };
}

function renderDetailDescriptionBlocks(container, blocks) {
    const title = document.createElement("p");
    title.className = "detail-description-title";
    const titleStrong = document.createElement("strong");
    titleStrong.textContent = "??살구:";
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
    if (sev === "error") return "??살첒";
    if (sev === "information" || sev === "info") return "?類ｋ궖";
    if (sev === "performance") return "?源낅뮟";
    if (sev === "warning") return "Warning";
    if (sev === "style") return "Style";
    if (sev === "portability") return "Portability";
    return severity || "?類ｋ궖";
}

async function runWorkspaceSelection(violation, eventName, selectionToken) {
    return workspaceRunWorkspaceSelection(violation, eventName, selectionToken);
}

function createResultRow(rowData) {
    return workspaceCreateResultRow(rowData);
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
    return workspaceQueueResultTableWindowRender(force);
}

function renderWorkspaceWindow() {
    return workspaceRenderWorkspaceWindow();
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

    const ruleSeverityById = new Map();
    flattenedP1.forEach((item) => {
        const ruleId = normalizeP1RuleId(item && item.violation && item.violation.rule_id);
        if (!ruleId || ruleId === "UNKNOWN") return;
        const current = String(item && item.violation && item.violation.severity || "").trim();
        if (!current) return;
        const previous = String(ruleSeverityById.get(ruleId) || "").trim();
        if (!previous) {
            ruleSeverityById.set(ruleId, current);
            return;
        }
        ruleSeverityById.set(ruleId, pickHigherSeverity(previous, current));
    });

    const resolveReviewedSeverity = (blockSeverity, effectiveRuleId) => {
        const byRule = String(ruleSeverityById.get(normalizeP1RuleId(effectiveRuleId)) || "").trim();
        if (byRule) return byRule;
        const byBlock = String(blockSeverity || "").trim();
        if (byBlock) return byBlock;
        return "Info";
    };
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
                const displayMessage = blockMessage || "REVIEWED TODO";
                const reviewFile = basenamePath(meta.file || reviewedFile);
                const reviewKey = [
                    fileIdentityKey(reviewFile),
                    normalizeReviewedMessageKey(displayMessage),
                ].join("||");
                if (!reviewOnlyGrouped.has(reviewKey)) {
                    reviewOnlyGrouped.set(reviewKey, {
                        file: reviewFile,
                        message: displayMessage,
                        severity: resolveReviewedSeverity(block.severity, effectiveRuleId),
                        lines: [],
                        todoLines: [],
                        issueIds: [],
                        ruleIds: [],
                        states: new Set(),
                        blockIndexes: [],
                    });
                }
                const grouped = reviewOnlyGrouped.get(reviewKey);
                grouped.severity = pickHigherSeverity(
                    grouped.severity || "Info",
                    resolveReviewedSeverity(block.severity, effectiveRuleId),
                );
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
            message: grouped.message || "REVIEWED TODO",
            file: grouped.file || "",
            object: grouped.file || "Global",
            line: uniqueLines[0] || 0,
            _grouping_mode: "review_only_message",
            _group_rule_ids: uniqueRules,
            _group_messages: [grouped.message || "REVIEWED TODO"],
            _group_issue_ids: uniqueIssues,
            _duplicate_count: Math.max(1, uniqueIssues.length),
            _duplicate_lines: uniqueLines,
            _primary_line: uniqueLines[0] || 0,
            _reviewed_todo_line: uniqueTodoLines[0] || 0,
            _reviewed_todo_lines: uniqueTodoLines,
            _reviewed_original_message: grouped.message || "REVIEWED TODO",
            _reviewed_block_indexes: uniqueBlocks,
        };
        pushP1Row(synthetic, "Global", state, "reviewed", [], grouped.message || "REVIEWED TODO", "review_only");
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
    return autofixAiController.showDetail(violation, eventName, options);
}

function renderWorkspace(options = {}) {
    return workspaceRenderWorkspace(options);
}

function getSelectedFiles() {
    return workspaceGetSelectedFiles();
}

function getSelectedInputSources() {
    return workspaceGetSelectedInputSources();
}

function renderFileList(files) {
    return workspaceRenderFileList(files);
}

async function loadFiles() {
    return workspaceLoadFiles();
}

async function handleFlushExcelReportsClick() {
    if (!analysisData.output_dir) return;
    if (flushExcelBtn) {
        flushExcelBtn.disabled = true;
        flushExcelBtn.textContent = "Excel ??밴쉐 餓?..";
    }
    setExcelDownloadsExpanded(false);
    setExcelJobStatus("Excel ?귐뗫７????밴쉐 ?怨밴묶 ?類ㅼ뵥 餓?..", "#fff59d");
    try {
        const payload = await flushExcelReports({ wait: true, timeout_sec: 120 });
        analysisData.report_jobs = payload.report_jobs || {};
        analysisData.report_paths = payload.report_paths || analysisData.report_paths || {};
        analysisData.output_dir = payload.output_dir || analysisData.output_dir || "";
        if (Array.isArray((payload.report_paths || {}).excel) && payload.report_paths.excel.length) {
            setExcelDownloadsExpanded(true);
        }
        updateExcelJobUiFromAnalysis();
    } catch (err) {
        const msg = String((err && err.message) || err || "Excel flush failed");
        setExcelJobStatus(`Excel ??쎈솭: ${msg}`, "#ffcdd2");
        alert(`Excel ??밴쉐 ?袁⑥┷ 筌ｌ꼶????쎈솭: ${msg}`);
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
    if (phase === "queued") phaseLabel = "Queued";
    else if (phase === "read_source") phaseLabel = "Read source";
    else if (phase === "heuristic_review") phaseLabel = "Heuristic review";
    else if (phase === "ctrlpp_check") phaseLabel = "CtrlppCheck";
    else if (phase === "live_ai_review") phaseLabel = "Live AI";
    else if (phase === "write_reports") phaseLabel = "?귐뗫７???臾믨쉐";
    else if (phase === "analyze_file_done") phaseLabel = "???뵬 ?袁⑥┷";
    else if (phase === "analyze_file_failed") phaseLabel = "???뵬 ??쎈솭";

    if (analyzeProgressStatus) {
        const head = status === "queued" ? "Queued..." : status === "running" ? "Running..." : status === "completed" ? "Completed" : "Failed";
        const parts = [head];
        if (currentFile) parts.push(currentFile);
        if (phaseLabel) parts.push(phaseLabel);
        analyzeProgressStatus.textContent = parts.join(" 夷?");
    }
    if (analyzeProgressBar) {
        analyzeProgressBar.style.width = `${percent}%`;
    }
    if (analyzeProgressMeta) {
        const etaText = Number.isFinite(Number(etaMs)) && Number(etaMs) >= 0 ? formatDurationMs(Number(etaMs)) : "Calculating...";
        const elapsedText = Number.isFinite(Number(elapsedMs)) && Number(elapsedMs) >= 0 ? formatDurationMs(Number(elapsedMs)) : "00:00";
        analyzeProgressMeta.textContent = `${percent}% | ${completed}/${total} ???뵬 | ETA ${etaText} | 野껋럡??${elapsedText}`;
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
        report_paths: payload.report_paths || {},
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
    navWorkspace.onclick();
    void loadLatestVerificationProfile();
    void loadLatestOperationalResults();
    void loadRulesHealth();

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
            btnAnalyze.textContent = "?브쑴苑?餓?..";
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
                mode: "AI Review",
                selected_files,
                input_sources,
                allow_raw_txt: allowRawTxt,
                enable_ctrlppcheck: enableCtrlppcheck,
                enable_live_ai: enableLiveAi,
                ai_model_name: ai_model_name || undefined,
                ai_with_context: aiWithContext,
                defer_excel_reports: true,
            }),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "?브쑴苑???쎈솭");
        }

        const jobId = String(payload.job_id || "");
        if (!jobId) {
            throw new Error("?브쑴苑??臾믩씜 ID??獄쏆룇? 筌륁궢六??щ빍??");
        }
        const pollIntervalMs = Math.max(200, Number(payload.poll_interval_ms) || 500);

        for (;;) {
            const statusResp = await fetch(`/api/analyze/status?job_id=${encodeURIComponent(jobId)}`);
            const statusPayload = await statusResp.json();
            if (!statusResp.ok) {
                throw new Error(statusPayload.error || `?브쑴苑??怨밴묶 鈺곌퀬????쎈솭 (${statusResp.status})`);
            }
            updateAnalyzeProgressUi(statusPayload);
            const status = String(statusPayload.status || "");
            if (status === "completed") {
                await applyAnalyzePayload(statusPayload.result || {});
                break;
            }
            if (status === "failed") {
                throw new Error(String(statusPayload.error || "?브쑴苑???쎈솭"));
            }
            await sleepMs(pollIntervalMs);
        }
    } catch (err) {
        alert(`?브쑴苑???쎈솭: ${(err && err.message) || String(err)}`);
    } finally {
        setAnalyzeProgressVisible(false);
        if (btnAnalyze) {
            btnAnalyze.disabled = false;
            btnAnalyze.textContent = originalText || "Start Analysis";
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
    if (flushExcelBtn) {
        flushExcelBtn.addEventListener("click", () => {
            void handleFlushExcelReportsClick();
        });
    }
    if (excelDownloadToggle) {
        excelDownloadToggle.addEventListener("click", () => {
            setExcelDownloadsExpanded(!excelDownloadsExpanded);
        });
    }
    if (btnAddExternalFiles && externalFileInput) {
        btnAddExternalFiles.addEventListener("click", () => externalFileInput.click());
        externalFileInput.addEventListener("change", async () => {
            try {
                await stageExternalInputs(externalFileInput.files, "files");
            } catch (err) {
                alert(`?紐? ???뵬 ?곕떽? ??쎈솭: ${String((err && err.message) || err || "")}`);
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
                alert(`?????醫뤾문 ??쎈솭: ${String((err && err.message) || err || "")}`);
            } finally {
                externalFolderInput.value = "";
            }
        });
    }
    syncAiContextToggle();
    updateExcelJobUiFromAnalysis();
    updateDashboard();
    await loadLatestVerificationProfile();
    await loadLatestOperationalResults();
    await loadRulesHealth();
    setCodeViewerText("// ???뵬???醫뤾문??롢늺 ?癒?궚 ?꾨뗀諭?? ?袁⑥뺘 ??????類ㅼ뵥??????됰뮸??덈뼄.");
    try {
        await loadFiles();
    } catch (err) {
        alert(`???뵬 筌뤴뫖以??λ뜃由????쎈솭: ${(err && err.message) || String(err)}`);
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

