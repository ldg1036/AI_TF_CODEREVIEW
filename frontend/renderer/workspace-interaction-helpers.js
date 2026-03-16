function toRowId(row) {
    return String((row && row.rowId) || "").trim();
}

export function findWorkspaceRowIndex(rows, rowId) {
    const normalized = String(rowId || "").trim();
    if (!normalized || !Array.isArray(rows)) return -1;
    return rows.findIndex((row) => toRowId(row) === normalized);
}

export function resolveWorkspaceSelection({ previousRows, nextRows, activeRowId }) {
    const prev = Array.isArray(previousRows) ? previousRows : [];
    const next = Array.isArray(nextRows) ? nextRows : [];
    const normalizedActive = String(activeRowId || "").trim();
    if (!next.length) {
        return {
            activeRowId: "",
            selectedRow: null,
            preserved: false,
            autoSelected: false,
            reason: "empty",
        };
    }

    if (normalizedActive) {
        const keptIndex = findWorkspaceRowIndex(next, normalizedActive);
        if (keptIndex >= 0) {
            return {
                activeRowId: normalizedActive,
                selectedRow: next[keptIndex],
                preserved: true,
                autoSelected: false,
                reason: "preserved",
            };
        }
    }

    const previousIndex = normalizedActive ? findWorkspaceRowIndex(prev, normalizedActive) : -1;
    if (previousIndex >= 0) {
        const fallbackIndex = Math.max(0, Math.min(next.length - 1, previousIndex));
        return {
            activeRowId: toRowId(next[fallbackIndex]),
            selectedRow: next[fallbackIndex],
            preserved: false,
            autoSelected: true,
            reason: "fallback_nearest",
        };
    }

    return {
        activeRowId: toRowId(next[0]),
        selectedRow: next[0],
        preserved: false,
        autoSelected: true,
        reason: normalizedActive ? "fallback_first" : "initial_first",
    };
}

export function getAdjacentWorkspaceRowId(rows, activeRowId, direction) {
    const safeRows = Array.isArray(rows) ? rows : [];
    if (!safeRows.length) return "";
    const step = direction < 0 ? -1 : 1;
    const currentIndex = findWorkspaceRowIndex(safeRows, activeRowId);
    if (currentIndex < 0) {
        return toRowId(step > 0 ? safeRows[0] : safeRows[safeRows.length - 1]);
    }
    const nextIndex = Math.max(0, Math.min(safeRows.length - 1, currentIndex + step));
    return toRowId(safeRows[nextIndex]);
}

export function buildWorkspaceEmptyStateReason({
    totalRowCount,
    quickFilterText,
    filterSummaryText,
    resultQuery = "",
    suppressedHiddenCount = 0,
}) {
    const total = Math.max(0, Number.parseInt(totalRowCount, 10) || 0);
    const hiddenSuppressed = Math.max(0, Number.parseInt(suppressedHiddenCount, 10) || 0);
    const quickFilter = String(quickFilterText || "").trim();
    const filterSummary = String(filterSummaryText || "").trim();
    const searchQuery = String(resultQuery || "").trim();
    if (total <= 0) {
        return "아직 검토 결과가 없습니다. 분석을 실행하면 이 영역에 검토 대상이 표시됩니다.";
    }
    if (hiddenSuppressed > 0 && !quickFilter && !filterSummary && !searchQuery) {
        return `현재 보이는 P1 결과는 모두 숨김 처리되었습니다. '숨김 처리 포함'을 켜면 ${hiddenSuppressed}개 항목을 다시 볼 수 있습니다.`;
    }
    if (searchQuery) {
        return `결과 검색과 일치하는 항목이 없습니다. 검색어를 조정하거나 다른 보기 조건을 사용해 보세요. ("${searchQuery}")`;
    }
    if (quickFilter) {
        return `현재 빠른 보기 기준과 일치하는 항목이 없습니다. 빠른 기준을 해제하거나 범위를 넓혀 보세요. (${quickFilter})`;
    }
    if (filterSummary) {
        return `현재 보기 조건과 일치하는 항목이 없습니다. 적용된 조건을 조정해 다시 확인해 보세요. (${filterSummary})`;
    }
    return "현재 보기 조건과 일치하는 항목이 없습니다. 출처나 심각도 조건을 넓혀 계속 검토해 보세요.";
}

export function toggleWorkspacePaneVisibility(panes, paneName) {
    const current = (panes && typeof panes === "object") ? panes : {};
    const normalized = String(paneName || "").trim().toLowerCase();
    if (!["files", "code", "inspector"].includes(normalized)) {
        return {
            files: current.files !== false,
            code: current.code !== false,
            inspector: current.inspector !== false,
        };
    }
    return {
        files: normalized === "files" ? !(current.files !== false) : current.files !== false,
        code: normalized === "code" ? !(current.code !== false) : current.code !== false,
        inspector: normalized === "inspector" ? !(current.inspector !== false) : current.inspector !== false,
    };
}

export function shouldIgnoreWorkspaceShortcut(eventLike) {
    const event = eventLike || {};
    if (event.defaultPrevented) return true;
    if (event.altKey || event.ctrlKey || event.metaKey) return true;
    const target = event.target;
    if (!target || typeof target !== "object") return false;
    if (target.isContentEditable) return true;
    const tagName = String(target.tagName || "").toUpperCase();
    if (["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tagName)) return true;
    return typeof target.closest === "function" && !!target.closest("[contenteditable='true']");
}
