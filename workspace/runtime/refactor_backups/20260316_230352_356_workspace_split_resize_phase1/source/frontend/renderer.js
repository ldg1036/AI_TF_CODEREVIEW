import { createAutofixAiController } from "./renderer/autofix-ai.js";
import { createCodeViewerController } from "./renderer/code-viewer.js";
import { createDetailPanelController } from "./renderer/detail-panel.js";
import { createDashboardPanelsController } from "./renderer/dashboard-panels.js";
import { createRulesManageController } from "./renderer/rules-manage.js";
import { createWorkspaceController } from "./renderer/workspace-view.js";
import { createRendererShell } from "./renderer/app-shell.js";
import { createP1TriageController } from "./renderer/p1-triage.js";
import { shouldIgnoreWorkspaceShortcut, toggleWorkspacePaneVisibility } from "./renderer/workspace-interaction-helpers.js";
import { deriveInspectorActionState } from "./renderer/workspace-chrome-helpers.js";
import {
    createRendererStateSeed,
    normalizeSeverityKeyword,
    pickHigherSeverity,
    severityFilterKey,
    sourceFilterKey,
} from "./renderer/app-state.js";
import {
    basenamePath,
    buildFunctionScopes,
    compactUiText,
    countChar,
    escapeHtml,
    findScopeForLine,
    isLikelyFunctionKeyword,
    normalizeInsightToken,
    normalizeP1RuleId,
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

const { dom, elements, recordRendererError, updateRendererDiagnostics } = createRendererShell();
const {
    aiContextHelp,
    aiContextLabel,
    aiContextToggle,
    aiModelSelect,
    analyzeProgressBar,
    analyzeProgressMeta,
    analyzeProgressPanel,
    analyzeProgressStatus,
    btnAddExternalFiles,
    btnAddExternalFolder,
    btnAnalyze,
    ctrlppToggle,
    dashboardView,
    diffModalBackdrop,
    diffModalClose,
    diffModalViewSplit,
    diffModalViewUnified,
    excelDownloadList,
    excelDownloadPanel,
    excelDownloadToggle,
    excelJobStatusText,
    externalFileInput,
    externalFolderInput,
    externalInputList,
    externalInputSummary,
    flushExcelBtn,
    inspectorTabAi,
    inspectorTabDetail,
    inspectorActionAi,
    inspectorActionCompare,
    inspectorActionDetail,
    inspectorActionJump,
    liveAiToggle,
    navDashboard,
    navSettings,
    navWorkspace,
    fileTreeSidebar,
    inspectorPanel,
    workspaceCodeShell,
    workspaceCommandAi,
    workspaceCommandDetail,
    workspaceCommandJump,
    workspaceCommandNext,
    workspaceCommandPrev,
    workspaceCommandReset,
    workspaceCommandShowSuppressed,
    workspaceFileSearch,
    workspaceResultSearch,
    workspacePresetAll,
    workspacePresetP1,
    workspacePresetAttention,
    workspacePaneCode,
    workspacePaneFiles,
    workspacePaneInspector,
    workspaceSurface,
    workspaceView,
} = elements;
const {
    aiCard,
    aiCompareButtons,
    aiCompareMeta,
    aiComparePanel,
    aiComparePreview,
    aiDiffPanel,
    aiDiffText,
    aiMoreActions,
    aiPanelWrap,
    aiPrimaryActions,
    aiReviewToggleBtn,
    aiSummaryList,
    aiText,
    aiTextFull,
    aiValidationPanel,
    aiValidationText,
    analysisDiffCompare,
    btnAiMore,
    codeViewer,
    criticalText,
    dedupeSummary,
    diffModal,
    diffModalAfter,
    diffModalBefore,
    diffModalCandidates,
    diffModalMeta,
    diffModalSplit,
    diffModalSummary,
    diffModalText,
    diffModalTitle,
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
    verificationBadge,
    verificationProfileCard,
    violationDetail,
    violationDetailPanel,
    warningText,
    workspaceCommandSelectionText,
    workspaceCommandSummaryText,
    workspaceFilterSummaryText,
    workspaceQuickFilter,
    workspaceQuickFilterClear,
    workspaceQuickFilterText,
} = dom;

const rendererStateSeed = createRendererStateSeed();
let analysisData = rendererStateSeed.analysisData;
let currentViewerFile = rendererStateSeed.currentViewerFile;
let currentViewerResolvedName = rendererStateSeed.currentViewerResolvedName;
let currentViewerSource = rendererStateSeed.currentViewerSource;
let currentViewerContent = rendererStateSeed.currentViewerContent;
let currentViewerHeaderLines = rendererStateSeed.currentViewerHeaderLines;
let currentHighlightedLine = rendererStateSeed.currentHighlightedLine;
let currentHighlightedLineNear = rendererStateSeed.currentHighlightedLineNear;
let currentViewerLines = rendererStateSeed.currentViewerLines;
let activeJumpRequestState = rendererStateSeed.activeJumpRequestState;
const functionScopeCacheByFile = rendererStateSeed.functionScopeCacheByFile;
const reviewedTodoCacheByFile = rendererStateSeed.reviewedTodoCacheByFile;
const viewerContentCache = rendererStateSeed.viewerContentCache;
let workspaceRowIndex = rendererStateSeed.workspaceRowIndex;
let workspaceRenderToken = rendererStateSeed.workspaceRenderToken;
let workspaceFilteredRows = rendererStateSeed.workspaceFilteredRows;
let activeWorkspaceRowId = rendererStateSeed.activeWorkspaceRowId;
let flashedWorkspaceRowId = rendererStateSeed.flashedWorkspaceRowId;
let activeWorkspaceFlashTimer = rendererStateSeed.activeWorkspaceFlashTimer;
let codeViewerFocusTimer = rendererStateSeed.codeViewerFocusTimer;
let workspaceSelectionToken = rendererStateSeed.workspaceSelectionToken;
let activeRecommendationRowId = rendererStateSeed.activeRecommendationRowId;
let recommendationInsightByRowId = rendererStateSeed.recommendationInsightByRowId;
let workspaceRecommendationInsightByRowId = rendererStateSeed.workspaceRecommendationInsightByRowId;
let recommendationWorkspaceFilter = rendererStateSeed.recommendationWorkspaceFilter;
let workspaceUi = rendererStateSeed.workspaceUi;
let workspaceAvailableFiles = rendererStateSeed.workspaceAvailableFiles;
let workspaceSelectedFiles = rendererStateSeed.workspaceSelectedFiles;
let workspaceFileQuery = rendererStateSeed.workspaceFileQuery;
let workspaceResultQuery = rendererStateSeed.workspaceResultQuery;
let workspaceQuickPreset = rendererStateSeed.workspaceQuickPreset;
let showSuppressedP1 = rendererStateSeed.showSuppressedP1;
let p1TriageEntries = rendererStateSeed.p1TriageEntries;
let p1TriageByKey = rendererStateSeed.p1TriageByKey;
let p1TriageLoading = rendererStateSeed.p1TriageLoading;
let p1TriageError = rendererStateSeed.p1TriageError;
let excelDownloadsExpanded = rendererStateSeed.excelDownloadsExpanded;
let analysisInsights = rendererStateSeed.analysisInsights;
let workspaceAnalysisInsights = rendererStateSeed.workspaceAnalysisInsights;
const resultTableVirtualState = rendererStateSeed.resultTableVirtualState;
let resultTableRenderQueued = rendererStateSeed.resultTableRenderQueued;
const autofixProposalCache = rendererStateSeed.autofixProposalCache;
const AUTOFIX_PREPARE_MODE = rendererStateSeed.AUTOFIX_PREPARE_MODE;
let aiReviewExpanded = rendererStateSeed.aiReviewExpanded;
let activeInspectorTab = rendererStateSeed.activeInspectorTab;
let aiMoreMenuOpen = rendererStateSeed.aiMoreMenuOpen;
let sessionInputSources = rendererStateSeed.sessionInputSources;
let selectedAiModel = rendererStateSeed.selectedAiModel;
let aiModelCatalogLoaded = rendererStateSeed.aiModelCatalogLoaded;
let latestRulesHealthPayload = rendererStateSeed.latestRulesHealthPayload;
let rulesManageOpen = rendererStateSeed.rulesManageOpen;
let rulesManageLoading = rendererStateSeed.rulesManageLoading;
let rulesManageSaving = rendererStateSeed.rulesManageSaving;
let rulesManageRows = rendererStateSeed.rulesManageRows;
let rulesManageDraftById = rendererStateSeed.rulesManageDraftById;
let rulesManageEditorMode = rendererStateSeed.rulesManageEditorMode;
let rulesManageEditorRuleId = rendererStateSeed.rulesManageEditorRuleId;
let rulesManageEditorDraft = rendererStateSeed.rulesManageEditorDraft;
let rulesManageStatusMessage = rendererStateSeed.rulesManageStatusMessage;
let rulesManageImportPreview = rendererStateSeed.rulesManageImportPreview;
let rulesManageImportDraft = rendererStateSeed.rulesManageImportDraft;
let analysisDiffRunOptions = rendererStateSeed.analysisDiffRunOptions;
let selectedAnalysisDiffLatest = rendererStateSeed.selectedAnalysisDiffLatest;
let selectedAnalysisDiffPrevious = rendererStateSeed.selectedAnalysisDiffPrevious;
const codeViewerVirtualState = rendererStateSeed.codeViewerVirtualState;
let codeViewerWindowRenderQueued = rendererStateSeed.codeViewerWindowRenderQueued;
const filterControls = rendererStateSeed.filterControls;

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
    get workspaceAvailableFiles() { return workspaceAvailableFiles; },
    set workspaceAvailableFiles(value) { workspaceAvailableFiles = Array.isArray(value) ? value : []; },
    get workspaceSelectedFiles() { return workspaceSelectedFiles; },
    set workspaceSelectedFiles(value) { workspaceSelectedFiles = value instanceof Set ? value : new Set(); },
    get workspaceFileQuery() { return workspaceFileQuery; },
    set workspaceFileQuery(value) { workspaceFileQuery = String(value || ""); },
    get workspaceResultQuery() { return workspaceResultQuery; },
    set workspaceResultQuery(value) { workspaceResultQuery = String(value || ""); },
    get workspaceQuickPreset() { return workspaceQuickPreset; },
    set workspaceQuickPreset(value) { workspaceQuickPreset = String(value || "all"); },
    get showSuppressedP1() { return showSuppressedP1; },
    set showSuppressedP1(value) { showSuppressedP1 = !!value; },
    get p1TriageEntries() { return p1TriageEntries; },
    set p1TriageEntries(value) { p1TriageEntries = Array.isArray(value) ? value : []; },
    get p1TriageByKey() { return p1TriageByKey; },
    set p1TriageByKey(value) { p1TriageByKey = value instanceof Map ? value : new Map(); },
    get p1TriageLoading() { return p1TriageLoading; },
    set p1TriageLoading(value) { p1TriageLoading = !!value; },
    get p1TriageError() { return p1TriageError; },
    set p1TriageError(value) { p1TriageError = String(value || ""); },
    get workspaceUi() { return workspaceUi; },
    set workspaceUi(value) { workspaceUi = value; },
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
    get rulesManageImportDraft() { return rulesManageImportDraft; },
    set rulesManageImportDraft(value) { rulesManageImportDraft = value; },
    get rulesManageImportPreview() { return rulesManageImportPreview; },
    set rulesManageImportPreview(value) { rulesManageImportPreview = value; },
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
        buildRecommendationWorkspaceFilterText: () => workspaceBuildRecommendationWorkspaceFilterText(),
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
    appendDetailNote: detailAppendDetailNote,
    buildP1DetailBlocks: detailBuildP1DetailBlocks,
    buildP2DetailBlocks: detailBuildP2DetailBlocks,
    buildP2LocalizedMessage: detailBuildP2LocalizedMessage,
    renderDetailDescriptionBlocks: detailRenderDescriptionBlocks,
    renderInspectorSelectionMeta: detailRenderInspectorSelectionMeta,
} = detailPanelController;

