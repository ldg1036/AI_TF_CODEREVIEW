function queryById(id) {
    return document.getElementById(id);
}

function stringifyRendererError(errorLike) {
    if (errorLike instanceof Error) {
        return String(errorLike.stack || errorLike.message || errorLike);
    }
    if (errorLike && typeof errorLike === "object") {
        if (typeof errorLike.reason !== "undefined") {
            return stringifyRendererError(errorLike.reason);
        }
        if (typeof errorLike.message !== "undefined") {
            return String(errorLike.message);
        }
    }
    return String(errorLike || "");
}

export function createRendererShell() {
    function updateRendererDiagnostics(patch) {
        if (typeof window === "undefined") return;
        const current = (window.__rendererDiagnostics && typeof window.__rendererDiagnostics === "object")
            ? window.__rendererDiagnostics
            : {};
        window.__rendererDiagnostics = { ...current, ...patch };
    }

    function recordRendererError(errorLike) {
        if (typeof window === "undefined") return;
        const message = stringifyRendererError(errorLike);
        window.__lastRendererError = message;
        updateRendererDiagnostics({ last_error: message });
    }

    if (typeof window !== "undefined") {
        if (typeof window.__lastRendererError === "undefined") {
            window.__lastRendererError = null;
        }
        updateRendererDiagnostics({
            boot_status: "module_loaded",
            file_list_status: "booting",
            selected_file_count: 0,
            result_row_count: 0,
        });
        window.addEventListener("error", (event) => {
            recordRendererError(event.error || event.message || "window error");
        });
        window.addEventListener("unhandledrejection", (event) => {
            recordRendererError(event.reason || "unhandled rejection");
        });
    }

    const elements = {
        dashboardView: queryById("dashboard-view"),
        fileTreeSidebar: queryById("file-tree-sidebar"),
        inspectorPanel: queryById("inspector-panel"),
        workspaceView: queryById("workspace-view"),
        workspaceSurface: queryById("workspace-surface"),
        workspaceCodeShell: queryById("workspace-code-shell"),
        workspaceResizer: queryById("workspace-resizer"),
        navDashboard: queryById("nav-dashboard"),
        navWorkspace: queryById("nav-workspace"),
        navSettings: queryById("nav-settings"),
        btnAnalyze: queryById("btn-analyze"),
        btnAddExternalFiles: queryById("btn-add-external-files"),
        btnAddExternalFolder: queryById("btn-add-external-folder"),
        externalFileInput: queryById("external-file-input"),
        externalFolderInput: queryById("external-folder-input"),
        externalInputSummary: queryById("external-input-summary"),
        externalInputList: queryById("external-input-list"),
        ctrlppToggle: queryById("toggle-ctrlppcheck"),
        flushExcelBtn: queryById("btn-flush-excel"),
        excelJobStatusText: queryById("excel-job-status"),
        excelDownloadToggle: queryById("excel-download-toggle"),
        excelDownloadPanel: queryById("excel-download-panel"),
        excelDownloadList: queryById("excel-download-list"),
        analyzeProgressPanel: queryById("analyze-progress-panel"),
        analyzeProgressStatus: queryById("analyze-progress-status"),
        analyzeProgressBar: queryById("analyze-progress-bar"),
        analyzeProgressMeta: queryById("analyze-progress-meta"),
        liveAiToggle: queryById("toggle-live-ai"),
        aiModelSelect: queryById("select-ai-model"),
        aiContextToggle: queryById("toggle-ai-context"),
        aiContextLabel: queryById("label-ai-context"),
        aiContextHelp: queryById("ai-context-help"),
        inspectorTabDetail: queryById("inspector-tab-detail"),
        inspectorTabAi: queryById("inspector-tab-ai"),
        workspaceCommandPrev: queryById("workspace-command-prev"),
        workspaceCommandNext: queryById("workspace-command-next"),
        workspaceCommandJump: queryById("workspace-command-jump"),
        workspaceCommandDetail: queryById("workspace-command-detail"),
        workspaceCommandAi: queryById("workspace-command-ai"),
        workspaceCommandReset: queryById("workspace-command-reset"),
        workspaceCommandShowSuppressed: queryById("workspace-command-show-suppressed"),
        workspaceFileSearch: queryById("workspace-file-search"),
        workspaceResultSearch: queryById("workspace-result-search"),
        workspacePresetAll: queryById("workspace-preset-all"),
        workspacePresetP1: queryById("workspace-preset-p1"),
        workspacePresetAttention: queryById("workspace-preset-attention"),
        workspacePaneFiles: queryById("workspace-pane-files"),
        workspacePaneCode: queryById("workspace-pane-code"),
        workspacePaneInspector: queryById("workspace-pane-inspector"),
        inspectorActionJump: queryById("inspector-action-jump"),
        inspectorActionDetail: queryById("inspector-action-detail"),
        inspectorActionAi: queryById("inspector-action-ai"),
        inspectorActionCompare: queryById("inspector-action-compare"),
        aiReviewToggleBtn: queryById("btn-ai-review-toggle"),
        diffModalBackdrop: queryById("autofix-diff-modal-backdrop"),
        diffModalClose: queryById("autofix-diff-modal-close"),
        diffModalViewSplit: queryById("autofix-diff-view-split"),
        diffModalViewUnified: queryById("autofix-diff-view-unified"),
    };

    const dom = {
        aiCard: queryById("ai-suggestion-card"),
        aiCompareButtons: queryById("autofix-compare-buttons"),
        aiCompareMeta: queryById("autofix-compare-meta"),
        aiComparePanel: queryById("autofix-compare-panel"),
        aiComparePreview: queryById("ai-compare-preview"),
        aiDiffPanel: queryById("autofix-diff-panel"),
        aiDiffText: queryById("autofix-diff-text"),
        aiMoreActions: queryById("ai-more-actions"),
        aiPanelWrap: queryById("ai-panel-wrap"),
        aiPrimaryActions: document.querySelector(".ai-primary-actions"),
        aiReviewToggleBtn: queryById("btn-ai-review-toggle"),
        aiSummaryList: queryById("ai-summary-list"),
        aiText: queryById("ai-text"),
        aiTextFull: queryById("ai-text-full"),
        aiValidationPanel: queryById("autofix-validation-panel"),
        aiValidationText: queryById("autofix-validation-text"),
        analysisDiffCompare: queryById("analysis-diff-compare"),
        btnAiMore: queryById("btn-ai-more"),
        codeViewer: queryById("code-viewer"),
        criticalText: queryById("critical-issues"),
        dedupeSummary: queryById("dedupe-summary"),
        diffModal: queryById("autofix-diff-modal"),
        diffModalAfter: queryById("autofix-diff-modal-after"),
        diffModalBackdrop: queryById("autofix-diff-modal-backdrop"),
        diffModalBefore: queryById("autofix-diff-modal-before"),
        diffModalCandidates: queryById("autofix-diff-modal-candidates"),
        diffModalClose: queryById("autofix-diff-modal-close"),
        diffModalMeta: queryById("autofix-diff-modal-meta"),
        diffModalSplit: queryById("autofix-diff-modal-split"),
        diffModalSummary: queryById("autofix-diff-modal-summary"),
        diffModalText: queryById("autofix-diff-modal-text"),
        diffModalTitle: queryById("autofix-diff-modal-title"),
        diffModalViewSplit: queryById("autofix-diff-view-split"),
        diffModalViewUnified: queryById("autofix-diff-view-unified"),
        fileList: queryById("file-list"),
        filterMatrix: document.querySelector(".filter-matrix"),
        inspectorSelectionMeta: queryById("inspector-selection-meta"),
        operationsCompare: queryById("operations-compare"),
        priorityRecommendations: queryById("priority-recommendations"),
        resultBody: queryById("result-body"),
        resultTableWrap: document.querySelector(".result-table"),
        rulesHealthCompare: queryById("rules-health-compare"),
        scoreBar: queryById("score-bar"),
        scoreText: queryById("score-text"),
        totalText: queryById("total-issues"),
        currentReviewText: queryById("current-review-issues"),
        verificationBadge: queryById("verification-badge"),
        verificationProfileCard: queryById("verification-profile-card"),
        violationDetail: queryById("violation-detail"),
        violationDetailPanel: queryById("violation-detail-panel"),
        warningText: queryById("warning-issues"),
        workspaceSurface: queryById("workspace-surface"),
        workspaceCodeShell: queryById("workspace-code-shell"),
        workspaceResizer: queryById("workspace-resizer"),
        workspaceFilterSummaryText: queryById("workspace-filter-summary-text"),
        workspaceCommandBar: queryById("workspace-command-bar"),
        workspaceCommandPrev: queryById("workspace-command-prev"),
        workspaceCommandNext: queryById("workspace-command-next"),
        workspaceCommandJump: queryById("workspace-command-jump"),
        workspaceCommandDetail: queryById("workspace-command-detail"),
        workspaceCommandAi: queryById("workspace-command-ai"),
        workspaceCommandReset: queryById("workspace-command-reset"),
        workspaceCommandShowSuppressed: queryById("workspace-command-show-suppressed"),
        workspaceCommandSummaryText: queryById("workspace-command-summary-text"),
        workspaceCommandSelectionText: queryById("workspace-command-selection-text"),
        workspaceFileSearch: queryById("workspace-file-search"),
        workspaceResultSearch: queryById("workspace-result-search"),
        workspacePresetAll: queryById("workspace-preset-all"),
        workspacePresetP1: queryById("workspace-preset-p1"),
        workspacePresetAttention: queryById("workspace-preset-attention"),
        workspaceQuickFilter: queryById("workspace-quick-filter"),
        workspaceQuickFilterClear: queryById("workspace-quick-filter-clear"),
        workspaceQuickFilterText: queryById("workspace-quick-filter-text"),
    };

    return {
        dom,
        elements,
        recordRendererError,
        updateRendererDiagnostics,
    };
}
