import {
    basenamePath,
    escapeHtml,
    normalizeInsightToken,
    positiveLineOrZero,
    truncateUiText,
    violationCanonicalFileId,
    violationDisplayFile,
    violationResolvedFile,
} from "./utils.js";
import { buildReviewedP1SyncPlan } from "./reviewed-linking.js";
import {
    applyP1TriageToRow,
    excludeSuppressedP1Rows,
    shouldHideSuppressedP1Row,
} from "./p1-triage.js";
import {
    buildWorkspaceEmptyStateReason,
    getAdjacentWorkspaceRowId,
    resolveWorkspaceSelection,
} from "./workspace-interaction-helpers.js";
import {
    buildWorkspaceFileListEmptyMessage,
    buildWorkspaceSearchStateLabel,
    filterWorkspaceFilesByQuery,
    getWorkspaceFileName,
    normalizeWorkspaceQuickPreset,
    rowMatchesWorkspaceQuickPreset,
    rowMatchesWorkspaceResultQuery,
} from "./workspace-search-helpers.js";
import {
    buildWorkspaceCommandSummary,
    buildWorkspaceSelectionSummary,
    deriveWorkspaceCommandButtonState,
} from "./workspace-chrome-helpers.js";
import {
    DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
    calculateWorkspaceCodePaneHeightFromPointer,
    clampWorkspaceCodePaneHeight,
} from "./workspace-resize-helpers.js";
import {
    buildRecommendationInsightIndex,
    deriveAnalysisInsights,
    getRowHotspotKey,
    getRowRuleFamilies,
} from "./workspace/recommendations.js";
import { rebuildWorkspaceRowIndex } from "./workspace/row-index.js";