const p1TriageController = createP1TriageController({
    state,
    helpers: {
        updateRendererDiagnostics,
    },
});

const {
    getViolationTriageMeta: p1TriageGetViolationTriageMeta,
    loadEntries: p1TriageLoadEntries,
    setShowSuppressedP1: p1TriageSetShowSuppressedP1,
    suppressViolation: p1TriageSuppressViolation,
    unsuppressViolation: p1TriageUnsuppressViolation,
} = p1TriageController;

const workspaceController = createWorkspaceController({
    dom,
    state,
    caches,
    virtualState,
    helpers: {
        updateDashboard: () => updateDashboard(),
        updateWorkspaceChrome: () => updateWorkspaceChrome(),
        applyPrecomputedJumpTarget,
        buildP2LocalizedMessage: (violation) => detailBuildP2LocalizedMessage(violation),
        getInspectorAiEnabled: () => !!(inspectorTabAi && !inspectorTabAi.disabled),
        jumpCodeViewerToViolation,
        loadCodeViewer,
        navWorkspace: () => navWorkspace.onclick && navWorkspace.onclick(),
        normalizeSeverityKeyword: (value) => normalizeSeverityKeyword(value),
        pendingJumpLineForViolation,
        pickHigherSeverity: (left, right) => pickHigherSeverity(left, right),
        renderExternalInputSources,
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        setActiveJumpRequestState: (status, line) => setActiveJumpRequestState(status, line),
        severityFilterKey: (value) => severityFilterKey(value),
        showDetail: (violation, eventName, options = {}) => autofixAiController.showDetail(violation, eventName, options),
        sourceFilterKey: (value) => sourceFilterKey(value),
        updateRendererDiagnostics,
        updateCodeViewerHeaderMeta,
    },
});

