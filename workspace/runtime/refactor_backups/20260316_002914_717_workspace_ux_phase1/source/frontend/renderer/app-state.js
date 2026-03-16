export function createRendererStateSeed() {
    return {
        analysisData: {
            summary: { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
            violations: { P1: [], P2: [], P3: [] },
            ai_review_statuses: [],
            output_dir: "",
            metrics: {},
            report_jobs: {},
            report_paths: {},
        },
        currentViewerFile: "",
        currentViewerResolvedName: "",
        currentViewerSource: "",
        currentViewerContent: "",
        currentViewerHeaderLines: 0,
        currentHighlightedLine: null,
        currentHighlightedLineNear: false,
        currentViewerLines: [],
        activeJumpRequestState: { status: "idle", line: 0 },
        workspaceRowIndex: [],
        workspaceRenderToken: 0,
        workspaceFilteredRows: [],
        activeWorkspaceRowId: "",
        flashedWorkspaceRowId: "",
        activeWorkspaceFlashTimer: 0,
        codeViewerFocusTimer: 0,
        workspaceSelectionToken: 0,
        activeRecommendationRowId: "",
        recommendationInsightByRowId: new Map(),
        workspaceRecommendationInsightByRowId: new Map(),
        recommendationWorkspaceFilter: { mode: "", label: "", value: "", source: "" },
        excelDownloadsExpanded: false,
        analysisInsights: {
            dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
            recommendations: [],
        },
        workspaceAnalysisInsights: {
            dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
            recommendations: [],
        },
        resultTableVirtualState: {
            scrollAttached: false,
            rowHeight: 34,
            renderedStart: -1,
            renderedEnd: -1,
        },
        resultTableRenderQueued: false,
        autofixProposalCache: new Map(),
        AUTOFIX_PREPARE_MODE: "compare",
        aiReviewExpanded: false,
        activeInspectorTab: "detail",
        aiMoreMenuOpen: false,
        sessionInputSources: [],
        selectedAiModel: "",
        aiModelCatalogLoaded: false,
        latestRulesHealthPayload: null,
        rulesManageOpen: false,
        rulesManageLoading: false,
        rulesManageSaving: false,
        rulesManageRows: [],
        rulesManageDraftById: new Map(),
        rulesManageEditorMode: "edit",
        rulesManageEditorRuleId: "",
        rulesManageEditorDraft: null,
        rulesManageStatusMessage: "",
        rulesManageImportPreview: null,
        rulesManageImportDraft: null,
        analysisDiffRunOptions: [],
        selectedAnalysisDiffLatest: "",
        selectedAnalysisDiffPrevious: "",
        codeViewerVirtualState: {
            headerEl: null,
            linesWrap: null,
            topSpacer: null,
            visibleHost: null,
            bottomSpacer: null,
            lineHeight: 20,
            renderedStart: -1,
            renderedEnd: -1,
            scrollHandlerAttached: false,
        },
        codeViewerWindowRenderQueued: false,
        filterControls: {
            p1: null,
            p2: null,
            p3: null,
            critical: null,
            warning: null,
            info: null,
        },
        functionScopeCacheByFile: new Map(),
        reviewedTodoCacheByFile: new Map(),
        viewerContentCache: new Map(),
    };
}

export function sourceFilterKey(source) {
    const key = String(source || "").toLowerCase();
    if (key.startsWith("p1")) return "p1";
    if (key.startsWith("p2")) return "p2";
    if (key.startsWith("p3")) return "p3";
    return "p1";
}

export function severityFilterKey(rawSeverity) {
    const sev = String(rawSeverity || "").toLowerCase();
    if (["critical", "error", "fatal"].includes(sev)) return "critical";
    if (["warning", "high", "medium", "performance", "style", "portability"].includes(sev)) return "warning";
    return "info";
}

export function pickHigherSeverity(currentSeverity, candidateSeverity) {
    const rank = { info: 0, warning: 1, critical: 2 };
    const currentKey = severityFilterKey(currentSeverity);
    const candidateKey = severityFilterKey(candidateSeverity);
    return (rank[candidateKey] || 0) > (rank[currentKey] || 0) ? candidateSeverity : currentSeverity;
}

export function normalizeSeverityKeyword(rawSeverity) {
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
