export function buildWorkspaceCommandSummary({
    selectedCount = 0,
    visibleCount = 0,
    totalCount = 0,
    hiddenSuppressedCount = 0,
    activeFilterText = "",
} = {}) {
    const parts = [
        `선택 파일 ${selectedCount}개`,
        `현재 표시 ${visibleCount}개`,
        `전체 검토 대상 ${totalCount}개`,
    ];
    if (hiddenSuppressedCount > 0) {
        parts.push(`숨김 처리 ${hiddenSuppressedCount}개`);
    }
    if (activeFilterText) {
        parts.push(activeFilterText);
    }
    return parts.join(" | ");
}

export function buildWorkspaceSelectionSummary(selection) {
    if (!selection) return "활성 이슈 없음";
    const source = String((selection && selection.source) || "P1").trim().toUpperCase();
    const objectText = String((selection && selection.object) || "Global").trim() || "Global";
    const lineValue = Number.parseInt(selection && selection.line, 10);
    const lineText = Number.isFinite(lineValue) && lineValue > 0 ? String(lineValue) : "-";
    return `${source} | ${objectText} | 줄 ${lineText}`;
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
        prevTitle: hasRows ? "이전 이슈로 이동합니다." : "이동할 이슈가 없습니다.",
        nextTitle: hasRows ? "다음 이슈로 이동합니다." : "이동할 이슈가 없습니다.",
        jumpTitle: hasActiveSelection ? "현재 이슈 위치의 코드를 엽니다." : "선택된 이슈가 없어 코드를 열 수 없습니다.",
        detailTitle: hasActiveSelection ? "상세 탭으로 전환합니다." : "선택된 이슈가 없어 상세를 열 수 없습니다.",
        aiTitle: hasActiveSelection
            ? (hasAiAvailable ? "AI 제안 탭으로 전환합니다." : "현재 이슈에는 AI 제안을 사용할 수 없습니다.")
            : "선택된 이슈가 없어 AI 탭을 열 수 없습니다.",
        resetTitle: (hasQuickFilter || hasCustomFilter) ? "현재 적용된 보기 조건을 초기화합니다." : "초기화할 보기 조건이 없습니다.",
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
        jumpTitle: hasActiveSelection ? "현재 이슈 위치의 코드를 엽니다." : "선택된 이슈가 없어 코드를 열 수 없습니다.",
        detailTitle: hasActiveSelection ? "상세 패널을 표시합니다." : "선택된 이슈가 없어 상세를 열 수 없습니다.",
        aiTitle: hasActiveSelection
            ? (aiEnabled ? "AI 제안 패널을 표시합니다." : "현재 이슈에는 AI 제안을 사용할 수 없습니다.")
            : "선택된 이슈가 없어 AI 패널을 열 수 없습니다.",
        compareTitle: hasActiveSelection
            ? (compareEnabled ? "현재 선택 항목의 비교 보기를 엽니다." : "현재 선택 항목에는 비교 가능한 제안이 없습니다.")
            : "선택된 이슈가 없어 비교를 열 수 없습니다.",
    };
}
