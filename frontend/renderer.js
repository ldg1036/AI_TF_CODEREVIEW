import { createAutofixAiController } from "./renderer/autofix-ai.js";
import { bindRendererDomContentLoaded } from "./renderer/bootstrap-event-bindings.js";
import { bindRendererGlobalShortcuts } from "./renderer/bootstrap-global-shortcuts.js";
import { createAnalyzeRunController } from "./renderer/bootstrap-load-sequence.js";
import { createCodeViewerController } from "./renderer/code-viewer.js";
import { createDetailPanelController } from "./renderer/detail-panel.js";
import { createDashboardPanelsController } from "./renderer/dashboard-panels.js";
import { createExcelJobsController } from "./renderer/excel-jobs.js";
import { createRendererUiChromeController } from "./renderer/renderer-ui-chrome.js";
import { createRulesManageController } from "./renderer/rules-manage.js";
import { createWorkspaceController } from "./renderer/workspace-view.js";
import { createRendererShell } from "./renderer/app-shell.js";
import { createP1TriageController } from "./renderer/p1-triage.js";
import { buildPrimaryViewState } from "./renderer/primary-view-helpers.js";
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
    dashboardOpenSettings,
    settingsView,
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
    workspaceResizer,
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
    renderDetailEvidence: detailRenderEvidence,
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
        renderExternalInputSources: () => renderExternalInputSources(),
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        setActiveJumpRequestState: (status, line) => setActiveJumpRequestState(status, line),
        severityFilterKey: (value) => severityFilterKey(value),
        showDetail: (violation, eventName, options = {}) => autofixAiController.showDetail(violation, eventName, options),
        sourceFilterKey: (value) => sourceFilterKey(value),
        queueCodeViewerWindowRender: (force = false) => queueCodeViewerWindowRender(force),
        updateRendererDiagnostics,
        updateCodeViewerHeaderMeta,
    },
});

