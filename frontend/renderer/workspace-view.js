import { positiveLineOrZero } from "./utils.js";
import { shouldHideSuppressedP1Row } from "./p1-triage.js";
import {
    buildWorkspaceEmptyStateReason,
    getAdjacentWorkspaceRowId,
    resolveWorkspaceSelection,
} from "./workspace-interaction-helpers.js";
import { normalizeWorkspaceQuickPreset } from "./workspace-search-helpers.js";
import { rebuildWorkspaceRowIndex } from "./workspace/row-index.js";
import { createWorkspaceFilePaneController } from "./workspace/file-pane.js";
import { createWorkspacePaneLayoutController } from "./workspace/pane-layout.js";
import { createWorkspaceRecommendationController } from "./workspace/recommendation-filters.js";

export function createWorkspaceController({ dom, state, caches, virtualState, helpers }) {
    function runWorkspaceSelection(violation, eventName, selectionToken) {
        const pendingLine = helpers.pendingJumpLineForViolation(violation);
        helpers.setActiveJumpRequestState("pending", pendingLine);
        helpers.showDetail(violation, eventName, { jumpPendingLine: pendingLine });
        return helpers.jumpCodeViewerToViolation(violation).then((jumpResult) => {
            if (selectionToken !== state.workspaceSelectionToken) return;
            if (!jumpResult || !jumpResult.ok) helpers.setActiveJumpRequestState("failed", pendingLine);
            helpers.showDetail(violation, eventName, { jumpResult });
        });
    }

    function findWorkspaceRowById(rowId, rows = state.workspaceFilteredRows) {
        const targetId = String(rowId || "").trim();
        if (!targetId) return null;
        const safeRows = Array.isArray(rows) ? rows : [];
        return safeRows.find((row) => String((row && row.rowId) || "").trim() === targetId) || null;
    }

    function markWorkspaceRowActive(rowId) {
        state.activeWorkspaceRowId = String(rowId || "").trim();
    }

    function syncWorkspaceRowHighlight() {
        if (!dom.resultBody) return;
        const activeId = String(state.activeWorkspaceRowId || "").trim();
        const flashId = String(state.flashedWorkspaceRowId || "").trim();
        dom.resultBody.querySelectorAll("tr.result-item-row").forEach((row) => {
            row.classList.toggle("result-item-row-active", !!activeId && row.getAttribute("data-row-id") === activeId);
            row.classList.toggle("result-item-row-flash", !!flashId && row.getAttribute("data-row-id") === flashId);
        });
    }

    function getResultTableBodyOffset() {
        if (!dom.resultTableWrap || !dom.resultBody) return 0;
        const wrapRect = dom.resultTableWrap.getBoundingClientRect();
        const bodyRect = dom.resultBody.getBoundingClientRect();
        return Math.max(0, (bodyRect.top - wrapRect.top) + dom.resultTableWrap.scrollTop);
    }

    function flashWorkspaceRow(rowId) {
        const targetId = String(rowId || "").trim();
        if (!targetId || !dom.resultBody) return;
        if (state.activeWorkspaceFlashTimer) {
            window.clearTimeout(state.activeWorkspaceFlashTimer);
            state.activeWorkspaceFlashTimer = 0;
        }
        state.flashedWorkspaceRowId = targetId;
        syncWorkspaceRowHighlight();
        const targetRow = dom.resultBody.querySelector(`tr.result-item-row[data-row-id="${CSS.escape(targetId)}"]`);
        if (targetRow) {
            targetRow.classList.remove("result-item-row-flash");
            void targetRow.offsetWidth;
            targetRow.classList.add("result-item-row-flash");
        }
        state.activeWorkspaceFlashTimer = window.setTimeout(() => {
            state.flashedWorkspaceRowId = "";
            syncWorkspaceRowHighlight();
            state.activeWorkspaceFlashTimer = 0;
        }, 1400);
    }

    function focusWorkspaceRow(rowId) {
        const targetId = String(rowId || "").trim();
        if (!targetId) return;
        markWorkspaceRowActive(targetId);
        const rowIndex = (state.workspaceFilteredRows || []).findIndex((row) => String(row && row.rowId || "").trim() === targetId);
        if (rowIndex < 0) {
            queueResultTableWindowRender(true);
            return;
        }
        if (dom.resultTableWrap) {
            const rowHeight = Math.max(24, Number(virtualState.resultTableVirtualState.rowHeight || 34));
            const bodyOffset = getResultTableBodyOffset();
            const viewportHeight = Math.max(1, dom.resultTableWrap.clientHeight || 1);
            dom.resultTableWrap.scrollTop = Math.max(0, bodyOffset + (rowIndex * rowHeight) - Math.max(0, (viewportHeight - rowHeight) / 2));
        }
        queueResultTableWindowRender(true);
        window.requestAnimationFrame(() => {
            syncWorkspaceRowHighlight();
            const targetRow = dom.resultBody.querySelector(`tr.result-item-row[data-row-id="${CSS.escape(targetId)}"]`);
            if (targetRow) {
                targetRow.scrollIntoView({ block: "nearest" });
                flashWorkspaceRow(targetId);
            }
        });
    }

    const paneLayoutController = createWorkspacePaneLayoutController({
        dom,
        state,
        helpers,
        onQueueResultRender: (force = false) => queueResultTableWindowRender(force),
    });

    const {
        applyWorkspaceCodePaneHeight,
        bindWorkspaceResizer,
        refreshWorkspaceSplitLayout,
        setWorkspaceCodePaneHeight,
    } = paneLayoutController;

    let recommendationController = null;
    let filePaneController = null;

    recommendationController = createWorkspaceRecommendationController({
        dom,
        state,
        helpers,
        getSelectedFiles: () => (filePaneController ? filePaneController.getSelectedFiles() : []),
        findWorkspaceRowById,
        markWorkspaceRowActive,
        focusWorkspaceRow,
        renderWorkspace,
        queueResultTableWindowRender,
    });

    const {
        applyRecommendationWorkspaceFilter,
        applyWorkspaceFilters,
        buildRecommendationWorkspaceFilterText,
        buildWorkspaceFilterSummaryText,
        clearRecommendationWorkspaceFilter,
        findRecommendationInsightForViolation,
        getFilterState,
        renderAnalysisInsights,
        renderWorkspaceCommandBar,
        renderWorkspaceFilterSummary,
        renderWorkspaceQuickFilter,
        rowMatchesRecommendationFilter,
    } = recommendationController;

    filePaneController = createWorkspaceFilePaneController({
        dom,
        state,
        helpers,
        applyWorkspaceCodePaneHeight,
        renderWorkspaceCommandBar: () => recommendationController.renderWorkspaceCommandBar(),
        renderWorkspaceFilterSummary: () => recommendationController.renderWorkspaceFilterSummary(),
    });

    const {
        getSelectedFiles,
        getSelectedInputSources,
        loadFiles,
        renderFileList,
        setWorkspaceFileQuery,
    } = filePaneController;

    function initFilterControls() {
        if (!dom.filterMatrix) return;
        const boxes = Array.from(dom.filterMatrix.querySelectorAll("input[type='checkbox']"));
        [state.filterControls.p1, state.filterControls.p2, state.filterControls.p3, state.filterControls.critical, state.filterControls.warning, state.filterControls.info] = boxes;
        boxes.forEach((cb) => cb.addEventListener("change", () => renderWorkspace()));
        if (state.filterControls.p3) {
            state.filterControls.p3.checked = false;
            const row = state.filterControls.p3.closest("div");
            if (row) row.style.display = "none";
        }
        if (dom.workspaceQuickFilterClear) {
            dom.workspaceQuickFilterClear.onclick = () => clearRecommendationWorkspaceFilter();
        }
    }

    async function activateWorkspaceRow(rowData, selectionToken, options = {}) {
        if (!rowData) return;
        const rowId = String((rowData && rowData.rowId) || "").trim();
        markWorkspaceRowActive(rowId);
        state.activeRecommendationRowId = state.recommendationInsightByRowId.has(rowId) ? rowId : "";
        syncWorkspaceRowHighlight();
        renderWorkspaceCommandBar();
        if (typeof helpers.updateWorkspaceChrome === "function") {
            helpers.updateWorkspaceChrome();
        }
        if (options.navigateWorkspace !== false) {
            helpers.navWorkspace();
            await new Promise((resolve) => window.requestAnimationFrame(resolve));
        }
        if (typeof (rowData && rowData.onClick) === "function") {
            await rowData.onClick(selectionToken);
        }
        renderWorkspaceCommandBar();
        if (typeof helpers.updateWorkspaceChrome === "function") {
            helpers.updateWorkspaceChrome();
        }
    }

    async function openActiveWorkspaceRow() {
        const row = findWorkspaceRowById(state.activeWorkspaceRowId);
        if (!row) return;
        const selectionToken = ++state.workspaceSelectionToken;
        await activateWorkspaceRow(row, selectionToken, { navigateWorkspace: true });
    }

    async function focusAdjacentWorkspaceRow(direction) {
        const nextRowId = getAdjacentWorkspaceRowId(state.workspaceFilteredRows, state.activeWorkspaceRowId, direction);
        if (!nextRowId) return;
        const row = findWorkspaceRowById(nextRowId);
        if (!row) return;
        focusWorkspaceRow(nextRowId);
        const selectionToken = ++state.workspaceSelectionToken;
        await activateWorkspaceRow(row, selectionToken, { navigateWorkspace: false });
    }

    function resetWorkspaceFilters() {
        const boxes = [
            state.filterControls.p1,
            state.filterControls.p2,
            state.filterControls.critical,
            state.filterControls.warning,
            state.filterControls.info,
        ];
        boxes.forEach((cb) => {
            if (cb) cb.checked = true;
        });
        state.recommendationWorkspaceFilter = { mode: "", label: "", value: "", source: "" };
        state.workspaceFileQuery = "";
        state.workspaceResultQuery = "";
        state.workspaceQuickPreset = "all";
        state.showSuppressedP1 = false;
        renderFileList(state.workspaceAvailableFiles || []);
        renderWorkspace({ autoSelect: true, resetScroll: true });
    }

    function createResultRow(rowData) {
        const row = document.createElement("tr");
        const rowId = rowData && rowData.rowId;
        row.className = "result-item-row";
        if (rowId) row.setAttribute("data-row-id", String(rowId));
        const source = rowData && rowData.source;
        const object = rowData && rowData.object;
        const severity = rowData && rowData.severity;
        const message = rowData && rowData.message;
        const suppressed = !!(rowData && rowData.p1TriageSuppressed);
        const sourceCell = document.createElement("td");
        sourceCell.className = "result-cell result-cell-source";
        const sourceBadge = document.createElement("span");
        sourceBadge.className = `badge badge-${String(source || "").toLowerCase()}`;
        sourceBadge.textContent = String(source || "-");
        sourceCell.appendChild(sourceBadge);
        if (suppressed) {
            row.classList.add("result-item-row-suppressed");
            const suppressedBadge = document.createElement("span");
            suppressedBadge.className = "result-inline-badge result-inline-badge-suppressed";
            suppressedBadge.textContent = "제외";
            sourceCell.appendChild(suppressedBadge);
        }
        const objectCell = document.createElement("td");
        objectCell.className = "result-cell result-cell-object";
        const objectTitle = document.createElement("div");
        objectTitle.className = "result-object-title";
        objectTitle.textContent = object || "-";
        objectCell.appendChild(objectTitle);
        const objectMeta = document.createElement("div");
        objectMeta.className = "result-object-meta";
        const objectMetaParts = [];
        const sourceText = String(source || "").trim();
        const issueId = String((rowData && rowData.issueId) || "").trim();
        if (sourceText) objectMetaParts.push(sourceText);
        if (issueId) objectMetaParts.push(issueId);
        objectMeta.textContent = objectMetaParts.join(" | ");
        if (objectMeta.textContent) objectCell.appendChild(objectMeta);
        const severityCell = document.createElement("td");
        severityCell.className = "result-cell result-cell-severity";
        const severitySpan = document.createElement("span");
        const severityRaw = String(severity || "Info");
        severitySpan.className = `result-severity severity-${helpers.severityFilterKey(severityRaw)}`;
        severitySpan.textContent = helpers.normalizeSeverityKeyword(severityRaw);
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
        const primaryRuleId = String(
            (rowData && (rowData.ruleId || rowData.rule_id))
            || (Array.isArray(rowData && rowData.ruleIds) ? rowData.ruleIds[0] : "")
            || "",
        ).trim();
        if (lineNo > 0) metaParts.push(`line ${lineNo}`);
        if (primaryRuleId) metaParts.push(primaryRuleId);
        if (Number.parseInt(rowData && rowData.duplicateCount, 10) > 1) metaParts.push(`duplicates ${Number.parseInt(rowData && rowData.duplicateCount, 10)}`);
        if (suppressed) metaParts.push("suppressed");
        messageMeta.textContent = metaParts.join(" | ");
        if (messageMeta.textContent) messageCell.appendChild(messageMeta);
        row.append(sourceCell, objectCell, severityCell, messageCell);
        row.onclick = async () => {
            const selectionToken = ++state.workspaceSelectionToken;
            await activateWorkspaceRow(rowData, selectionToken, { navigateWorkspace: true });
        };
        return row;
    }

    function attachResultTableVirtualScrollHandler() {
        if (!dom.resultTableWrap || virtualState.resultTableVirtualState.scrollAttached) return;
        dom.resultTableWrap.addEventListener("scroll", () => queueResultTableWindowRender());
        virtualState.resultTableVirtualState.scrollAttached = true;
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
        if (!dom.resultBody) return;
        if (force) {
            virtualState.resultTableVirtualState.renderedStart = -1;
            virtualState.resultTableVirtualState.renderedEnd = -1;
        }
        if (state.resultTableRenderQueued) return;
        state.resultTableRenderQueued = true;
        window.requestAnimationFrame(() => {
            state.resultTableRenderQueued = false;
            renderWorkspaceWindow();
        });
    }

    function renderWorkspaceWindow() {
        applyWorkspaceCodePaneHeight();
        if (!dom.resultBody) return;
        attachResultTableVirtualScrollHandler();
        const rows = Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows : [];
        if (!dom.resultTableWrap) {
            dom.resultBody.replaceChildren();
            const frag = document.createDocumentFragment();
            rows.forEach((row) => frag.appendChild(createResultRow(row)));
            dom.resultBody.appendChild(frag);
            syncWorkspaceRowHighlight();
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    result_row_count: rows.length,
                    workspace_filtered_row_count: rows.length,
                });
            }
            return;
        }
        if (!rows.length) {
            dom.resultBody.replaceChildren();
            virtualState.resultTableVirtualState.renderedStart = 0;
            virtualState.resultTableVirtualState.renderedEnd = 0;
            const emptyRow = document.createElement("tr");
            emptyRow.className = "result-empty-row";
            const emptyCell = document.createElement("td");
            emptyCell.colSpan = 4;
            emptyCell.className = "result-empty-state";
            emptyCell.textContent = buildWorkspaceEmptyStateReason({
                totalRowCount: Array.isArray(state.workspaceRowIndex) ? state.workspaceRowIndex.length : 0,
                quickFilterText: buildRecommendationWorkspaceFilterText(),
                filterSummaryText: buildWorkspaceFilterSummaryText(),
                resultQuery: state.workspaceResultQuery,
                suppressedHiddenCount: Array.isArray(state.workspaceRowIndex)
                    ? state.workspaceRowIndex.filter((row) => shouldHideSuppressedP1Row(row, !!state.showSuppressedP1)).length
                    : 0,
            });
            emptyRow.appendChild(emptyCell);
            dom.resultBody.appendChild(emptyRow);
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    result_row_count: 0,
                    workspace_filtered_row_count: 0,
                });
            }
            renderWorkspaceCommandBar();
            return;
        }
        const rowHeight = Math.max(24, Number(virtualState.resultTableVirtualState.rowHeight || 34));
        const bodyOffset = getResultTableBodyOffset();
        const viewportHeight = Math.max(1, dom.resultTableWrap.clientHeight || 1);
        const scrollTop = Math.max(0, (dom.resultTableWrap.scrollTop || 0) - bodyOffset);
        const overscan = 18;
        let start = Math.floor(scrollTop / rowHeight) - overscan;
        if (!Number.isFinite(start)) start = 0;
        start = Math.max(0, start);
        const visibleCount = Math.max(1, Math.ceil(viewportHeight / rowHeight) + overscan * 2);
        const end = Math.min(rows.length, start + visibleCount);
        if (start === virtualState.resultTableVirtualState.renderedStart && end === virtualState.resultTableVirtualState.renderedEnd) return;
        virtualState.resultTableVirtualState.renderedStart = start;
        virtualState.resultTableVirtualState.renderedEnd = end;
        const frag = document.createDocumentFragment();
        frag.appendChild(createResultSpacerRow(start * rowHeight));
        for (let idx = start; idx < end; idx += 1) frag.appendChild(createResultRow(rows[idx]));
        frag.appendChild(createResultSpacerRow(Math.max(0, (rows.length - end) * rowHeight)));
        dom.resultBody.replaceChildren(frag);
        syncWorkspaceRowHighlight();
        const measuredRow = dom.resultBody.querySelector("tr.result-item-row");
        if (measuredRow) {
            const h = measuredRow.getBoundingClientRect().height;
            if (Number.isFinite(h) && h > 0 && Math.abs(h - virtualState.resultTableVirtualState.rowHeight) > 1) {
                virtualState.resultTableVirtualState.rowHeight = h;
                virtualState.resultTableVirtualState.renderedStart = -1;
                virtualState.resultTableVirtualState.renderedEnd = -1;
                queueResultTableWindowRender();
            }
        }
        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                result_row_count: dom.resultBody.querySelectorAll("tr.result-item-row").length,
                workspace_filtered_row_count: rows.length,
            });
        }
        renderWorkspaceCommandBar();
    }

    function buildWorkspaceRowIndex() {
        rebuildWorkspaceRowIndex({
            state,
            caches,
            helpers,
            runWorkspaceSelection,
        });
    }

    function renderWorkspace(options = {}) {
        const previousRows = Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows : [];
        state.workspaceRenderToken += 1;
        state.workspaceFilteredRows = applyWorkspaceFilters(state.workspaceRowIndex || []);
        const selection = resolveWorkspaceSelection({
            previousRows,
            nextRows: state.workspaceFilteredRows,
            activeRowId: state.activeWorkspaceRowId,
        });
        state.activeWorkspaceRowId = selection.activeRowId;
        if ((options && options.resetScroll !== false) && dom.resultTableWrap) {
            dom.resultTableWrap.scrollTop = 0;
        }
        renderWorkspaceQuickFilter();
        renderWorkspaceFilterSummary();
        renderWorkspaceCommandBar();
        queueResultTableWindowRender(true);
        if ((options && options.autoSelect !== false) && selection.autoSelected && selection.selectedRow) {
            const selectionToken = ++state.workspaceSelectionToken;
            window.requestAnimationFrame(() => {
                void activateWorkspaceRow(selection.selectedRow, selectionToken, { navigateWorkspace: false });
            });
        } else if (typeof helpers.updateWorkspaceChrome === "function") {
            helpers.updateWorkspaceChrome();
        }
        if (typeof helpers.updateDashboard === "function") {
            helpers.updateDashboard();
        }
    }

    function setWorkspaceResultQuery(query = "") {
        state.workspaceResultQuery = String(query || "");
        renderWorkspace({ autoSelect: true, resetScroll: true });
    }

    function setWorkspaceQuickPreset(preset = "all") {
        state.workspaceQuickPreset = normalizeWorkspaceQuickPreset(preset);
        renderWorkspace({ autoSelect: true, resetScroll: true });
    }

    return {
        applyRecommendationWorkspaceFilter,
        applyWorkspaceCodePaneHeight,
        attachResultTableVirtualScrollHandler,
        bindWorkspaceResizer,
        buildRecommendationWorkspaceFilterText,
        buildWorkspaceRowIndex,
        clearRecommendationWorkspaceFilter,
        createResultRow,
        findRecommendationInsightForViolation,
        flashWorkspaceRow,
        focusAdjacentWorkspaceRow,
        focusWorkspaceRow,
        getFilterState,
        getSelectedFiles,
        getSelectedInputSources,
        initFilterControls,
        loadFiles,
        markWorkspaceRowActive,
        openActiveWorkspaceRow,
        queueResultTableWindowRender,
        refreshWorkspaceSplitLayout,
        renderAnalysisInsights,
        renderWorkspaceCommandBar,
        renderFileList,
        renderWorkspace,
        renderWorkspaceFilterSummary,
        renderWorkspaceQuickFilter,
        renderWorkspaceWindow,
        resetWorkspaceFilters,
        rowMatchesRecommendationFilter,
        runWorkspaceSelection,
        setWorkspaceFileQuery,
        setWorkspaceCodePaneHeight,
        setWorkspaceQuickPreset,
        setWorkspaceResultQuery,
        syncWorkspaceRowHighlight,
    };
}