const {
    buildRecommendationWorkspaceFilterText: workspaceBuildRecommendationWorkspaceFilterText,
    buildWorkspaceRowIndex: workspaceBuildWorkspaceRowIndex,
    focusAdjacentWorkspaceRow: workspaceFocusAdjacentWorkspaceRow,
    getSelectedFiles: workspaceGetSelectedFiles,
    getSelectedInputSources: workspaceGetSelectedInputSources,
    initFilterControls: workspaceInitFilterControls,
    loadFiles: workspaceLoadFiles,
    openActiveWorkspaceRow: workspaceOpenActiveWorkspaceRow,
    queueResultTableWindowRender: workspaceQueueResultTableWindowRender,
    renderAnalysisInsights: workspaceRenderAnalysisInsights,
    renderWorkspaceCommandBar: workspaceRenderWorkspaceCommandBar,
    renderWorkspace: workspaceRenderWorkspace,
    renderWorkspaceFilterSummary: workspaceRenderWorkspaceFilterSummary,
    resetWorkspaceFilters: workspaceResetWorkspaceFilters,
    renderWorkspaceQuickFilter: workspaceRenderWorkspaceQuickFilter,
    setWorkspaceFileQuery: workspaceSetWorkspaceFileQuery,
    setWorkspaceQuickPreset: workspaceSetWorkspaceQuickPreset,
    setWorkspaceResultQuery: workspaceSetWorkspaceResultQuery,
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
        appendDetailNote: (container, text, tone = "") => detailAppendDetailNote(container, text, tone),
        buildAfterRowsFromProposal: (proposal) => buildAfterRowsFromProposal(proposal),
        buildIssueContextRows: (violation, radius = 3) => buildIssueContextRows(violation, radius),
        buildIssueContextRowsWithLines: (lines, targetLine, violation, radius = 4, loadError = "", options = {}) =>
            buildIssueContextRowsWithLines(lines, targetLine, violation, radius, loadError, options),
        buildP1DetailBlocks: (violation) => detailBuildP1DetailBlocks(violation),
        buildP2DetailBlocks: (violation) => detailBuildP2DetailBlocks(violation),
        buildReviewContextRows: (aiMatch) => buildReviewContextRows(aiMatch),
        compactUiText: (value, maxLength = 120) => compactUiText(value, maxLength),
        createComparePreviewColumn: (title, rows, kindClass = "") => createComparePreviewColumn(title, rows, kindClass),
        extractReviewCodeBlock: (reviewText) => extractReviewCodeBlock(reviewText),
        fetchFileContentPayload: (fileName, options = {}) => fetchFileContentPayload(fileName, options),
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
        getP1TriageMeta: (violation) => p1TriageGetViolationTriageMeta(violation),
        refreshWorkspaceAfterTriage: () => refreshWorkspaceAfterTriage(),
        renderDetailDescriptionBlocks: (container, blocks) => detailRenderDescriptionBlocks(container, blocks),
        renderInspectorSelectionMeta: (violation, options = {}) => detailRenderInspectorSelectionMeta(violation, options),
        resetInspectorTabsForViolation: (options = {}) => resetInspectorTabsForViolation(options),
        resolveDiffAnchorLine: (sourceLines, violation, aiMatch, fileName = "") => resolveDiffAnchorLine(sourceLines, violation, aiMatch, fileName),
        sameFileIdentity: (left, right) => sameFileIdentity(left, right),
        suppressP1Violation: (violation, options = {}) => p1TriageSuppressViolation(violation, options),
        setAutofixValidationPanel: (text, options = {}) => setAutofixValidationPanel(text, options),
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        sourceFilterKey: (value) => sourceFilterKey(value),
        unsuppressP1Violation: (violation) => p1TriageUnsuppressViolation(violation),
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
    renderAiEmptyState: autofixRenderAiEmptyState,
    setAutofixDiffPanel: autofixSetAutofixDiffPanel,
    setAiActionHint: autofixSetAiActionHint,
    setDiffModalView: autofixSetDiffModalView,
    setAiReviewText: autofixSetAiReviewText,
    setAiStatusInline: autofixSetAiStatusInline,
    showDetail: autofixShowDetail,
    syncAiMoreMenuUi: autofixSyncAiMoreMenuUi,
} = autofixAiController;

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

function setActivePrimaryView(viewName) {
    const activeView = String(viewName || "").trim().toLowerCase();
    [
        [navDashboard, activeView === "dashboard"],
        [navWorkspace, activeView === "workspace"],
    ].forEach(([button, isActive]) => {
        if (!button) return;
        button.classList.toggle("is-active", !!isActive);
        if (isActive) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });
}

