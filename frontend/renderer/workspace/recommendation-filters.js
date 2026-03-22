import {
    basenamePath,
    escapeHtml,
    normalizeInsightToken,
    positiveLineOrZero,
    truncateUiText,
} from "../utils.js";
import { shouldHideSuppressedP1Row } from "../p1-triage.js";
import {
    buildWorkspaceCommandSummary,
    buildWorkspaceSelectionSummary,
    deriveWorkspaceCommandButtonState,
} from "../workspace-chrome-helpers.js";
import {
    buildWorkspaceSearchStateLabel,
    rowMatchesWorkspaceQuickPreset,
    rowMatchesWorkspaceResultQuery,
} from "../workspace-search-helpers.js";
import {
    buildRecommendationInsightIndex,
    deriveAnalysisInsights,
    getRowHotspotKey,
    getRowRuleFamilies,
} from "./recommendations.js";

export function createWorkspaceRecommendationController({
    dom,
    state,
    helpers,
    getSelectedFiles,
    findWorkspaceRowById,
    markWorkspaceRowActive,
    focusWorkspaceRow,
    renderWorkspace,
    queueResultTableWindowRender,
}) {
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
        return `${mode === "rule_family" ? "우선 규칙 필터" : "우선 hotspot 필터"}: ${label}${source ? ` | ${source.toUpperCase()}` : ""}`;
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
            banner: `표시 행 ${currentRows}/${overallRows} | 이슈 ${currentIssues}/${overallIssues} | 제외 ${rowDelta}/${issueDelta}`,
            detail: `전체 ${overallRows}개 행과 ${overallIssues}개 이슈 중 현재 기준으로 ${currentRows}개 결과와 ${currentIssues}개 이슈를 보고 있습니다. 숨겨진 항목은 ${rowDelta}개 행 / ${issueDelta}개 이슈입니다.`,
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
        dom.workspaceQuickFilterText.textContent = `${prefix}: ${label}${source ? ` | ${source.toUpperCase()}` : ""} | 행 ${dedupe.displayedRowCount || 0} | 이슈 ${dedupe.rawIssueCount || 0}${topRecommendation ? ` | 대표 규칙 ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` | ${comparison.banner}` : ""}`;
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
                dom.dedupeSummary.innerHTML = `<div class="review-insight-stats"><div class="review-insight-stat"><div class="review-insight-stat-label">원본 이슈</div><div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">현재 표시 수</div><div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">접힌 중복</div><div class="review-insight-stat-value">${escapeHtml(dedupe.collapsedDuplicateCount)}</div></div></div>`;
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
            card.innerHTML = `<div class="priority-item-header"><div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div><div class="priority-item-score">점수 ${escapeHtml(item.score)}</div></div><div class="priority-item-meta">${escapeHtml(String(item.source).toUpperCase())} | ${severityText} | 행 ${escapeHtml(item.rowCount)} | 이슈 ${escapeHtml(item.duplicateCount)}</div><div class="priority-item-meta">hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)}건 | 규칙 ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)}건 | 폭 ${escapeHtml(item.ruleBreadth || 0)}</div><div class="priority-item-reason">${escapeHtml(item.reason || "집중 우선순위 감각이 높아 우선 검토 대상으로 적합합니다.")}</div><div class="priority-item-actions"><button type="button" class="priority-chip priority-chip-hotspot">hotspot 보기</button><button type="button" class="priority-chip priority-chip-rule">규칙 보기</button></div><div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "대표 메시지가 아직 없습니다."))}</div>`;
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
        const buttonState = deriveWorkspaceCommandButtonState({
            hasRows,
            hasActiveSelection: hasActive,
            hasAiAvailable: hasAi,
            hasQuickFilter,
            hasCustomFilter,
        });
        if (dom.workspaceCommandSummaryText) {
            dom.workspaceCommandSummaryText.textContent = buildWorkspaceCommandSummary({
                selectedCount,
                visibleCount,
                totalCount,
                hiddenSuppressedCount,
                activeFilterText,
            });
        }
        if (dom.workspaceCommandSelectionText) {
            dom.workspaceCommandSelectionText.textContent = buildActiveSelectionLabel();
        }
        if (dom.workspaceCommandShowSuppressed) {
            dom.workspaceCommandShowSuppressed.checked = !!state.showSuppressedP1;
            dom.workspaceCommandShowSuppressed.disabled = !!state.p1TriageLoading;
            dom.workspaceCommandShowSuppressed.title = state.p1TriageError
                ? `P1 triage를 사용할 수 없습니다: ${state.p1TriageError}`
                : "검토 중 제외 처리한 P1 항목을 다시 표시합니다.";
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

    function shouldRenderRow(source, severity) {
        const filters = getFilterState();
        const srcKey = helpers.sourceFilterKey(source);
        const sevKey = helpers.severityFilterKey(severity);
        return !!filters.sources[srcKey] && !!filters.severities[sevKey];
    }

    function applyWorkspaceFilters(rows = []) {
        const nextRows = (Array.isArray(rows) ? rows : []).filter(
            (row) => shouldRenderRow(row.source, row.severity)
                && rowMatchesWorkspaceQuickPreset(row, state.workspaceQuickPreset)
                && rowMatchesWorkspaceResultQuery(row, state.workspaceResultQuery)
                && rowMatchesRecommendationFilter(row)
                && !shouldHideSuppressedP1Row(row, !!state.showSuppressedP1),
        );
        state.workspaceAnalysisInsights = deriveAnalysisInsights(nextRows, helpers);
        state.workspaceRecommendationInsightByRowId = buildRecommendationInsightIndex(state.workspaceAnalysisInsights);
        return nextRows;
    }

    return {
        applyRecommendationWorkspaceFilter,
        applyWorkspaceFilters,
        buildRecommendationWorkspaceFilterText,
        buildWorkspaceFilterSummaryText,
        clearRecommendationWorkspaceFilter,
        findRecommendationInsightForViolation,
        getFilterState,
        queueResultTableWindowRender,
        renderAnalysisInsights,
        renderWorkspaceCommandBar,
        renderWorkspaceFilterSummary,
        renderWorkspaceQuickFilter,
        rowMatchesRecommendationFilter,
    };
}