const {
    applyWorkspaceCodePaneHeight: workspaceApplyCodePaneHeight,
    attachResultTableVirtualScrollHandler: workspaceAttachResultTableVirtualScrollHandler,
    bindWorkspaceResizer,
    buildRecommendationWorkspaceFilterText: workspaceBuildRecommendationWorkspaceFilterText,
    buildWorkspaceRowIndex: workspaceBuildWorkspaceRowIndex,
    focusAdjacentWorkspaceRow: workspaceFocusAdjacentWorkspaceRow,
    getSelectedFiles: workspaceGetSelectedFiles,
    getSelectedInputSources: workspaceGetSelectedInputSources,
    initFilterControls: workspaceInitFilterControls,
    loadFiles: workspaceLoadFiles,
    openActiveWorkspaceRow: workspaceOpenActiveWorkspaceRow,
    queueResultTableWindowRender: workspaceQueueResultTableWindowRender,
    refreshWorkspaceSplitLayout: workspaceRefreshSplitLayout,
    renderAnalysisInsights: workspaceRenderAnalysisInsights,
    renderWorkspaceCommandBar: workspaceRenderWorkspaceCommandBar,
    renderWorkspace: workspaceRenderWorkspace,
    renderWorkspaceFilterSummary: workspaceRenderWorkspaceFilterSummary,
    resetWorkspaceFilters: workspaceResetWorkspaceFilters,
    renderWorkspaceQuickFilter: workspaceRenderWorkspaceQuickFilter,
    setWorkspaceFileQuery: workspaceSetWorkspaceFileQuery,
    setWorkspaceCodePaneHeight: workspaceSetWorkspaceCodePaneHeight,
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
        renderDetailEvidence: (container, violation) => detailRenderEvidence(container, violation),
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

const uiChromeController = createRendererUiChromeController({
    dom,
    state,
    elements,
    helpers: {
        basenamePath: (value) => basenamePath(value),
        buildPrimaryViewState: (viewName) => buildPrimaryViewState(viewName),
        deriveInspectorActionState: (options) => deriveInspectorActionState(options),
        loadAiModels: () => loadAiModels(),
        queueCodeViewerWindowRender: (force = false) => queueCodeViewerWindowRender(force),
        toggleWorkspacePaneVisibility: (panes, paneName) => toggleWorkspacePaneVisibility(panes, paneName),
        updateRendererDiagnostics,
        workspaceBuildWorkspaceRowIndex: () => workspaceBuildWorkspaceRowIndex(),
        workspaceRefreshSplitLayout: (options = {}) => workspaceRefreshSplitLayout(options),
        workspaceRenderWorkspace: (options = {}) => workspaceRenderWorkspace(options),
        workspaceRenderWorkspaceCommandBar: () => workspaceRenderWorkspaceCommandBar(),
    },
});

const {
    bindPrimaryNavigation,
    refreshWorkspaceAfterTriage,
    renderExternalInputSources,
    setActivePrimaryView,
    syncAiContextToggle,
    toggleWorkspaceAdvanced,
    toggleWorkspacePane,
    updateAiContextHelpText,
    updateInspectorActionStrip,
    updateWorkspaceChrome,
    updateWorkspacePaneUi,
} = uiChromeController;

const excelJobsController = createExcelJobsController({
    elements,
    state,
});

const {
    handleFlushExcelReportsClick,
    setExcelDownloadsExpanded,
    setExcelJobStatus,
    updateExcelJobUiFromAnalysis,
} = excelJobsController;

const analyzeRunController = createAnalyzeRunController({
    elements,
    state,
    caches,
    helpers: {
        autofixCloseDiffModal: () => autofixCloseDiffModal(),
        autofixSetAutofixDiffPanel: (text) => autofixSetAutofixDiffPanel(text),
        loadCodeViewer: (fileName, options = {}) => loadCodeViewer(fileName, options),
        loadLatestOperationalResults: () => loadLatestOperationalResults(),
        loadLatestVerificationProfile: () => loadLatestVerificationProfile(),
        loadRulesHealth: () => loadRulesHealth(),
        p1TriageLoadEntries: () => p1TriageLoadEntries(),
        prepareFunctionScopeCacheForSelectedFiles: (selected) => prepareFunctionScopeCacheForSelectedFiles(selected),
        recordRendererError,
        setActiveJumpRequestState: (status, line) => setActiveJumpRequestState(status, line),
        setAutofixValidationPanel: (text, options = {}) => setAutofixValidationPanel(text, options),
        updateAiContextHelpText: () => updateAiContextHelpText(),
        updateExcelJobUiFromAnalysis: () => updateExcelJobUiFromAnalysis(),
        updateRendererDiagnostics,
        updateWorkspaceChrome: () => updateWorkspaceChrome(),
        workspaceBuildWorkspaceRowIndex: () => workspaceBuildWorkspaceRowIndex(),
        workspaceGetSelectedFiles: () => workspaceGetSelectedFiles(),
        workspaceGetSelectedInputSources: () => workspaceGetSelectedInputSources(),
        workspaceRenderWorkspace: (options = {}) => workspaceRenderWorkspace(options),
    },
});

const {
    bindAnalyzeButton,
} = analyzeRunController;

bindPrimaryNavigation();
bindAnalyzeButton();

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

function createDiffPaneLine(lineNo, text, kind) {
    const row = document.createElement("div");
    row.className = `diff-pane-line diff-pane-line-${kind || "context"}`;
    const number = document.createElement("span");
    number.className = "diff-pane-line-number";
    number.textContent = lineNo > 0 ? String(lineNo) : "";
    const content = document.createElement("span");
    content.className = "diff-pane-line-text";
    content.textContent = String(text || "");
    row.append(number, content);
    return row;
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

bindRendererDomContentLoaded({
    dom,
    elements,
    state,
    helpers: {
        autofixCloseDiffModal: () => autofixCloseDiffModal(),
        autofixSetAiReviewText: (text) => autofixSetAiReviewText(text),
        autofixSetDiffModalView: (view) => autofixSetDiffModalView(view),
        autofixSyncAiMoreMenuUi: () => autofixSyncAiMoreMenuUi(),
        bindWorkspaceResizer,
        handleFlushExcelReportsClick: () => handleFlushExcelReportsClick(),
        p1TriageLoadEntries: () => p1TriageLoadEntries(),
        p1TriageSetShowSuppressedP1: (value) => p1TriageSetShowSuppressedP1(value),
        recordRendererError,
        setActivePrimaryView: (viewName) => setActivePrimaryView(viewName),
        setCodeViewerText: (text) => setCodeViewerText(text),
        setExcelDownloadsExpanded: (expanded) => setExcelDownloadsExpanded(expanded),
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        stageExternalInputs: (files, mode) => stageExternalInputs(files, mode),
        syncAiContextToggle: () => syncAiContextToggle(),
        toggleWorkspaceAdvanced: () => toggleWorkspaceAdvanced(),
        toggleWorkspacePane: (paneName) => toggleWorkspacePane(paneName),
        updateDashboard: () => updateDashboard(),
        updateExcelJobUiFromAnalysis: () => updateExcelJobUiFromAnalysis(),
        updateRendererDiagnostics,
        updateWorkspaceChrome: () => updateWorkspaceChrome(),
        updateWorkspacePaneUi: () => updateWorkspacePaneUi(),
        updateAiContextHelpText: () => updateAiContextHelpText(),
        workspaceApplyCodePaneHeight: () => workspaceApplyCodePaneHeight(),
        workspaceAttachResultTableVirtualScrollHandler: () => workspaceAttachResultTableVirtualScrollHandler(),
        workspaceFocusAdjacentWorkspaceRow: (direction) => workspaceFocusAdjacentWorkspaceRow(direction),
        workspaceInitFilterControls: () => workspaceInitFilterControls(),
        workspaceLoadFiles: () => workspaceLoadFiles(),
        workspaceOpenActiveWorkspaceRow: () => workspaceOpenActiveWorkspaceRow(),
        workspaceRenderWorkspace: (options = {}) => workspaceRenderWorkspace(options),
        workspaceRenderWorkspaceCommandBar: () => workspaceRenderWorkspaceCommandBar(),
        workspaceRenderWorkspaceQuickFilter: () => workspaceRenderWorkspaceQuickFilter(),
        workspaceResetWorkspaceFilters: () => workspaceResetWorkspaceFilters(),
        workspaceSetWorkspaceFileQuery: (query) => workspaceSetWorkspaceFileQuery(query),
        workspaceSetWorkspaceQuickPreset: (preset) => workspaceSetWorkspaceQuickPreset(preset),
        workspaceSetWorkspaceResultQuery: (query) => workspaceSetWorkspaceResultQuery(query),
        loadLatestVerificationProfile: () => loadLatestVerificationProfile(),
        loadLatestOperationalResults: () => loadLatestOperationalResults(),
        loadRulesHealth: () => loadRulesHealth(),
    },
});

bindRendererGlobalShortcuts({
    elements,
    helpers: {
        autofixCloseDiffModal: () => autofixCloseDiffModal(),
        setInspectorTab: (tabName, hasAiSuggestion = false) => setInspectorTab(tabName, hasAiSuggestion),
        shouldIgnoreWorkspaceShortcut: (event) => shouldIgnoreWorkspaceShortcut(event),
        workspaceFocusAdjacentWorkspaceRow: (direction) => workspaceFocusAdjacentWorkspaceRow(direction),
        workspaceOpenActiveWorkspaceRow: () => workspaceOpenActiveWorkspaceRow(),
        workspaceRefreshSplitLayout: (options = {}) => workspaceRefreshSplitLayout(options),
    },
});