navDashboard.onclick = () => {
    dashboardView.style.display = "block";
    workspaceView.style.display = "none";
    setActivePrimaryView("dashboard");
};

navWorkspace.onclick = () => {
    dashboardView.style.display = "none";
    workspaceView.style.display = "flex";
    setActivePrimaryView("workspace");
    updateWorkspaceChrome();
    queueCodeViewerWindowRender(true);
};

if (navSettings) {
    navSettings.disabled = true;
    navSettings.setAttribute("aria-disabled", "true");
    navSettings.title = "현재 설정은 상단 분석 제어 영역에서 바로 조정합니다.";
}

function updateWorkspacePaneUi() {
    const panes = (state.workspaceUi && state.workspaceUi.paneVisibility) || {};
    const filesOpen = panes.files !== false;
    const codeOpen = panes.code !== false;
    const inspectorOpen = panes.inspector !== false;
    fileTreeSidebar?.classList.toggle("is-collapsed", !filesOpen);
    workspaceCodeShell?.classList.toggle("is-collapsed", !codeOpen);
    workspaceSurface?.classList.toggle("is-code-collapsed", !codeOpen);
    inspectorPanel?.classList.toggle("is-collapsed", !inspectorOpen);
    if (workspacePaneFiles) workspacePaneFiles.setAttribute("aria-pressed", filesOpen ? "true" : "false");
    if (workspacePaneCode) workspacePaneCode.setAttribute("aria-pressed", codeOpen ? "true" : "false");
    if (workspacePaneInspector) workspacePaneInspector.setAttribute("aria-pressed", inspectorOpen ? "true" : "false");
}

function updateInspectorActionStrip() {
    const hasActiveSelection = !!String(state.activeWorkspaceRowId || "").trim();
    const aiEnabled = !!(inspectorTabAi && !inspectorTabAi.disabled);
    const compareBtn = document.getElementById("btn-ai-diff");
    const actionState = deriveInspectorActionState({
        hasActiveSelection,
        aiEnabled,
        compareEnabled: !!(compareBtn && !compareBtn.disabled),
        activeInspectorTab,
    });
    if (workspaceCommandJump) workspaceCommandJump.disabled = actionState.jumpDisabled;
    if (workspaceCommandDetail) {
        workspaceCommandDetail.disabled = actionState.detailDisabled;
        workspaceCommandDetail.setAttribute("aria-pressed", actionState.detailPressed ? "true" : "false");
        workspaceCommandDetail.title = actionState.detailTitle;
    }
    if (workspaceCommandAi) {
        workspaceCommandAi.disabled = actionState.aiDisabled;
        workspaceCommandAi.setAttribute("aria-pressed", actionState.aiPressed ? "true" : "false");
        workspaceCommandAi.title = actionState.aiTitle;
    }
    if (workspaceCommandJump) workspaceCommandJump.title = actionState.jumpTitle;
    if (inspectorActionJump) {
        inspectorActionJump.disabled = actionState.jumpDisabled;
        inspectorActionJump.title = actionState.jumpTitle;
    }
    if (inspectorActionDetail) {
        inspectorActionDetail.disabled = actionState.detailDisabled;
        inspectorActionDetail.setAttribute("aria-pressed", actionState.detailPressed ? "true" : "false");
        inspectorActionDetail.title = actionState.detailTitle;
    }
    if (inspectorActionAi) {
        inspectorActionAi.disabled = actionState.aiDisabled;
        inspectorActionAi.setAttribute("aria-pressed", actionState.aiPressed ? "true" : "false");
        inspectorActionAi.title = actionState.aiTitle;
    }
    if (inspectorActionCompare) {
        inspectorActionCompare.disabled = actionState.compareDisabled;
        inspectorActionCompare.title = actionState.compareTitle;
    }
}

function updateWorkspaceChrome() {
    updateWorkspacePaneUi();
    workspaceRenderWorkspaceCommandBar();
    updateInspectorActionStrip();
}

function refreshWorkspaceAfterTriage() {
    workspaceBuildWorkspaceRowIndex();
    workspaceRenderWorkspace({ autoSelect: true, resetScroll: false });
    updateWorkspaceChrome();
}