export function createWorkspaceController({ dom, state, caches, virtualState, helpers }) {
    let activeResizeSession = null;

    function ensureWorkspaceUiState() {
        const current = (state.workspaceUi && typeof state.workspaceUi === "object") ? state.workspaceUi : {};
        if (!current.paneVisibility || typeof current.paneVisibility !== "object") {
            current.paneVisibility = { files: true, code: true, inspector: true };
        }
        if (!Number.isFinite(Number.parseInt(current.codePaneHeightPx, 10))) {
            current.codePaneHeightPx = DEFAULT_WORKSPACE_CODE_PANE_HEIGHT;
        }
        current.isResizingCodePane = !!current.isResizingCodePane;
        state.workspaceUi = current;
        return current;
    }

    function getWorkspaceResizableHeight() {
        const surfaceHeight = Math.max(0, Number.parseInt(dom.workspaceSurface && dom.workspaceSurface.clientHeight, 10) || 0);
        const resizerHeight = Math.max(0, Math.round(dom.workspaceResizer && dom.workspaceResizer.getBoundingClientRect
            ? dom.workspaceResizer.getBoundingClientRect().height
            : 0));
        return Math.max(0, surfaceHeight - resizerHeight);
    }

    function syncWorkspaceResizeUi() {
        const ui = ensureWorkspaceUiState();
        const isCodeVisible = ui.paneVisibility.code !== false;
        if (dom.workspaceSurface) {
            dom.workspaceSurface.classList.toggle("is-resizing", !!ui.isResizingCodePane);
            if (!isCodeVisible) {
                dom.workspaceSurface.style.removeProperty("--workspace-code-pane-height");
            }
        }
        if (dom.workspaceResizer) {
            dom.workspaceResizer.hidden = !isCodeVisible;
            dom.workspaceResizer.setAttribute("aria-hidden", isCodeVisible ? "false" : "true");
        }
        if (typeof document !== "undefined" && document.body) {
            document.body.classList.toggle("workspace-resize-active", !!ui.isResizingCodePane);
        }
        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                workspace_code_pane_height_px: Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
                workspace_resize_active: !!ui.isResizingCodePane,
            });
        }
    }

    function applyWorkspaceCodePaneHeight(options = {}) {
        const ui = ensureWorkspaceUiState();
        const isCodeVisible = ui.paneVisibility.code !== false;
        if (!isCodeVisible) {
            syncWorkspaceResizeUi();
            return 0;
        }
        const resizableHeight = getWorkspaceResizableHeight();
        const clampedHeight = resizableHeight > 0
            ? clampWorkspaceCodePaneHeight(ui.codePaneHeightPx, resizableHeight)
            : (Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT);
        ui.codePaneHeightPx = clampedHeight;
        state.workspaceUi = ui;
        if (dom.workspaceSurface) {
            dom.workspaceSurface.style.setProperty("--workspace-code-pane-height", `${clampedHeight}px`);
        }
        syncWorkspaceResizeUi();
        if (options.rerender) {
            if (typeof helpers.queueCodeViewerWindowRender === "function") {
                helpers.queueCodeViewerWindowRender(true);
            }
            queueResultTableWindowRender(true);
        }
        return clampedHeight;
    }

    function setWorkspaceCodePaneHeight(nextHeight, options = {}) {
        const ui = ensureWorkspaceUiState();
        ui.codePaneHeightPx = clampWorkspaceCodePaneHeight(nextHeight, getWorkspaceResizableHeight());
        state.workspaceUi = ui;
        return applyWorkspaceCodePaneHeight({ rerender: !!options.rerender });
    }

    function refreshWorkspaceSplitLayout(options = {}) {
        return applyWorkspaceCodePaneHeight({ rerender: !!options.rerender });
    }

    function stopWorkspaceResize(pointerId = null) {
        const ui = ensureWorkspaceUiState();
        ui.isResizingCodePane = false;
        state.workspaceUi = ui;
        if (dom.workspaceResizer && pointerId !== null && typeof dom.workspaceResizer.releasePointerCapture === "function") {
            try {
                dom.workspaceResizer.releasePointerCapture(pointerId);
            } catch (_) {
                // Ignore stale capture release errors.
            }
        }
        activeResizeSession = null;
        refreshWorkspaceSplitLayout({ rerender: true });
    }

    function bindWorkspaceResizer() {
        if (!dom.workspaceResizer || dom.workspaceResizer.dataset.resizeBound === "true") return;
        dom.workspaceResizer.dataset.resizeBound = "true";
        dom.workspaceResizer.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) return;
            if (event.pointerType && event.pointerType !== "mouse") return;
            const ui = ensureWorkspaceUiState();
            if (ui.paneVisibility.code === false) return;
            activeResizeSession = {
                pointerId: event.pointerId,
                startY: event.clientY,
                startHeightPx: Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
            };
            ui.isResizingCodePane = true;
            state.workspaceUi = ui;
            syncWorkspaceResizeUi();
            if (typeof dom.workspaceResizer.setPointerCapture === "function") {
                dom.workspaceResizer.setPointerCapture(event.pointerId);
            }
            event.preventDefault();
        });
        dom.workspaceResizer.addEventListener("pointermove", (event) => {
            if (!activeResizeSession || event.pointerId !== activeResizeSession.pointerId) return;
            const nextHeight = calculateWorkspaceCodePaneHeightFromPointer({
                startHeightPx: activeResizeSession.startHeightPx,
                startPointerY: activeResizeSession.startY,
                nextPointerY: event.clientY,
                containerHeightPx: getWorkspaceResizableHeight(),
            });
            setWorkspaceCodePaneHeight(nextHeight, { rerender: false });
            event.preventDefault();
        });
        const finishResize = (event) => {
            if (!activeResizeSession) return;
            if (event && event.pointerId !== activeResizeSession.pointerId) return;
            stopWorkspaceResize(activeResizeSession.pointerId);
        };
        dom.workspaceResizer.addEventListener("pointerup", finishResize);
        dom.workspaceResizer.addEventListener("pointercancel", finishResize);
        dom.workspaceResizer.addEventListener("lostpointercapture", () => {
            if (!activeResizeSession) return;
            stopWorkspaceResize(null);
        });
    }

    function rowMatchesRecommendationFilter(row) {
        const mode = String(state.recommendationWorkspaceFilter.mode || "").trim();
        const value = String(state.recommendationWorkspaceFilter.value || "").trim();
        if (!mode || !value) return true;
        if (mode === "hotspot") return getRowHotspotKey(row) === value;
        if (mode === "rule_family") return getRowRuleFamilies(row).includes(value);
        return true;
    }

    function buildRecommendationWorkspaceFilterText() {
        const mode = String(state.recommendationWorkspaceFilter.mode || "").trim();
        const label = String(state.recommendationWorkspaceFilter.label || "").trim();
        const source = String(state.recommendationWorkspaceFilter.source || "").trim();
        if (!mode || !label) return "";
        return `${mode === "rule_family" ? "활성 규칙 필터" : "활성 hotspot 필터"}: ${label}${source ? ` | ${source.toUpperCase()}` : ""}`;
    }

    function buildWorkspaceFilterComparisonSummary() {
        const activeMode = String(state.recommendationWorkspaceFilter.mode || "").trim();
        if (!activeMode) return { banner: "", detail: "" };
        const overall = (state.analysisInsights && state.analysisInsights.dedupe) || {};
        const current = (state.workspaceAnalysisInsights && state.workspaceAnalysisInsights.dedupe) || {};
        const overallIssues = Math.max(0, Number.parseInt(overall.rawIssueCount, 10) || 0);
        const currentIssues = Math.max(0, Number.parseInt(current.rawIssueCount, 10) || 0);
        const overallRows = Math.max(0, Number.parseInt(overall.displayedRowCount, 10) || 0);
        const currentRows = Math.max(0, Number.parseInt(current.displayedRowCount, 10) || 0);
        const issueDelta = Math.max(0, overallIssues - currentIssues);
        const rowDelta = Math.max(0, overallRows - currentRows);
        return {
            banner: `표시 행 ${currentRows}/${overallRows} | 이슈 ${currentIssues}/${overallIssues} | 숨김 ${rowDelta}/${issueDelta}`,
            detail: `전체 ${overallRows}개 행, ${overallIssues}개 이슈 중 현재 기준으로 ${currentRows}개 행과 ${currentIssues}개 이슈를 유지합니다. 숨겨진 항목은 ${rowDelta}개 행, ${issueDelta}개 이슈입니다.`,
        };
    }

    function renderWorkspaceQuickFilter() {
        if (!dom.workspaceQuickFilter || !dom.workspaceQuickFilterText) return;
        const mode = String(state.recommendationWorkspaceFilter.mode || "").trim();
        const label = String(state.recommendationWorkspaceFilter.label || "").trim();
        const source = String(state.recommendationWorkspaceFilter.source || "").trim();
        if (!mode || !label) {
            dom.workspaceQuickFilter.classList.add("hidden");
            dom.workspaceQuickFilterText.textContent = "";
            helpers.updateCodeViewerHeaderMeta();
            return;
        }
        const dedupe = (state.workspaceAnalysisInsights && state.workspaceAnalysisInsights.dedupe) || {};
        const topRecommendation = Array.isArray(state.workspaceAnalysisInsights && state.workspaceAnalysisInsights.recommendations)
            ? state.workspaceAnalysisInsights.recommendations[0]
            : null;
        const comparison = buildWorkspaceFilterComparisonSummary();
        const prefix = mode === "rule_family" ? "규칙 집중" : "Hotspot 집중";
        dom.workspaceQuickFilter.classList.remove("hidden");
        dom.workspaceQuickFilterText.textContent = `${prefix}: ${label}${source ? ` | ${source.toUpperCase()}` : ""} | 행 ${dedupe.displayedRowCount || 0} | 이슈 ${dedupe.rawIssueCount || 0}${topRecommendation ? ` | 우선 규칙 ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` | ${comparison.banner}` : ""}`;
        helpers.updateCodeViewerHeaderMeta();
    }

    function applyRecommendationWorkspaceFilter(mode, label, value, source = "") {
        state.recommendationWorkspaceFilter = {
            mode: String(mode || "").trim(),
            label: String(label || "").trim(),
            value: String(value || "").trim(),
            source: String(source || "").trim(),
        };
        renderWorkspace();
    }

    function clearRecommendationWorkspaceFilter() {
        state.recommendationWorkspaceFilter = { mode: "", label: "", value: "", source: "" };
        renderWorkspace();
    }

    function findRecommendationInsightForViolation(violation) {
        const activeRowKey = String(state.activeRecommendationRowId || state.activeWorkspaceRowId || "").trim();
        const exact = state.workspaceRecommendationInsightByRowId.get(activeRowKey)
            || state.recommendationInsightByRowId.get(activeRowKey)
            || null;
        if (exact) return exact;
        const violationSource = String((violation && violation.priority_origin) || (violation && violation.source) || "").trim().toUpperCase();
        const violationTarget = basenamePath((violation && (violation.file || violation.object)) || "") || String((violation && violation.object) || "Global");
        const matchByTarget = (insights) => {
            const recommendations = Array.isArray(insights && insights.recommendations) ? insights.recommendations : [];
            return recommendations.find((item) =>
                String(item && item.source || "").trim().toUpperCase() === violationSource
                && String(item && item.target || "").trim() === String(violationTarget || "").trim()
            ) || null;
        };
        return matchByTarget(state.workspaceAnalysisInsights)
            || matchByTarget(state.analysisInsights)
            || ((state.workspaceAnalysisInsights && state.workspaceAnalysisInsights.recommendations && state.workspaceAnalysisInsights.recommendations[0]) || null)
            || ((state.analysisInsights && state.analysisInsights.recommendations && state.analysisInsights.recommendations[0]) || null);
    }

    function renderAnalysisInsights() {
        if (dom.dedupeSummary) {
            const dedupe = (state.analysisInsights && state.analysisInsights.dedupe) || {};
            if (!dedupe.displayedRowCount) {
                dom.dedupeSummary.className = "review-insight-empty";
                dom.dedupeSummary.textContent = "분석 후 중복 정리 요약이 여기에 표시됩니다.";
            } else {
                dom.dedupeSummary.className = "";
                dom.dedupeSummary.innerHTML = `<div class="review-insight-stats"><div class="review-insight-stat"><div class="review-insight-stat-label">원본 이슈</div><div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">현재 표시 행</div><div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">접힌 중복</div><div class="review-insight-stat-value">${escapeHtml(dedupe.collapsedDuplicateCount)}</div></div></div>`;
            }
        }
        if (!dom.priorityRecommendations) return;
        const recommendations = (state.analysisInsights && state.analysisInsights.recommendations) || [];
        state.recommendationInsightByRowId = buildRecommendationInsightIndex(state.analysisInsights);
        if (!recommendations.length) {
            dom.priorityRecommendations.className = "review-insight-empty";
            dom.priorityRecommendations.textContent = "분석 후 우선 검토 추천이 여기에 표시됩니다.";
            return;
        }
        dom.priorityRecommendations.className = "priority-list";
        dom.priorityRecommendations.replaceChildren();
        const frag = document.createDocumentFragment();
        recommendations.forEach((item, idx) => {
            const severityText = escapeHtml(
                String(
                    (typeof helpers.normalizeSeverityKeyword === "function"
                        ? helpers.normalizeSeverityKeyword(item && item.severity)
                        : (item && item.severity))
                    || "정보",
                ),
            );
            const card = document.createElement("div");
            card.className = "priority-item";
            card.tabIndex = 0;
            card.setAttribute("role", "button");
            card.setAttribute("aria-label", `${idx + 1}. ${String(item.target || "")} 우선 검토 추천 열기`);
            if (item && item.representativeRow && item.representativeRow.rowId) {
                card.setAttribute("data-row-id", String(item.representativeRow.rowId));
            }
            card.innerHTML = `<div class="priority-item-header"><div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div><div class="priority-item-score">점수 ${escapeHtml(item.score)}</div></div><div class="priority-item-meta">${escapeHtml(String(item.source).toUpperCase())} | ${severityText} | 행 ${escapeHtml(item.rowCount)} | 이슈 ${escapeHtml(item.duplicateCount)}</div><div class="priority-item-meta">hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)}건 | 규칙 ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)}건 | 폭 ${escapeHtml(item.ruleBreadth || 0)}</div><div class="priority-item-reason">${escapeHtml(item.reason || "집중도와 심각도가 높아 우선 검토 대상으로 적합합니다.")}</div><div class="priority-item-actions"><button type="button" class="priority-chip priority-chip-hotspot">hotspot 보기</button><button type="button" class="priority-chip priority-chip-rule">규칙 보기</button></div><div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "대표 메시지가 아직 없습니다."))}</div>`;
            const openRecommendation = () => {
                helpers.navWorkspace();
                state.activeRecommendationRowId = String(item && item.representativeRow && item.representativeRow.rowId || "").trim();
                markWorkspaceRowActive(state.activeRecommendationRowId);
                if (item && item.representativeRow && typeof item.representativeRow.onClick === "function") {
                    void item.representativeRow.onClick();
                    focusWorkspaceRow(item.representativeRow.rowId);
                }
            };
            card.querySelector(".priority-chip-hotspot")?.addEventListener("click", (event) => {
                event.stopPropagation();
                helpers.navWorkspace();
                applyRecommendationWorkspaceFilter("hotspot", String(item.hotspotObject || item.target || "Global"), normalizeInsightToken(item.hotspotObject || item.target, "global"), String(item.source || ""));
            });
            card.querySelector(".priority-chip-rule")?.addEventListener("click", (event) => {
                event.stopPropagation();
                helpers.navWorkspace();
                applyRecommendationWorkspaceFilter("rule_family", String(item.dominantRuleFamily || "UNKNOWN"), normalizeInsightToken(item.dominantRuleFamily, "unknown"), String(item.source || ""));
            });
            card.addEventListener("click", openRecommendation);
            card.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openRecommendation();
                }
            });
            frag.appendChild(card);
        });
        dom.priorityRecommendations.appendChild(frag);
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

    function getFilterState() {
        const read = (cb, fallback = true) => (cb ? !!cb.checked : fallback);
        return {
            sources: { p1: read(state.filterControls.p1), p2: read(state.filterControls.p2), p3: false },
            severities: { critical: read(state.filterControls.critical), warning: read(state.filterControls.warning), info: read(state.filterControls.info) },
        };
    }

    function buildWorkspaceFilterSummaryText() {
        const filters = getFilterState();
        const sourceLabels = [filters.sources.p1 ? "P1" : "", filters.sources.p2 ? "P2" : ""].filter(Boolean);
        const severityLabels = [filters.severities.critical ? "치명" : "", filters.severities.warning ? "경고" : "", filters.severities.info ? "정보" : ""].filter(Boolean);
        const recommendationText = buildRecommendationWorkspaceFilterText();
        const searchText = buildWorkspaceSearchStateLabel({
            fileQuery: state.workspaceFileQuery,
            resultQuery: state.workspaceResultQuery,
            quickPreset: state.workspaceQuickPreset,
        });
        const comparison = buildWorkspaceFilterComparisonSummary();
        const parts = [
            `출처: ${sourceLabels.length ? sourceLabels.join(", ") : "전체"}`,
            `심각도: ${severityLabels.length ? severityLabels.join(", ") : "전체"}`,
            recommendationText || "추천 필터 없음",
        ];
        if (searchText) parts.push(searchText);
        if (comparison.banner && recommendationText) parts.push(comparison.banner);
        return parts.join(" | ");
    }

    function renderWorkspaceFilterSummary() {
        if (!dom.workspaceFilterSummaryText) return;
        dom.workspaceFilterSummaryText.textContent = buildWorkspaceFilterSummaryText();
    }

    function findWorkspaceRowById(rowId, rows = state.workspaceFilteredRows) {
        const targetId = String(rowId || "").trim();
        if (!targetId) return null;
        const safeRows = Array.isArray(rows) ? rows : [];
        return safeRows.find((row) => String((row && row.rowId) || "").trim() === targetId) || null;
    }

    function buildActiveSelectionLabel() {
        const row = findWorkspaceRowById(state.activeWorkspaceRowId);
        if (!row) return buildWorkspaceSelectionSummary(null);
        return buildWorkspaceSelectionSummary({
            source: (row && row.source) || "P1",
            object: (row && row.object) || "Global",
            line: positiveLineOrZero(row && row.line) || "-",
        });
    }

    function renderWorkspaceCommandBar() {
        applyWorkspaceCodePaneHeight();
        const selectedCount = getSelectedFiles().length;
        const visibleCount = Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows.length : 0;
        const totalCount = Array.isArray(state.workspaceRowIndex) ? state.workspaceRowIndex.length : 0;
        const hiddenSuppressedCount = Array.isArray(state.workspaceRowIndex)
            ? state.workspaceRowIndex.filter((row) => shouldHideSuppressedP1Row(row, !!state.showSuppressedP1)).length
            : 0;
        const hasRows = visibleCount > 0;
        const hasActive = !!findWorkspaceRowById(state.activeWorkspaceRowId);
        const hasAi = !!(helpers.getInspectorAiEnabled && helpers.getInspectorAiEnabled());
        const hasQuickFilter = !!String((state.recommendationWorkspaceFilter && state.recommendationWorkspaceFilter.mode) || "").trim();
        const filters = getFilterState();
        const searchStateLabel = buildWorkspaceSearchStateLabel({
            fileQuery: state.workspaceFileQuery,
            resultQuery: state.workspaceResultQuery,
            quickPreset: state.workspaceQuickPreset,
        });
        const sourceStateLabel = [filters.sources.p1 ? "P1" : "", filters.sources.p2 ? "P2" : ""].filter(Boolean);
        const severityStateLabel = [
            filters.severities.critical ? "치명" : "",
            filters.severities.warning ? "경고" : "",
            filters.severities.info ? "정보" : "",
        ].filter(Boolean);
        const activeFilterText = [
            searchStateLabel,
            (!filters.sources.p1 || !filters.sources.p2) ? `출처 ${sourceStateLabel.join(", ") || "없음"}` : "",
            (!filters.severities.critical || !filters.severities.warning || !filters.severities.info) ? `심각도 ${severityStateLabel.join(", ") || "없음"}` : "",
            hasQuickFilter ? "추천 기준 적용" : "",
        ].filter(Boolean).join(" | ");
        const hasCustomFilter = !filters.sources.p1
            || !filters.sources.p2
            || !filters.severities.critical
            || !filters.severities.warning
            || !filters.severities.info
            || !!searchStateLabel;
        const commandSummaryText = buildWorkspaceCommandSummary({
            selectedCount,
            visibleCount,
            totalCount,
            hiddenSuppressedCount,
            activeFilterText,
        });
        const activeSelectionText = buildActiveSelectionLabel();
        const buttonState = deriveWorkspaceCommandButtonState({
            hasRows,
            hasActiveSelection: hasActive,
            hasAiAvailable: hasAi,
            hasQuickFilter,
            hasCustomFilter,
        });
        if (dom.workspaceCommandSummaryText) {
            dom.workspaceCommandSummaryText.textContent = commandSummaryText;
        }
        if (dom.workspaceCommandSelectionText) {
            dom.workspaceCommandSelectionText.textContent = activeSelectionText;
        }
        if (dom.analysisStripSummaryText) {
            dom.analysisStripSummaryText.textContent = commandSummaryText;
        }
        if (dom.analysisStripSummaryNote) {
            dom.analysisStripSummaryNote.textContent = activeSelectionText;
        }
        if (dom.dashboardAnalysisSummaryText) {
            dom.dashboardAnalysisSummaryText.textContent = commandSummaryText;
        }
        if (dom.dashboardAnalysisSummaryNote) {
            dom.dashboardAnalysisSummaryNote.textContent = activeSelectionText;
        }
        if (dom.workspaceCommandShowSuppressed) {
            dom.workspaceCommandShowSuppressed.checked = !!state.showSuppressedP1;
            dom.workspaceCommandShowSuppressed.disabled = !!state.p1TriageLoading;
            dom.workspaceCommandShowSuppressed.title = state.p1TriageError
                ? `P1 triage를 사용할 수 없습니다: ${state.p1TriageError}`
                : "검토 중 숨김 처리한 P1 항목을 다시 표시합니다.";
        }
        if (dom.workspaceCommandPrev) {
            dom.workspaceCommandPrev.disabled = buttonState.prevDisabled;
            dom.workspaceCommandPrev.title = buttonState.prevTitle;
        }
        if (dom.workspaceCommandNext) {
            dom.workspaceCommandNext.disabled = buttonState.nextDisabled;
            dom.workspaceCommandNext.title = buttonState.nextTitle;
        }
        if (dom.workspaceCommandJump) {
            dom.workspaceCommandJump.disabled = buttonState.jumpDisabled;
            dom.workspaceCommandJump.title = buttonState.jumpTitle;
        }
        if (dom.workspaceCommandDetail) {
            dom.workspaceCommandDetail.disabled = buttonState.detailDisabled;
            dom.workspaceCommandDetail.title = buttonState.detailTitle;
        }
        if (dom.workspaceCommandAi) {
            dom.workspaceCommandAi.disabled = buttonState.aiDisabled;
            dom.workspaceCommandAi.title = buttonState.aiTitle;
        }
        if (dom.workspaceCommandReset) {
            dom.workspaceCommandReset.disabled = buttonState.resetDisabled;
            dom.workspaceCommandReset.title = buttonState.resetTitle;
        }
        if (dom.workspacePresetAll) dom.workspacePresetAll.setAttribute("aria-pressed", state.workspaceQuickPreset === "all" ? "true" : "false");
        if (dom.workspacePresetP1) dom.workspacePresetP1.setAttribute("aria-pressed", state.workspaceQuickPreset === "p1_only" ? "true" : "false");
        if (dom.workspacePresetAttention) dom.workspacePresetAttention.setAttribute("aria-pressed", state.workspaceQuickPreset === "attention_only" ? "true" : "false");
        if (dom.workspaceFileSearch) dom.workspaceFileSearch.value = String(state.workspaceFileQuery || "");
        if (dom.workspaceResultSearch) dom.workspaceResultSearch.value = String(state.workspaceResultQuery || "");
        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                selected_file_count: selectedCount,
                workspace_hidden_suppressed_count: hiddenSuppressedCount,
            });
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

    function shouldRenderRow(source, severity) {
        const filters = getFilterState();
        const srcKey = helpers.sourceFilterKey(source);
        const sevKey = helpers.severityFilterKey(severity);
        return !!filters.sources[srcKey] && !!filters.severities[sevKey];
    }

    async function runWorkspaceSelection(violation, eventName, selectionToken) {
        const pendingLine = helpers.pendingJumpLineForViolation(violation);
        helpers.setActiveJumpRequestState("pending", pendingLine);
        helpers.showDetail(violation, eventName, { jumpPendingLine: pendingLine });
        const jumpResult = await helpers.jumpCodeViewerToViolation(violation);
        if (selectionToken !== state.workspaceSelectionToken) return;
        if (!jumpResult || !jumpResult.ok) helpers.setActiveJumpRequestState("failed", pendingLine);
        helpers.showDetail(violation, eventName, { jumpResult });
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
            suppressedBadge.textContent = "숨김";
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
        state.workspaceFilteredRows = (state.workspaceRowIndex || []).filter(
            (row) => shouldRenderRow(row.source, row.severity)
                && rowMatchesWorkspaceQuickPreset(row, state.workspaceQuickPreset)
                && rowMatchesWorkspaceResultQuery(row, state.workspaceResultQuery)
                && rowMatchesRecommendationFilter(row)
                && !shouldHideSuppressedP1Row(row, !!state.showSuppressedP1),
        );
        state.workspaceAnalysisInsights = deriveAnalysisInsights(excludeSuppressedP1Rows(state.workspaceFilteredRows), helpers);
        state.workspaceRecommendationInsightByRowId = buildRecommendationInsightIndex(state.workspaceAnalysisInsights);
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

    function getSelectedFiles() {
        const selectedSet = state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : new Set();
        return (Array.isArray(state.workspaceAvailableFiles) ? state.workspaceAvailableFiles : [])
            .map((fileLike) => getWorkspaceFileName(fileLike))
            .filter((fileName) => selectedSet.has(fileName));
    }

    function getSelectedInputSources() {
        return state.sessionInputSources.map((item) => ({
            type: String(item.type || ""),
            value: String(item.value || ""),
        }));
    }

    function syncWorkspaceFileSelection(files = []) {
        const safeFiles = Array.isArray(files) ? files : [];
        const previousFiles = Array.isArray(state.workspaceAvailableFiles) ? state.workspaceAvailableFiles : [];
        const previousSelection = state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : new Set();
        const allFileNames = safeFiles
            .map((fileLike) => getWorkspaceFileName(fileLike))
            .filter(Boolean);
        const availableSet = new Set(allFileNames);
        const preservedSelection = new Set(
            Array.from(previousSelection)
                .filter((fileName) => availableSet.has(fileName)),
        );
        const shouldPreserveExplicitEmpty = previousFiles.length > 0 && previousSelection.size === 0;
        if (!preservedSelection.size && !shouldPreserveExplicitEmpty) {
            allFileNames.forEach((fileName) => preservedSelection.add(fileName));
        }
        state.workspaceAvailableFiles = safeFiles;
        state.workspaceSelectedFiles = preservedSelection;
    }

    function getVisibleWorkspaceFiles() {
        return filterWorkspaceFilesByQuery(state.workspaceAvailableFiles, state.workspaceFileQuery);
    }

    function renderFileList(files, options = {}) {
        applyWorkspaceCodePaneHeight();
        if (!dom.fileList) return;
        dom.fileList.replaceChildren();
        const safeFiles = Array.isArray(files) ? files : [];
        syncWorkspaceFileSelection(safeFiles);
        const visibleFiles = getVisibleWorkspaceFiles();
        const emptyMessage = buildWorkspaceFileListEmptyMessage({
            totalFileCount: safeFiles.length,
            fileQuery: state.workspaceFileQuery,
            fallbackMessage: String((options && options.emptyMessage) || "").trim(),
        });

        const selectAllWrap = document.createElement("div");
        selectAllWrap.className = "sidebar-select-all";
        const chkAll = document.createElement("input");
        chkAll.type = "checkbox";
        chkAll.id = "chk-all";
        chkAll.checked = visibleFiles.length > 0 && visibleFiles.every((fileLike) => state.workspaceSelectedFiles.has(getWorkspaceFileName(fileLike)));
        chkAll.indeterminate = visibleFiles.length > 0 && !chkAll.checked && visibleFiles.some((fileLike) => state.workspaceSelectedFiles.has(getWorkspaceFileName(fileLike)));
        const chkAllLabel = document.createElement("strong");
        chkAllLabel.textContent = "현재 표시 파일 전체 선택";
        selectAllWrap.append(chkAll, " ", chkAllLabel);
        dom.fileList.appendChild(selectAllWrap);

        visibleFiles.forEach((file) => {
            const fileName = getWorkspaceFileName(file);
            const row = document.createElement("div");
            row.className = "file-item";
            row.style.cursor = "pointer";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = state.workspaceSelectedFiles.has(fileName);
            cb.setAttribute("data-file", fileName);
            cb.addEventListener("click", (event) => event.stopPropagation());
            cb.addEventListener("change", () => {
                const nextSelection = new Set(state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : []);
                if (cb.checked) nextSelection.add(fileName);
                else nextSelection.delete(fileName);
                state.workspaceSelectedFiles = nextSelection;
                renderWorkspaceCommandBar();
            });
            const label = document.createElement("span");
            label.className = "file-item-label";
            label.textContent = fileName;
            row.append(cb, label);
            row.addEventListener("click", () => {
                void helpers.loadCodeViewer(fileName).catch(() => {});
            });
            dom.fileList.appendChild(row);
        });

        if (!visibleFiles.length) {
            const empty = document.createElement("div");
            empty.className = "file-item file-item-empty";
            empty.textContent = emptyMessage;
            dom.fileList.appendChild(empty);
        }

        chkAll.addEventListener("change", () => {
            const checked = chkAll.checked;
            const nextSelection = new Set(state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : []);
            visibleFiles.forEach((fileLike) => {
                const fileName = getWorkspaceFileName(fileLike);
                if (!fileName) return;
                if (checked) nextSelection.add(fileName);
                else nextSelection.delete(fileName);
            });
            state.workspaceSelectedFiles = nextSelection;
            dom.fileList.querySelectorAll("input[type='checkbox'][data-file]").forEach((cb) => {
                cb.checked = checked;
            });
            renderWorkspaceCommandBar();
        });

        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                file_list_status: safeFiles.length ? "ready" : "empty",
                file_list_dom_count: visibleFiles.length,
                file_list_empty_message: emptyMessage,
                file_list_query: String(state.workspaceFileQuery || ""),
            });
        }
        renderWorkspaceCommandBar();
    }

    async function loadFiles() {
        applyWorkspaceCodePaneHeight();
        const response = await fetch("/api/files");
        if (!response.ok) {
            state.workspaceAvailableFiles = [];
            state.workspaceSelectedFiles = new Set();
            renderFileList([], { emptyMessage: `파일 목록을 불러오지 못했습니다. (${response.status})` });
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    file_list_status: "http_error",
                    file_list_http_status: response.status,
                });
            }
            throw new Error(`파일 목록을 불러오지 못했습니다. (${response.status})`);
        }
        const payload = await response.json();
        if (!payload || !Array.isArray(payload.files)) {
            state.workspaceAvailableFiles = [];
            state.workspaceSelectedFiles = new Set();
            renderFileList([], { emptyMessage: "파일 목록 응답 형식이 올바르지 않습니다." });
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    file_list_status: "invalid_payload",
                    file_list_http_status: response.status,
                    file_list_payload_keys: payload && typeof payload === "object" ? Object.keys(payload) : [],
                });
            }
            return;
        }
        renderFileList(payload.files || []);
        helpers.renderExternalInputSources();
    }

    function setWorkspaceFileQuery(query = "") {
        state.workspaceFileQuery = String(query || "");
        renderFileList(state.workspaceAvailableFiles || []);
        renderWorkspaceFilterSummary();
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
