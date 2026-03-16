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

export function buildWorkspaceEmptyStateReason({ totalRowCount, quickFilterText, filterSummaryText }) {
    const total = Math.max(0, Number.parseInt(totalRowCount, 10) || 0);
    const quickFilter = String(quickFilterText || "").trim();
    const filterSummary = String(filterSummaryText || "").trim();
    if (total <= 0) {
        return "No review results are available yet. Run an analysis to populate the workspace.";
    }
    if (quickFilter) {
        return `No rows match the current filter. Clear the quick filter or widen the active source/severity filters. (${quickFilter})`;
    }
    if (filterSummary) {
        return `No rows match the current filter. Update the current view conditions and try again. (${filterSummary})`;
    }
    return "No rows match the current filter. Widen the source or severity filters to continue.";
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