function toggleWorkspacePane(paneName) {
    state.workspaceUi = {
        ...(state.workspaceUi || {}),
        paneVisibility: toggleWorkspacePaneVisibility((state.workspaceUi && state.workspaceUi.paneVisibility) || {}, paneName),
    };
    updateWorkspacePaneUi();
    queueCodeViewerWindowRender(true);
    workspaceQueueResultTableWindowRender(true);
}

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
        const contextEnabled = !!(aiContextToggle && aiContextToggle.checked);
        if (!liveEnabled) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "Turn on Live AI to request MCP-backed context.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }
        if (!contextEnabled) {
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
            aiContextHelp.title = `MCP context loaded for this review in ${Math.round(mcpMs)}ms. Hover to confirm that extra context was attached to the Live AI request.`;
        } else {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "MCP context is enabled, but no attached context timing was reported for the latest Live AI request.";
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
    aiModelSelect.innerHTML = '<option value="">Loading models...</option>';
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
            const errorText = String(payload.error || "Could not load the Ollama model catalog.");
            aiContextHelp.textContent = "Model status: fallback";
            aiContextHelp.title = errorText + " Using the fallback model list instead.";
        }
    } catch (err) {
        aiModelCatalogLoaded = false;
        aiModelSelect.disabled = true;
        if (aiContextHelp && liveAiToggle && liveAiToggle.checked) {
            const message = String((err && err.message) || err || "");
            aiContextHelp.textContent = "Model status: catalog load failed";
            aiContextHelp.title = "Model catalog request failed: " + message;
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
    updateInspectorActionStrip();
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
        const fallback = compactUiText(String((violation && violation.message) || "").trim(), 220) || "No nearby source context is available for this message.";
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
            ? `Could not load source context: ${loadError}`
            : "No source context is available for this issue.";
        return [{ lineNo: 0, text: fallback, kind: "placeholder" }];
    }
    if (preferredLine <= 0) {
        return [{ lineNo: 0, text: "No exact line match is available, so only a placeholder preview can be shown.", kind: "placeholder" }];
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
    const preferredText = codeBlock || reviewText || "No P3 review text is available yet.";
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
        : [{ lineNo: 0, text: "No preview rows are available yet.", kind: "placeholder" }];
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
        flushExcelBtn.textContent = (pending > 0 || running > 0) ? "Flush Excel queue" : "Flush Excel queue";
    }
    if (!hasSession) {
        setExcelJobStatus("");
        renderExcelDownloadList();
        return;
    }
    if (!excelAvailable) {
        setExcelJobStatus("openpyxl unavailable", "#ffcdd2");
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
    if (pending > 0) statusParts.push(`pending ${pending}`);
    if (running > 0) statusParts.push(`running ${running}`);
    if (failed > 0) statusParts.push(`failed ${failed}`);
    const color = failed > 0 ? "#ffcdd2" : (pending > 0 || running > 0) ? "#fff59d" : "#c8e6c9";
    setExcelJobStatus(statusParts.join(" | "), color);
    renderExcelDownloadList();
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

function jumpFailureMessage(jumpResult) {
    if (!jumpResult || jumpResult.ok) return "";
    const reason = String(jumpResult.reason || "");
    if (reason === "reviewed-anchor-miss") return "Could not find the REVIEWED TODO anchor. The source may have changed since the review was generated.";
    if (reason === "source-line-miss") return "Could not find the requested line in the source file. Confirm that the file still matches the analyzed revision.";
    if (reason === "file-load-miss") return "Could not reload the target file. Check the file path and session state.";
    if (reason === "no-locatable-position") return "There is not enough line/file information to calculate a jump target.";
    if (reason === "load-source-failed") return "Failed to reopen the P2 source .ctl file.";
    if (reason === "source-not-found") return "The target .ctl source file could not be found.";
    if (reason === "invalid-target-file") return "The P2 result points to an invalid target file path.";
    if (reason === "cross-file") return "This result points to a different file, so inline jump is not available.";
    if (reason === "load-failed") return "The selected file could not be reloaded.";
    if (reason === "no-viewer") return "The code viewer is not ready yet. Select the file again and retry.";
    if (reason === "no-match-reviewed") return "The REVIEWED.txt entry could not be matched to the current analysis result. Message text or nearby context may have changed.";
    return "An error occurred while calculating the jump target for this item.";
}

function localizeCtrlppMessage(message) {
    const text = String(message || "");
    if (!text) return text;

    let out = text;
    out = out.replace(/^Uninitialized variable:\s*(.+)$/i, "Uninitialized variable: $1");
    out = out.replace(/^It is potentially a safety issue to use the function\s+(.+)$/i, "Using function $1 may introduce a safety issue.");
    out = out.replace(/^It is really neccessary to use the function\s+(.+)$/i, "Please confirm that function $1 is really required here.");
    out = out.replace(/^It is really necessary to use the function\s+(.+)$/i, "Please confirm that function $1 is really required here.");
    out = out.replace(/^Cppcheck cannot find all the include files \(use --check-config for details\)$/i, "Cppcheck could not find every include file. Review the --check-config output for details.");
    return out;
}

function localizeCtrlppByRuleId(ruleId, message, verbose) {
    const id = String(ruleId || "").toLowerCase();
    const msg = String(message || "");
    const details = String(verbose || "");
    const mapping = [
        { keys: ["uninitializedvariable", "uninitvar"], text: "This may use an uninitialized variable." },
        { keys: ["nullpointer", "nullpointerdereference"], text: "This may dereference a null pointer." },
        { keys: ["checklibrarynoreturn", "noreturn"], text: "Please verify the use of a no-return function." },
        { keys: ["memleak", "resourceleak"], text: "This may leak memory or another resource." },
        { keys: ["unusedfunction", "unusedvariable"], text: "There may be an unused function or variable." },
        { keys: ["syntaxerror", "parseerror"], text: "This may contain a syntax or parse error." },
        { keys: ["bufferaccessoutofbounds", "outofbounds"], text: "This may access a buffer or array out of bounds." },
        { keys: ["useafterfree"], text: "This may use memory after it was freed." },
        { keys: ["shadowvariable", "shadowedvariable"], text: "This may shadow another variable." },
    ];
    for (const entry of mapping) {
        if (entry.keys.some((k) => id.includes(k))) return entry.text;
    }
    if (id === "ctrlppcheck.info") {
        const localized = localizeCtrlppMessage(msg || details);
        return localized || "CtrlppCheck informational message.";
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
        return name ? `Variable ${name} may be used while null.` : "A null pointer issue may exist here.";
    }
    const callMatch = text.match(/function\s+([A-Za-z_][A-Za-z0-9_]*)/i);
    if (callMatch) return `Please confirm that calling function ${callMatch[1]} is necessary and safe.`;
    const varMatch = text.match(/variable:\s*([A-Za-z_][A-Za-z0-9_]*)/i);
    if (varMatch) return `Please review how variable ${varMatch[1]} is used.`;
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

    const cause = localized.localizedText || "P2 issue reported by CtrlppCheck.";
    const impactMap = {
        error: "This issue may lead to runtime failures or incorrect control behavior.",
        warning: "This issue may reduce reliability or make failures harder to diagnose.",
        performance: "This issue may add avoidable overhead or repeated work at runtime.",
        information: "This item is informational, but it may still indicate code that deserves a closer look.",
        style: "This issue affects consistency and can make future maintenance harder.",
        portability: "This issue may behave differently across environments or deployments.",
    };
    const impact = impactMap[severity] || "This issue may affect reliability, readability, or runtime behavior.";

    let action = "Review the related code path, confirm the warning is still valid, and decide whether to fix, suppress, or document it.";
    const lowerRule = ruleId.toLowerCase();
    if (lowerRule.includes("uninitialized")) {
        action = "Initialize the variable on every path before use, or refactor so the variable cannot be read before assignment.";
    } else if (lowerRule.includes("null")) {
        action = "Add a null guard, validate upstream assumptions, or refactor so the value cannot be null at this point.";
    } else if (lowerRule.includes("noreturn")) {
        action = "Confirm that the called function really does not return and that the surrounding flow matches that assumption.";
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleId || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `Cause: ${cause}`,
        impact: `Impact: ${impact}`,
        action: `Action: ${action} (${evidence})`,
        raw: localized.rawText ? `Raw: ${truncateMiddle(localized.rawText, 180)}` : "",
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

    let cause = message || "A P1 rule matched this code path.";
    let impact = "This issue may affect maintainability, consistency, or runtime safety if left unresolved.";
    let action = "Review the flagged code, confirm the intent, and update the implementation or rule configuration as needed.";

    const prefixTemplates = [
        ["PERF-", {
            impact: "This issue may create avoidable runtime cost or repeated work.",
            action: "Reduce repeated calls, batch operations when possible, and validate hot paths with realistic data.",
        }],
        ["SEC-", {
            impact: "This issue may weaken validation or expose a risky execution path.",
            action: "Validate inputs, encode or escape data where required, and narrow the risky path before deployment.",
        }],
        ["DB-", {
            impact: "This issue may increase database cost or make query behavior harder to control.",
            action: "Review the query path, reduce unnecessary calls, and verify indexes or batching strategy.",
        }],
        ["SAFE-", {
            impact: "This issue may allow an avoidable runtime error or unsafe state transition.",
            action: "Add explicit guards and validate assumptions before the risky operation executes.",
        }],
        ["VAL-", {
            impact: "This issue may allow invalid input or unchecked state to flow deeper into the program.",
            action: "Tighten validation near the entry point and fail early when required data is missing or malformed.",
        }],
        ["LOG-", {
            impact: "This issue may reduce observability or make diagnostics noisier than necessary.",
            action: "Adjust log level, message quality, and logging volume so operators can act on the output.",
        }],
        ["CLEAN-", {
            impact: "This issue may leave dead, duplicated, or noisy code in place and slow future maintenance.",
            action: "Remove duplicate or dead code, simplify the flow, and keep the intent of the remaining path explicit.",
        }],
        ["HARD-", {
            impact: "This issue may hard-code assumptions that become fragile when configuration or deployment changes.",
            action: "Move fixed values into configuration or shared constants and document the dependency clearly.",
        }],
        ["CFG-", {
            impact: "This issue may cause configuration mismatches or make behavior harder to predict.",
            action: "Verify the related config keys, defaults, and error handling for missing or invalid values.",
        }],
        ["STYLE-", {
            impact: "This issue mainly affects readability and long-term consistency.",
            action: "Apply the local naming, formatting, or header conventions so future reviews stay predictable.",
        }],
        ["EXC-", {
            impact: "This issue may hide errors or make exception handling incomplete.",
            action: "Review the exception path, make failure handling explicit, and avoid swallowing important context.",
        }],
        ["ACTIVE-", {
            impact: "This issue may leave behavior enabled or active when the surrounding state suggests otherwise.",
            action: "Re-check the enable/active conditions and make the activation logic explicit.",
        }],
        ["DUP-", {
            impact: "This issue may duplicate behavior and create drift between similar code paths.",
            action: "Merge repeated logic, extract the shared path, and remove the extra branch when possible.",
        }],
        ["COMP-", {
            impact: "This issue may increase complexity and make the control flow harder to reason about.",
            action: "Break the logic into smaller pieces and make the relationship between the checks more explicit.",
        }],
    ];

    for (const [prefix, template] of prefixTemplates) {
        if (ruleUpper.startsWith(prefix)) {
            impact = template.impact;
            action = template.action;
            break;
        }
    }

    if (severity === "critical") {
        impact = `${impact} This item is marked critical, so it should be reviewed before lower-severity cleanup.`;
    }

    const evidenceParts = [];
    if (fileName) evidenceParts.push(fileName);
    if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
    evidenceParts.push(`rule_id=${ruleUpper || "unknown"}`);
    const evidence = evidenceParts.join(", ");

    return {
        cause: `Cause: ${cause}`,
        impact: `Impact: ${impact}`,
        action: `Action: ${action} (${evidence})`,
        raw: message ? `Raw: ${truncateMiddle(message, 180)}` : "",
    };
}

function renderDetailDescriptionBlocks(container, blocks) {
    const title = document.createElement("p");
    title.className = "detail-description-title";
    const titleStrong = document.createElement("strong");
    titleStrong.textContent = "Summary:";
    title.appendChild(titleStrong);
    container.appendChild(title);

    [blocks.cause, blocks.impact, stripDetailEvidence(blocks.action)].forEach((line) => {
        const p = document.createElement("p");
        p.className = "detail-description-line";
        p.textContent = line;
        container.appendChild(p);
    });
}

function attachResultTableVirtualScrollHandler() {
    if (!resultTableWrap || resultTableVirtualState.scrollAttached) return;
    resultTableWrap.addEventListener("scroll", () => {
        workspaceQueueResultTableWindowRender();
    });
    resultTableVirtualState.scrollAttached = true;
}

function getResultTableBodyOffset() {
    if (!resultTableWrap || !resultBody) return 0;
    const wrapRect = resultTableWrap.getBoundingClientRect();
    const bodyRect = resultBody.getBoundingClientRect();
    return Math.max(0, (bodyRect.top - wrapRect.top) + resultTableWrap.scrollTop);
}

async function handleFlushExcelReportsClick() {
    if (!analysisData.output_dir) return;
    if (flushExcelBtn) {
        flushExcelBtn.disabled = true;
        flushExcelBtn.textContent = "Flushing Excel...";
    }
    setExcelDownloadsExpanded(false);
    setExcelJobStatus("Excel flush is running. Please wait...", "#fff59d");
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
        setExcelJobStatus(`Excel flush failed: ${msg}`, "#ffcdd2");
        alert(`Excel flush failed: ${msg}`);
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
    updateRendererDiagnostics({ progress_panel_visible: !!visible });
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
    else if (phase === "write_reports") phaseLabel = "Write reports";
    else if (phase === "analyze_file_done") phaseLabel = "File complete";
    else if (phase === "analyze_file_failed") phaseLabel = "File failed";

    if (analyzeProgressStatus) {
        const head = status === "queued" ? "Queued..." : status === "running" ? "Running..." : status === "completed" ? "Completed" : "Failed";
        const parts = [head];
        if (currentFile) parts.push(currentFile);
        if (phaseLabel) parts.push(phaseLabel);
        analyzeProgressStatus.textContent = parts.join(" | ");
    }
    if (analyzeProgressBar) {
        analyzeProgressBar.style.width = `${percent}%`;
    }
    if (analyzeProgressMeta) {
        const etaText = Number.isFinite(Number(etaMs)) && Number(etaMs) >= 0 ? formatDurationMs(Number(etaMs)) : "Calculating...";
        const elapsedText = Number.isFinite(Number(elapsedMs)) && Number(elapsedMs) >= 0 ? formatDurationMs(Number(elapsedMs)) : "00:00";
        analyzeProgressMeta.textContent = `${percent}% | ${completed}/${total} files | ETA ${etaText} | Elapsed ${elapsedText}`;
    }
    updateRendererDiagnostics({
        progress_panel_visible: !!(analyzeProgressPanel && analyzeProgressPanel.style.display !== "none"),
        progress_status_text: analyzeProgressStatus ? String(analyzeProgressStatus.textContent || "") : "",
        progress_meta_text: analyzeProgressMeta ? String(analyzeProgressMeta.textContent || "") : "",
    });
}

async function applyAnalyzePayload(payload) {
    await p1TriageLoadEntries();
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
    autofixSetAutofixDiffPanel("");
    setAutofixValidationPanel("");
    autofixCloseDiffModal();
    const selected = workspaceGetSelectedFiles();
    await prepareFunctionScopeCacheForSelectedFiles(selected);
    workspaceBuildWorkspaceRowIndex();

    workspaceRenderWorkspace();
    updateWorkspaceChrome();
    updateRendererDiagnostics({
        analyze_status: "completed",
        analyze_error: "",
        selected_file_count: selected.length,
        result_row_count: Array.isArray(workspaceFilteredRows) ? workspaceFilteredRows.length : 0,
        last_analyze_result_summary: {
            total: Number((analysisData.summary && analysisData.summary.total) || 0),
            critical: Number((analysisData.summary && analysisData.summary.critical) || 0),
            warning: Number((analysisData.summary && analysisData.summary.warning) || 0),
            info: Number((analysisData.summary && analysisData.summary.info) || 0),
            score: Number((analysisData.summary && analysisData.summary.score) || 0),
        },
    });
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
        const selected_files = workspaceGetSelectedFiles();
        const input_sources = workspaceGetSelectedInputSources();
        const ai_model_name = enableLiveAi ? (selectedAiModel || (aiModelSelect && aiModelSelect.value) || "") : "";
        const totalRequestedCount = selected_files.length + input_sources.length;
        if (typeof window !== "undefined") {
            window.__lastRendererError = null;
        }
        updateRendererDiagnostics({
            analyze_status: "queued",
            analyze_error: "",
            selected_file_count: selected_files.length,
            selected_input_source_count: input_sources.length,
            result_row_count: 0,
        });

        if (btnAnalyze) {
            btnAnalyze.disabled = true;
            btnAnalyze.textContent = "Analyzing...";
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
            throw new Error(payload.error || "Analyze request failed");
        }
        updateRendererDiagnostics({
            analyze_status: "accepted",
            analyze_job_id: String(payload.job_id || ""),
            analyze_poll_interval_ms: Math.max(200, Number(payload.poll_interval_ms) || 500),
        });

        const jobId = String(payload.job_id || "");
        if (!jobId) {
            throw new Error("Analyze job id is missing from the response.");
        }
        const pollIntervalMs = Math.max(200, Number(payload.poll_interval_ms) || 500);

        for (;;) {
            const statusResp = await fetch(`/api/analyze/status?job_id=${encodeURIComponent(jobId)}`);
            const statusPayload = await statusResp.json();
            if (!statusResp.ok) {
                throw new Error(statusPayload.error || `Analyze status poll failed (${statusResp.status})`);
            }
            updateAnalyzeProgressUi(statusPayload);
            const status = String(statusPayload.status || "");
            updateRendererDiagnostics({
                analyze_status: status || "running",
                last_analyze_progress: statusPayload.progress || {},
                last_analyze_poll: {
                    status,
                    request_id: String(statusPayload.request_id || ""),
                },
            });
            if (status === "completed") {
                await applyAnalyzePayload(statusPayload.result || {});
                break;
            }
            if (status === "failed") {
                throw new Error(String(statusPayload.error || "Analyze job failed"));
            }
            await sleepMs(pollIntervalMs);
        }
    } catch (err) {
        recordRendererError(err);
        updateRendererDiagnostics({
            analyze_status: "failed",
            analyze_error: (err && err.message) || String(err),
        });
        alert(`Analysis failed: ${(err && err.message) || String(err)}`);
    } finally {
        setAnalyzeProgressVisible(false);
        updateRendererDiagnostics({
            progress_panel_visible: false,
            result_row_count: Array.isArray(workspaceFilteredRows) ? workspaceFilteredRows.length : 0,
        });
        if (btnAnalyze) {
            btnAnalyze.disabled = false;
            btnAnalyze.textContent = originalText || "Start Analysis";
        }
    }
};

window.addEventListener("DOMContentLoaded", async () => {
    updateRendererDiagnostics({ boot_status: "domcontentloaded" });
    await p1TriageLoadEntries();
    workspaceInitFilterControls();
    attachResultTableVirtualScrollHandler();
    workspaceRenderWorkspaceQuickFilter();
    workspaceRenderWorkspaceCommandBar();
    updateWorkspacePaneUi();
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
    autofixSyncAiMoreMenuUi();
    if (aiReviewToggleBtn) {
        aiReviewToggleBtn.addEventListener("click", () => {
            aiReviewExpanded = !aiReviewExpanded;
            const currentFull = (aiTextFull && aiTextFull.textContent) ? aiTextFull.textContent : "";
            autofixSetAiReviewText(currentFull);
        });
    }
    if (diffModalBackdrop) {
        diffModalBackdrop.addEventListener("click", autofixCloseDiffModal);
    }
    if (diffModalClose) {
        diffModalClose.addEventListener("click", autofixCloseDiffModal);
    }
    if (diffModalViewSplit) {
        diffModalViewSplit.addEventListener("click", () => autofixSetDiffModalView("split"));
    }
    if (diffModalViewUnified) {
        diffModalViewUnified.addEventListener("click", () => autofixSetDiffModalView("unified"));
    }
    if (workspaceCommandPrev) {
        workspaceCommandPrev.addEventListener("click", () => {
            void workspaceFocusAdjacentWorkspaceRow(-1);
        });
    }
    if (workspaceCommandNext) {
        workspaceCommandNext.addEventListener("click", () => {
            void workspaceFocusAdjacentWorkspaceRow(1);
        });
    }
    if (workspaceCommandJump) {
        workspaceCommandJump.addEventListener("click", () => {
            void workspaceOpenActiveWorkspaceRow();
        });
    }
    if (workspaceCommandDetail) {
        workspaceCommandDetail.addEventListener("click", () => {
            setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
        });
    }
    if (workspaceCommandAi) {
        workspaceCommandAi.addEventListener("click", () => {
            if (inspectorTabAi && !inspectorTabAi.disabled) {
                setInspectorTab("ai", true);
            }
        });
    }
    if (workspaceCommandReset) {
        workspaceCommandReset.addEventListener("click", () => workspaceResetWorkspaceFilters());
    }
    if (workspaceCommandShowSuppressed) {
        workspaceCommandShowSuppressed.addEventListener("change", () => {
            p1TriageSetShowSuppressedP1(!!workspaceCommandShowSuppressed.checked);
            workspaceRenderWorkspace({ autoSelect: true, resetScroll: false });
            updateWorkspaceChrome();
        });
    }
    if (workspaceFileSearch) {
        workspaceFileSearch.addEventListener("input", (event) => {
            workspaceSetWorkspaceFileQuery(event.target && event.target.value ? event.target.value : "");
        });
    }
    if (workspaceResultSearch) {
        workspaceResultSearch.addEventListener("input", (event) => {
            workspaceSetWorkspaceResultQuery(event.target && event.target.value ? event.target.value : "");
        });
    }
    if (workspacePresetAll) {
        workspacePresetAll.addEventListener("click", () => workspaceSetWorkspaceQuickPreset("all"));
    }
    if (workspacePresetP1) {
        workspacePresetP1.addEventListener("click", () => workspaceSetWorkspaceQuickPreset("p1_only"));
    }
    if (workspacePresetAttention) {
        workspacePresetAttention.addEventListener("click", () => workspaceSetWorkspaceQuickPreset("attention_only"));
    }
    if (workspacePaneFiles) {
        workspacePaneFiles.addEventListener("click", () => toggleWorkspacePane("files"));
    }
    if (workspacePaneCode) {
        workspacePaneCode.addEventListener("click", () => toggleWorkspacePane("code"));
    }
    if (workspacePaneInspector) {
        workspacePaneInspector.addEventListener("click", () => toggleWorkspacePane("inspector"));
    }
    if (inspectorActionJump) {
        inspectorActionJump.addEventListener("click", () => {
            void workspaceOpenActiveWorkspaceRow();
        });
    }
    if (inspectorActionDetail) {
        inspectorActionDetail.addEventListener("click", () => {
            setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
        });
    }
    if (inspectorActionAi) {
        inspectorActionAi.addEventListener("click", () => {
            if (inspectorTabAi && !inspectorTabAi.disabled) {
                setInspectorTab("ai", true);
            }
        });
    }
    if (inspectorActionCompare) {
        inspectorActionCompare.addEventListener("click", () => {
            const compareBtn = document.getElementById("btn-ai-diff");
            if (compareBtn && !compareBtn.disabled) {
                compareBtn.click();
            }
        });
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
                alert(`외부 파일을 추가하지 못했습니다: ${String((err && err.message) || err || "")}`);
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
                alert(`외부 폴더를 추가하지 못했습니다: ${String((err && err.message) || err || "")}`);
            } finally {
                externalFolderInput.value = "";
            }
        });
    }
    syncAiContextToggle();
    setActivePrimaryView("dashboard");
    updateExcelJobUiFromAnalysis();
    updateDashboard();
    await loadLatestVerificationProfile();
    await loadLatestOperationalResults();
    await loadRulesHealth();
    setCodeViewerText("// 파일을 선택하면 원본 코드와 검토 세부 정보를 여기에 표시합니다.");
    try {
        await workspaceLoadFiles();
        updateRendererDiagnostics({ boot_status: "ready" });
        updateWorkspaceChrome();
    } catch (err) {
        recordRendererError(err);
        updateRendererDiagnostics({
            boot_status: "file_load_failed",
            file_list_status: "load_failed",
        });
        alert(`파일 목록을 불러오지 못했습니다: ${(err && err.message) || String(err)}`);
    }
});

window.addEventListener("resize", () => {
    queueCodeViewerWindowRender(true);
    workspaceQueueResultTableWindowRender(true);
});

window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && diffModal && !diffModal.classList.contains("hidden")) {
        autofixCloseDiffModal();
        return;
    }
    if (!workspaceView || workspaceView.style.display === "none") return;
    if (shouldIgnoreWorkspaceShortcut(event)) return;

    if (event.key === "ArrowDown" || event.key === "j" || event.key === "J" || event.key === "]") {
        event.preventDefault();
        void workspaceFocusAdjacentWorkspaceRow(1);
        return;
    }
    if (event.key === "ArrowUp" || event.key === "k" || event.key === "K" || event.key === "[") {
        event.preventDefault();
        void workspaceFocusAdjacentWorkspaceRow(-1);
        return;
    }
    if (event.key === "Enter") {
        event.preventDefault();
        void workspaceOpenActiveWorkspaceRow();
        return;
    }
    if (event.key === "d" || event.key === "D") {
        event.preventDefault();
        setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
        return;
    }
    if (event.key === "a" || event.key === "A") {
        if (inspectorTabAi && !inspectorTabAi.disabled) {
            event.preventDefault();
            setInspectorTab("ai", true);
        }
    }
});

