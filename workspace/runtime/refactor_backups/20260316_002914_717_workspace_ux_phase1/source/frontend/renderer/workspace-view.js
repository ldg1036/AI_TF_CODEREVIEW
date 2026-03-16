import {
    basenamePath,
    escapeHtml,
    normalizeInsightToken,
    positiveLineOrZero,
    scoreSeverityWeight,
    scoreSourceWeight,
    truncateUiText,
    violationDisplayFile,
    violationResolvedFile,
} from "./utils.js";
import { buildReviewedP1SyncPlan } from "./reviewed-linking.js";

export function createWorkspaceController({ dom, state, caches, virtualState, helpers }) {
    function buildRecommendationReason(item) {
        const reasons = [];
        const duplicateCount = Math.max(0, Number.parseInt(item && item.duplicateCount, 10) || 0);
        const hotspotIssueCount = Math.max(0, Number.parseInt(item && item.hotspotIssueCount, 10) || 0);
        const ruleBreadth = Math.max(0, Number.parseInt(item && item.ruleBreadth, 10) || 0);
        const dominantRuleCount = Math.max(0, Number.parseInt(item && item.dominantRuleCount, 10) || 0);
        const severityKey = helpers.severityFilterKey(item && item.severity);
        const sourceKey = helpers.sourceFilterKey(item && item.source);
        if (severityKey === "critical") reasons.push("Critical severity needs review");
        else if (severityKey === "warning") reasons.push("Warning severity needs review");
        if (duplicateCount >= 4) reasons.push(`Duplicate impact ${duplicateCount} issues`);
        if (hotspotIssueCount >= 3) reasons.push(`${String(item && item.hotspotObject || item && item.target || "Global")} hotspot ${hotspotIssueCount} issues`);
        if (dominantRuleCount >= 2) reasons.push(`${String(item && item.dominantRuleFamily || "RULE")} repeated ${dominantRuleCount} times`);
        if (ruleBreadth >= 3) reasons.push(`Cross-rule overlap ${ruleBreadth} families`);
        if (sourceKey === "p1") reasons.push("Static rule priority");
        else if (sourceKey === "p2") reasons.push("Ctrlpp static analysis priority");
        else if (sourceKey === "p3") reasons.push("AI follow-up recommended");
        return reasons.slice(0, 3).join(" | ") || "High concentration and severity make this a good first review target.";
    }

    function getRowHotspotKey(row) {
        const hotspot = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
        return normalizeInsightToken(hotspot, "global");
    }

    function getRowRuleFamilies(row) {
        const ruleIds = Array.isArray(row && row.ruleIds) ? row.ruleIds : [];
        return Array.from(new Set(
            ruleIds
                .map((ruleId) => normalizeInsightToken(String(ruleId || "").split("-")[0] || ruleId, "unknown"))
                .filter(Boolean),
        ));
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
        return `${mode === "rule_family" ? "Active rule filter" : "Active hotspot filter"}: ${label}${source ? ` | ${source.toUpperCase()}` : ""}`;
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
            banner: `Filtered rows ${currentRows}/${overallRows} | issues ${currentIssues}/${overallIssues} | hidden ${rowDelta}/${issueDelta}`,
            detail: `Out of ${overallRows} rows and ${overallIssues} issues, the current filter keeps ${currentRows} rows and ${currentIssues} issues. Hidden items: ${rowDelta} rows and ${issueDelta} issues.`,
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
        const prefix = mode === "rule_family" ? "Rule focus" : "Hotspot focus";
        dom.workspaceQuickFilter.classList.remove("hidden");
        dom.workspaceQuickFilterText.textContent = `${prefix}: ${label}${source ? ` | ${source.toUpperCase()}` : ""} | rows ${dedupe.displayedRowCount || 0} | issues ${dedupe.rawIssueCount || 0}${topRecommendation ? ` | Top ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` | ${comparison.banner}` : ""}`;
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

    function deriveAnalysisInsights(rows) {
        const safeRows = Array.isArray(rows) ? rows : [];
        const dedupe = { rawIssueCount: 0, displayedRowCount: safeRows.length, collapsedDuplicateCount: 0 };
        const grouped = new Map();
        safeRows.forEach((row, index) => {
            const duplicateCount = Math.max(1, Number.parseInt(row && row.duplicateCount, 10) || 1);
            dedupe.rawIssueCount += duplicateCount;
            dedupe.collapsedDuplicateCount += Math.max(0, duplicateCount - 1);
            const source = String((row && row.source) || "P1");
            const target = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
            const key = `${source}||${target}`;
            if (!grouped.has(key)) {
                grouped.set(key, {
                    source,
                    target,
                    severity: row && row.severity || "Info",
                    rowCount: 0,
                    duplicateCount: 0,
                    messages: [],
                    firstIndex: index,
                    representativeRow: row || null,
                    objectCounts: new Map(),
                    objectLabels: new Map(),
                    ruleFamilyCounts: new Map(),
                    uniqueRuleIds: new Set(),
                    severityTotal: 0,
                    sourceTotal: 0,
                    duplicateBonusTotal: 0,
                });
            }
            const current = grouped.get(key);
            current.rowCount += 1;
            current.duplicateCount += duplicateCount;
            current.severity = helpers.pickHigherSeverity(current.severity, row && row.severity || "Info");
            current.severityTotal += scoreSeverityWeight(row && row.severity);
            current.sourceTotal += scoreSourceWeight(source);
            current.duplicateBonusTotal += Math.min(6, duplicateCount - 1);
            if (!current.representativeRow || scoreSeverityWeight(row && row.severity) >= scoreSeverityWeight(current.representativeRow && current.representativeRow.severity)) {
                current.representativeRow = row || current.representativeRow;
            }
            const message = String((row && row.message) || "").trim();
            if (message && current.messages.length < 3) current.messages.push(message);
            const hotspotObject = basenamePath((row && row.object) || "") || String((row && row.object) || target || "Global");
            const objectKey = normalizeInsightToken(hotspotObject);
            current.objectCounts.set(objectKey, (current.objectCounts.get(objectKey) || 0) + duplicateCount);
            if (!current.objectLabels.has(objectKey)) current.objectLabels.set(objectKey, hotspotObject);
            (Array.isArray(row && row.ruleIds) ? row.ruleIds : []).forEach((ruleId) => {
                const normalizedRuleId = String(ruleId || "").trim();
                if (!normalizedRuleId) return;
                current.uniqueRuleIds.add(normalizedRuleId);
                const family = normalizeInsightToken(normalizedRuleId.split("-")[0] || normalizedRuleId, "unknown");
                current.ruleFamilyCounts.set(family, (current.ruleFamilyCounts.get(family) || 0) + 1);
            });
        });
        const recommendations = Array.from(grouped.values())
            .map((item) => {
                let hotspotObject = item.target;
                let hotspotIssueCount = 0;
                item.objectCounts.forEach((count, objectKey) => {
                    if (count > hotspotIssueCount) {
                        hotspotIssueCount = count;
                        hotspotObject = item.objectLabels.get(objectKey) || objectKey;
                    }
                });
                let dominantRuleFamily = "unknown";
                let dominantRuleCount = 0;
                item.ruleFamilyCounts.forEach((count, family) => {
                    if (count > dominantRuleCount) {
                        dominantRuleCount = count;
                        dominantRuleFamily = family;
                    }
                });
                const score = item.severityTotal + item.sourceTotal + item.duplicateBonusTotal + Math.min(6, Math.max(0, hotspotIssueCount - 1)) + Math.min(4, item.uniqueRuleIds.size) + Math.min(5, Math.max(0, dominantRuleCount - 1));
                return {
                    ...item,
                    score,
                    hotspotObject,
                    hotspotIssueCount,
                    ruleBreadth: item.uniqueRuleIds.size,
                    dominantRuleFamily: dominantRuleFamily.toUpperCase(),
                    dominantRuleCount,
                };
            })
            .sort((a, b) => (b.score - a.score) || (b.duplicateCount - a.duplicateCount) || (b.rowCount - a.rowCount) || (a.firstIndex - b.firstIndex))
            .slice(0, 5)
            .map((item) => ({ ...item, leadMessage: item.messages[0] || "", reason: buildRecommendationReason(item) }));
        return { dedupe, recommendations };
    }

    function buildRecommendationInsightIndex(insights) {
        const index = new Map();
        (Array.isArray(insights && insights.recommendations) ? insights.recommendations : []).forEach((item) => {
            const rowId = String(item && item.representativeRow && item.representativeRow.rowId || "").trim();
            if (rowId) index.set(rowId, item);
        });
        return index;
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
                dom.dedupeSummary.textContent = "No dedupe summary is available yet.";
            } else {
                dom.dedupeSummary.className = "";
                dom.dedupeSummary.innerHTML = `<div class="review-insight-stats"><div class="review-insight-stat"><div class="review-insight-stat-label">Raw issues</div><div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">Displayed rows</div><div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">Collapsed duplicates</div><div class="review-insight-stat-value">${escapeHtml(dedupe.collapsedDuplicateCount)}</div></div></div>`;
            }
        }
        if (!dom.priorityRecommendations) return;
        const recommendations = (state.analysisInsights && state.analysisInsights.recommendations) || [];
        state.recommendationInsightByRowId = buildRecommendationInsightIndex(state.analysisInsights);
        if (!recommendations.length) {
            dom.priorityRecommendations.className = "review-insight-empty";
            dom.priorityRecommendations.textContent = "No priority recommendations are available yet.";
            return;
        }
        dom.priorityRecommendations.className = "priority-list";
        dom.priorityRecommendations.replaceChildren();
        const frag = document.createDocumentFragment();
        recommendations.forEach((item, idx) => {
            const card = document.createElement("div");
            card.className = "priority-item";
            card.tabIndex = 0;
            card.setAttribute("role", "button");
            card.setAttribute("aria-label", `${idx + 1}. ${String(item.target || "")} open priority recommendation`);
            if (item && item.representativeRow && item.representativeRow.rowId) {
                card.setAttribute("data-row-id", String(item.representativeRow.rowId));
            }
            card.innerHTML = `<div class="priority-item-header"><div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div><div class="priority-item-score">Score ${escapeHtml(item.score)}</div></div><div class="priority-item-meta">${escapeHtml(String(item.source).toUpperCase())} | ${escapeHtml(String(item.severity || "Info"))} | rows ${escapeHtml(item.rowCount)} | issues ${escapeHtml(item.duplicateCount)}</div><div class="priority-item-meta">hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)} items | rule ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)} items | breadth ${escapeHtml(item.ruleBreadth || 0)}</div><div class="priority-item-reason">${escapeHtml(item.reason || "This cluster is a strong candidate for first review.")}</div><div class="priority-item-actions"><button type="button" class="priority-chip priority-chip-hotspot">View hotspot</button><button type="button" class="priority-chip priority-chip-rule">View rule</button></div><div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "No lead message is available yet."))}</div>`;
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
        const severityLabels = [filters.severities.critical ? "Critical" : "", filters.severities.warning ? "Warning" : "", filters.severities.info ? "Info" : ""].filter(Boolean);
        const recommendationText = buildRecommendationWorkspaceFilterText();
        const comparison = buildWorkspaceFilterComparisonSummary();
        const parts = [`Sources ${sourceLabels.length ? sourceLabels.join(", ") : "All"}`, `Severity ${severityLabels.length ? severityLabels.join(", ") : "All"}`, recommendationText || "No recommendation filter"];
        if (comparison.banner && recommendationText) parts.push(comparison.banner);
        return parts.join(" | ");
    }

    function renderWorkspaceFilterSummary() {
        if (!dom.workspaceFilterSummaryText) return;
        dom.workspaceFilterSummaryText.textContent = buildWorkspaceFilterSummaryText();
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
        const sourceCell = document.createElement("td");
        sourceCell.className = "result-cell result-cell-source";
        const sourceBadge = document.createElement("span");
        sourceBadge.className = `badge badge-${String(source || "").toLowerCase()}`;
        sourceBadge.textContent = String(source || "N/A");
        sourceCell.appendChild(sourceBadge);
        const objectCell = document.createElement("td");
        objectCell.className = "result-cell result-cell-object";
        const objectTitle = document.createElement("div");
        objectTitle.className = "result-object-title";
        objectTitle.textContent = object || "N/A";
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
        const primaryRuleId = Array.isArray(rowData && rowData.ruleIds) ? String(rowData.ruleIds[0] || "").trim() : "";
        if (lineNo > 0) metaParts.push(`line ${lineNo}`);
        if (primaryRuleId) metaParts.push(primaryRuleId);
        if (Number.parseInt(rowData && rowData.duplicateCount, 10) > 1) metaParts.push(`duplicates ${Number.parseInt(rowData && rowData.duplicateCount, 10)}`);
        messageMeta.textContent = metaParts.join(" | ");
        if (messageMeta.textContent) messageCell.appendChild(messageMeta);
        row.append(sourceCell, objectCell, severityCell, messageCell);
        row.onclick = async () => {
            const selectionToken = ++state.workspaceSelectionToken;
            markWorkspaceRowActive(rowId);
            state.activeRecommendationRowId = state.recommendationInsightByRowId.has(String(rowId || "").trim()) ? String(rowId || "").trim() : "";
            syncWorkspaceRowHighlight();
            helpers.navWorkspace();
            await new Promise((resolve) => window.requestAnimationFrame(resolve));
            if (typeof (rowData && rowData.onClick) === "function") void rowData.onClick(selectionToken);
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
            emptyCell.textContent = "No results match the current filter. Loosen the filter or clear the quick filter to see more items.";
            emptyRow.appendChild(emptyCell);
            dom.resultBody.appendChild(emptyRow);
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    result_row_count: 0,
                    workspace_filtered_row_count: 0,
                });
            }
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
    }

    function buildWorkspaceRowIndex() {
        const nextRows = [];
        const violations = (state.analysisData && state.analysisData.violations) || {};
        const p1Groups = Array.isArray(violations.P1) ? violations.P1 : [];
        const p2List = Array.isArray(violations.P2) ? violations.P2 : [];
        const p1Rows = [];

        const pushP1Row = (baseViolation, eventName, syncState, originLabel, matchedItems = [], overrideMessage = "", syncReason = "") => {
            const lines = matchedItems.map((item) => positiveLineOrZero(item.violation && item.violation.line)).filter((line) => line > 0);
            const baseLines = Array.isArray(baseViolation._duplicate_lines) ? baseViolation._duplicate_lines : [];
            const uniqueLines = Array.from(new Set(lines.concat(baseLines).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
            const primaryLine = positiveLineOrZero(baseViolation._primary_line || baseViolation.line) || uniqueLines[0] || 0;
            const groupedRules = Array.from(new Set(matchedItems.map((item) => String(item.violation && item.violation.rule_id || "").trim()).filter(Boolean)));
            const baseGroupedRules = Array.isArray(baseViolation._group_rule_ids) ? baseViolation._group_rule_ids : [];
            groupedRules.push(...baseGroupedRules.map((value) => String(value || "").trim()).filter(Boolean));
            if (!groupedRules.length && baseViolation.rule_id) groupedRules.push(String(baseViolation.rule_id));
            const groupedMessages = Array.from(new Set(matchedItems.map((item) => String(item.violation && item.violation.message || "").trim()).filter(Boolean)));
            const baseGroupedMessages = Array.isArray(baseViolation._group_messages) ? baseViolation._group_messages : [];
            groupedMessages.push(...baseGroupedMessages.map((value) => String(value || "").trim()).filter(Boolean));
            if (!groupedMessages.length && overrideMessage) groupedMessages.push(overrideMessage);
            if (!groupedMessages.length && baseViolation.message) groupedMessages.push(String(baseViolation.message));
            const groupedIssues = Array.from(new Set(matchedItems.map((item) => String(item.violation && item.violation.issue_id || "").trim()).filter(Boolean)));
            const baseGroupedIssues = Array.isArray(baseViolation._group_issue_ids) ? baseViolation._group_issue_ids : [];
            groupedIssues.push(...baseGroupedIssues.map((value) => String(value || "").trim()).filter(Boolean));
            if (!groupedIssues.length && baseViolation.issue_id) groupedIssues.push(String(baseViolation.issue_id));
            const duplicateCountFromBase = Number.parseInt(baseViolation._duplicate_count, 10);
            const duplicateCount = Number.isFinite(duplicateCountFromBase) && duplicateCountFromBase > 0 ? duplicateCountFromBase : Math.max(1, matchedItems.length || 1);

            const enriched = {
                ...baseViolation,
                priority_origin: "P1",
                line: primaryLine || baseViolation.line || 0,
                _duplicate_count: duplicateCount,
                _duplicate_lines: uniqueLines,
                _primary_line: primaryLine,
                _grouping_mode: String(baseViolation._grouping_mode || "reviewed_block"),
                _group_rule_ids: Array.from(new Set(groupedRules)),
                _group_messages: Array.from(new Set(groupedMessages)),
                _group_issue_ids: Array.from(new Set(groupedIssues)),
                _sync_state: syncState,
                _sync_origin: originLabel,
                _sync_reason: syncReason || "",
            };
            const jumpReadyViolation = helpers.applyPrecomputedJumpTarget(enriched, "reviewed");
            const rowMessage = String(baseViolation.message || overrideMessage || "");
            p1Rows.push({
                rowId: `p1:${jumpReadyViolation.issue_id || `${jumpReadyViolation.object || "global"}:${jumpReadyViolation.line || 0}:${rowMessage}`}`,
                source: "P1",
                object: violationDisplayFile(baseViolation, "Global") || "Global",
                severity: baseViolation.severity || "Info",
                message: rowMessage,
                file: violationResolvedFile(baseViolation),
                line: primaryLine || baseViolation.line || 0,
                issueId: jumpReadyViolation.issue_id || "",
                duplicateCount,
                ruleIds: Array.from(new Set(groupedRules)),
                onClick: async (selectionToken) => {
                    await runWorkspaceSelection(jumpReadyViolation, eventName || "Global", selectionToken);
                },
            });
        };

        const {
            rowPlans,
            leftoverCount: violationOnlyCount,
            syncedCount,
            reviewOnlyCount,
            mappingDiagnostics,
        } = buildReviewedP1SyncPlan({
            p1Groups,
            reviewedTodoCacheByFile: caches.reviewedTodoCacheByFile,
            pickHigherSeverity: helpers.pickHigherSeverity,
        });

        rowPlans.forEach((plan) => {
            pushP1Row(
                plan.baseViolation,
                plan.eventName,
                plan.syncState,
                plan.originLabel,
                plan.matchedItems,
                plan.overrideMessage,
                plan.syncReason,
            );
        });

        if (p1Rows.length > 0) {
            console.debug("[P1 sync]", {
                synced_count: syncedCount,
                review_only_count: reviewOnlyCount,
                violation_only_count: violationOnlyCount,
                rows: p1Rows.length,
            });
            console.debug("[P1 mapping diagnostics]", mappingDiagnostics);
        }
        nextRows.push(...p1Rows);

        p2List.forEach((v) => {
            const objectName = String(v.object || "Global");
            const fileFromPayload = violationDisplayFile(v);
            const fileFromObject = /\.ctl$/i.test(objectName) ? basenamePath(objectName) : "";
            const fileHint = fileFromPayload || fileFromObject;
            const displayObject = fileHint || objectName || "Global";
            const p2Violation = {
                ...v,
                object: displayObject,
                file: String(v.file_path || v.file || fileHint || ""),
                file_path: String(v.file_path || v.file || fileHint || ""),
                priority_origin: v.priority_origin || "P2",
                issue_id: String(v.issue_id || `P2::${fileHint || displayObject}:${String(v.rule_id || "")}:${positiveLineOrZero(v.line)}`),
            };
            const jumpReadyP2Violation = helpers.applyPrecomputedJumpTarget(p2Violation, "source");
            const p2Localized = helpers.buildP2LocalizedMessage(p2Violation);
            nextRows.push({
                rowId: `p2:${jumpReadyP2Violation.issue_id || `${jumpReadyP2Violation.object || "global"}:${jumpReadyP2Violation.line || 0}:${p2Localized.shortText}`}`,
                source: jumpReadyP2Violation.priority_origin || "P2",
                object: jumpReadyP2Violation.object || "Global",
                severity: jumpReadyP2Violation.severity || jumpReadyP2Violation.type || "Info",
                message: p2Localized.shortText,
                file: String(jumpReadyP2Violation.file_path || jumpReadyP2Violation.file || ""),
                line: positiveLineOrZero(jumpReadyP2Violation.line),
                issueId: jumpReadyP2Violation.issue_id || "",
                duplicateCount: 1,
                ruleIds: [String(jumpReadyP2Violation.rule_id || "").trim()].filter(Boolean),
                onClick: async (selectionToken) => {
                    await runWorkspaceSelection(jumpReadyP2Violation, "Global", selectionToken);
                },
            });
        });

        state.workspaceRowIndex = nextRows;
        state.analysisInsights = deriveAnalysisInsights(nextRows);
    }

    function renderWorkspace(options = {}) {
        state.workspaceRenderToken += 1;
        state.workspaceFilteredRows = (state.workspaceRowIndex || []).filter((row) => shouldRenderRow(row.source, row.severity) && rowMatchesRecommendationFilter(row));
        state.workspaceAnalysisInsights = deriveAnalysisInsights(state.workspaceFilteredRows);
        state.workspaceRecommendationInsightByRowId = buildRecommendationInsightIndex(state.workspaceAnalysisInsights);
        if (state.activeWorkspaceRowId && !(state.workspaceFilteredRows || []).some((row) => String(row.rowId || "") === String(state.activeWorkspaceRowId))) {
            state.activeWorkspaceRowId = "";
        }
        if ((options && options.resetScroll !== false) && dom.resultTableWrap) {
            dom.resultTableWrap.scrollTop = 0;
        }
        renderWorkspaceQuickFilter();
        renderWorkspaceFilterSummary();
        queueResultTableWindowRender(true);
    }

    function getSelectedFiles() {
        return Array.from((dom.fileList || document.createElement("div")).querySelectorAll("input[type='checkbox'][data-file]"))
            .filter((cb) => cb.checked)
            .map((cb) => cb.getAttribute("data-file"));
    }

    function getSelectedInputSources() {
        return state.sessionInputSources.map((item) => ({
            type: String(item.type || ""),
            value: String(item.value || ""),
        }));
    }

    function renderFileList(files, options = {}) {
        if (!dom.fileList) return;
        dom.fileList.replaceChildren();
        const safeFiles = Array.isArray(files) ? files : [];
        const emptyMessage = String((options && options.emptyMessage) || "").trim();

        const selectAllWrap = document.createElement("div");
        selectAllWrap.className = "sidebar-select-all";
        const chkAll = document.createElement("input");
        chkAll.type = "checkbox";
        chkAll.id = "chk-all";
        chkAll.checked = true;
        const chkAllLabel = document.createElement("strong");
        chkAllLabel.textContent = "Select all";
        selectAllWrap.append(chkAll, " ", chkAllLabel);
        dom.fileList.appendChild(selectAllWrap);

        safeFiles.forEach((file) => {
            const row = document.createElement("div");
            row.className = "file-item";
            row.style.cursor = "pointer";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = true;
            cb.setAttribute("data-file", file.name);
            cb.addEventListener("click", (event) => event.stopPropagation());
            const label = document.createElement("span");
            label.className = "file-item-label";
            label.textContent = file.name;
            row.append(cb, label);
            row.addEventListener("click", () => {
                void helpers.loadCodeViewer(file.name).catch(() => {});
            });
            dom.fileList.appendChild(row);
        });

        if (!safeFiles.length) {
            const empty = document.createElement("div");
            empty.className = "file-item file-item-empty";
            empty.textContent = emptyMessage || "No selectable files available.";
            dom.fileList.appendChild(empty);
        }

        chkAll.addEventListener("change", () => {
            const checked = chkAll.checked;
            dom.fileList.querySelectorAll("input[type='checkbox'][data-file]").forEach((cb) => {
                cb.checked = checked;
            });
        });

        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                file_list_status: safeFiles.length ? "ready" : "empty",
                file_list_dom_count: safeFiles.length,
                file_list_empty_message: emptyMessage,
            });
        }
    }

    async function loadFiles() {
        const response = await fetch("/api/files");
        if (!response.ok) {
            renderFileList([], { emptyMessage: `File list load failed (${response.status})` });
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    file_list_status: "http_error",
                    file_list_http_status: response.status,
                });
            }
            throw new Error(`Failed to load the file list. (${response.status})`);
        }
        const payload = await response.json();
        if (!payload || !Array.isArray(payload.files)) {
            renderFileList([], { emptyMessage: "File list response shape is invalid." });
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

    return {
        applyRecommendationWorkspaceFilter,
        attachResultTableVirtualScrollHandler,
        buildRecommendationWorkspaceFilterText,
        buildWorkspaceRowIndex,
        clearRecommendationWorkspaceFilter,
        createResultRow,
        findRecommendationInsightForViolation,
        flashWorkspaceRow,
        focusWorkspaceRow,
        getFilterState,
        getSelectedFiles,
        getSelectedInputSources,
        initFilterControls,
        loadFiles,
        markWorkspaceRowActive,
        queueResultTableWindowRender,
        renderAnalysisInsights,
        renderFileList,
        renderWorkspace,
        renderWorkspaceFilterSummary,
        renderWorkspaceQuickFilter,
        renderWorkspaceWindow,
        rowMatchesRecommendationFilter,
        runWorkspaceSelection,
        syncWorkspaceRowHighlight,
    };
}
