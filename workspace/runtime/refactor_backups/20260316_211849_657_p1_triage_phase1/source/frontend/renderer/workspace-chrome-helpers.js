export function buildWorkspaceCommandSummary({ selectedCount = 0, visibleCount = 0, totalCount = 0 } = {}) {
    return `Selected ${selectedCount} files | Showing ${visibleCount} rows / ${totalCount} total`;
}

export function buildWorkspaceSelectionSummary(selection) {
    if (!selection) return "No active issue";
    const source = String((selection && selection.source) || "P1").trim().toUpperCase();
    const objectText = String((selection && selection.object) || "Global").trim() || "Global";
    const lineValue = Number.parseInt(selection && selection.line, 10);
    const lineText = Number.isFinite(lineValue) && lineValue > 0 ? String(lineValue) : "-";
    return `${source} | ${objectText} | line ${lineText}`;
}

export function deriveWorkspaceCommandButtonState({
    hasRows = false,
    hasActiveSelection = false,
    hasAiAvailable = false,
    hasQuickFilter = false,
    hasCustomFilter = false,
} = {}) {
    return {
        prevDisabled: !hasRows,
        nextDisabled: !hasRows,
        jumpDisabled: !hasActiveSelection,
        detailDisabled: !hasActiveSelection,
        aiDisabled: !(hasActiveSelection && hasAiAvailable),
        resetDisabled: !(hasQuickFilter || hasCustomFilter),
    };
}

export function deriveInspectorActionState({
    hasActiveSelection = false,
    aiEnabled = false,
    compareEnabled = false,
    activeInspectorTab = "detail",
} = {}) {
    const activeTab = activeInspectorTab === "ai" && aiEnabled ? "ai" : "detail";
    return {
        jumpDisabled: !hasActiveSelection,
        detailDisabled: !hasActiveSelection,
        detailPressed: activeTab === "detail",
        aiDisabled: !(hasActiveSelection && aiEnabled),
        aiPressed: activeTab === "ai" && aiEnabled,
        compareDisabled: !(hasActiveSelection && compareEnabled),
    };
}
