import {
    basenamePath,
    escapeHtml,
    fileIdentityKey,
    inferRuleIdFromReviewedBlock,
    normalizeInsightToken,
    normalizeP1RuleId,
    normalizeReviewedMessageKey,
    p1RulePrefixGroup,
    positiveLineOrZero,
    scoreSeverityWeight,
    scoreSourceWeight,
    truncateUiText,
    violationDisplayFile,
    violationResolvedFile,
} from "./utils.js";

export function createWorkspaceController({ dom, state, caches, virtualState, helpers }) {
    function buildRecommendationReason(item) {
        const reasons = [];
        const duplicateCount = Math.max(0, Number.parseInt(item && item.duplicateCount, 10) || 0);
        const hotspotIssueCount = Math.max(0, Number.parseInt(item && item.hotspotIssueCount, 10) || 0);
        const ruleBreadth = Math.max(0, Number.parseInt(item && item.ruleBreadth, 10) || 0);
        const dominantRuleCount = Math.max(0, Number.parseInt(item && item.dominantRuleCount, 10) || 0);
        const severityKey = helpers.severityFilterKey(item && item.severity);
        const sourceKey = helpers.sourceFilterKey(item && item.source);
        if (severityKey === "critical") reasons.push("치명도 기준 최우선");
        else if (severityKey === "warning") reasons.push("경고급 이슈 밀집");
        if (duplicateCount >= 4) reasons.push(`중복 영향 ${duplicateCount}건`);
        if (hotspotIssueCount >= 3) reasons.push(`${String(item && item.hotspotObject || item && item.target || "대상")} 집중 ${hotspotIssueCount}건`);
        if (dominantRuleCount >= 2) reasons.push(`${String(item && item.dominantRuleFamily || "RULE")} 계열 반복 ${dominantRuleCount}건`);
        if (ruleBreadth >= 3) reasons.push(`다중 규칙 ${ruleBreadth}종 연관`);
        if (sourceKey === "p1") reasons.push("정적 규칙 기준 우선 검토");
        else if (sourceKey === "p2") reasons.push("Ctrlpp 정적 분석 우선 검토");
        else if (sourceKey === "p3") reasons.push("AI 리뷰 후속 확인 권장");
        return reasons.slice(0, 3).join(" · ") || "심각도와 집중도를 기준으로 우선 추천";
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
        return `${mode === "rule_family" ? "현재 추천 rule 필터" : "현재 추천 hotspot 필터"}: ${label}${source ? ` · ${source.toUpperCase()}` : ""}`;
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
            banner: `전체 대비 행 ${currentRows}/${overallRows} · 이슈 ${currentIssues}/${overallIssues} · ${rowDelta}행/${issueDelta}건 제외`,
            detail: `전체 결과 ${overallRows}행 ${overallIssues}건 중 현재 ${currentRows}행 ${currentIssues}건만 표시합니다. ${rowDelta}행/${issueDelta}건이 필터로 제외되었습니다.`,
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
        dom.workspaceQuickFilter.classList.remove("hidden");
        dom.workspaceQuickFilterText.textContent = `${mode === "rule_family" ? "추천 rule 보기" : "추천 hotspot 보기"}: ${label}${source ? ` · ${source.toUpperCase()}` : ""} · 행 ${dedupe.displayedRowCount || 0}개 · 이슈 ${dedupe.rawIssueCount || 0}개${topRecommendation ? ` · Top ${String(topRecommendation.dominantRuleFamily || "UNKNOWN")}` : ""}${comparison.banner ? ` · ${comparison.banner}` : ""}`;
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
                dom.dedupeSummary.textContent = "분석 후 중복 정리 결과가 표시됩니다.";
            } else {
                dom.dedupeSummary.className = "";
                dom.dedupeSummary.innerHTML = `<div class="review-insight-stats"><div class="review-insight-stat"><div class="review-insight-stat-label">원시 이슈 수</div><div class="review-insight-stat-value">${escapeHtml(dedupe.rawIssueCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">표시 행 수</div><div class="review-insight-stat-value">${escapeHtml(dedupe.displayedRowCount)}</div></div><div class="review-insight-stat"><div class="review-insight-stat-label">접힌 중복 수</div><div class="review-insight-stat-value">${escapeHtml(dedupe.collapsedDuplicateCount)}</div></div></div>`;
            }
        }
        if (!dom.priorityRecommendations) return;
        const recommendations = (state.analysisInsights && state.analysisInsights.recommendations) || [];
        state.recommendationInsightByRowId = buildRecommendationInsightIndex(state.analysisInsights);
        if (!recommendations.length) {
            dom.priorityRecommendations.className = "review-insight-empty";
            dom.priorityRecommendations.textContent = "분석 후 우선 수정 추천이 표시됩니다.";
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
            card.setAttribute("aria-label", `${idx + 1}. ${String(item.target || "")} 우선 수정 추천 열기`);
            if (item && item.representativeRow && item.representativeRow.rowId) {
                card.setAttribute("data-row-id", String(item.representativeRow.rowId));
            }
            card.innerHTML = `<div class="priority-item-header"><div class="priority-item-target">${idx + 1}. ${escapeHtml(item.target)}</div><div class="priority-item-score">점수 ${escapeHtml(item.score)}</div></div><div class="priority-item-meta">${escapeHtml(String(item.source).toUpperCase())} · ${escapeHtml(String(item.severity || "Info"))} · 행 ${escapeHtml(item.rowCount)}개 · 이슈 ${escapeHtml(item.duplicateCount)}개</div><div class="priority-item-meta">hotspot ${escapeHtml(item.hotspotObject || item.target)} ${escapeHtml(item.hotspotIssueCount || 0)}건 · rule ${escapeHtml(item.dominantRuleFamily || "UNKNOWN")} ${escapeHtml(item.dominantRuleCount || 0)}건 · 규칙 ${escapeHtml(item.ruleBreadth || 0)}종</div><div class="priority-item-reason">${escapeHtml(item.reason || "심각도와 집중도를 기준으로 우선 추천")}</div><div class="priority-item-actions"><button type="button" class="priority-chip priority-chip-hotspot">같은 hotspot 보기</button><button type="button" class="priority-chip priority-chip-rule">같은 rule 보기</button></div><div class="priority-item-message">${escapeHtml(truncateUiText(item.leadMessage || "대표 이슈 메시지 없음"))}</div>`;
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
        const comparison = buildWorkspaceFilterComparisonSummary();
        const parts = [`소스 ${sourceLabels.length ? sourceLabels.join(", ") : "없음"}`, `심각도 ${severityLabels.length ? severityLabels.join(", ") : "없음"}`, recommendationText || "추천 필터 없음"];
        if (comparison.banner && recommendationText) parts.push(comparison.banner);
        return parts.join(" · ");
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
        objectMeta.textContent = objectMetaParts.join(" · ");
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
        if (Number.parseInt(rowData && rowData.duplicateCount, 10) > 1) metaParts.push(`중복 ${Number.parseInt(rowData.duplicateCount, 10)}건`);
        messageMeta.textContent = metaParts.join(" · ");
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
            emptyCell.textContent = "현재 필터 기준으로 표시할 결과가 없습니다. 왼쪽 필터를 풀거나 다른 추천 quick filter를 선택해 보세요.";
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
        const p1Groups = state.analysisData.violations.P1 || [];
        const p2List = state.analysisData.violations.P2 || [];
        const flattenedP1 = [];
        p1Groups.forEach((group) => {
            (group.violations || []).forEach((v, index) => {
                const violation = { ...v, object: group.object };
                violation.file = violation.file || group.object;
                violation.file_path = violation.file_path || violation.file || group.object;
                violation.priority_origin = violation.priority_origin || "P1";
                const flatKey = String(violation.issue_id || `${violationDisplayFile(violation, group.object)}:${positiveLineOrZero(violation.line)}:${String(violation.rule_id || "")}:${index}`);
                flattenedP1.push({
                    flatKey,
                    violation,
                    eventName: String(group.event || "Global"),
                    rowObject: group.object,
                    fileKey: violationResolvedFile(violation, group.object),
                });
            });
        });

        const ruleSeverityById = new Map();
        flattenedP1.forEach((item) => {
            const ruleId = normalizeP1RuleId(item && item.violation && item.violation.rule_id);
            if (!ruleId || ruleId === "UNKNOWN") return;
            const current = String(item && item.violation && item.violation.severity || "").trim();
            if (!current) return;
            const previous = String(ruleSeverityById.get(ruleId) || "").trim();
            ruleSeverityById.set(ruleId, previous ? helpers.pickHigherSeverity(previous, current) : current);
        });

        const resolveReviewedSeverity = (blockSeverity, effectiveRuleId) => {
            const byRule = String(ruleSeverityById.get(normalizeP1RuleId(effectiveRuleId)) || "").trim();
            if (byRule) return byRule;
            const byBlock = String(blockSeverity || "").trim();
            return byBlock || "Info";
        };

        const mappingDiagnostics = {
            violation_total: flattenedP1.length,
            violation_unknown_rule_count: 0,
            violation_cfg_rule_count: 0,
            violation_cfg_alias_mapped_count: 0,
            violation_cfg_alias_unmapped_ids: new Set(),
            reviewed_block_total: 0,
            reviewed_unknown_rule_count: 0,
            reviewed_unknown_with_no_line_count: 0,
            reviewed_inferred_rule_count: 0,
            reviewed_inferred_match_success_count: 0,
            reviewed_inferred_match_ambiguous_count: 0,
            reviewed_unknown_after_infer_count: 0,
            review_only_grouped_row_count: 0,
            review_only_grouped_collapsed_count: 0,
            synced_message_mismatch_count: 0,
            synced_rule_message_conflict_samples: [],
        };

        flattenedP1.forEach((item) => {
            const rawRuleId = String(item && item.violation && item.violation.rule_id || "").trim();
            const normalizedRuleId = normalizeP1RuleId(rawRuleId);
            if (!rawRuleId || normalizedRuleId === "UNKNOWN") mappingDiagnostics.violation_unknown_rule_count += 1;
            if (/^cfg-/i.test(rawRuleId)) {
                mappingDiagnostics.violation_cfg_rule_count += 1;
                if (normalizedRuleId !== rawRuleId.toUpperCase()) mappingDiagnostics.violation_cfg_alias_mapped_count += 1;
                else mappingDiagnostics.violation_cfg_alias_unmapped_ids.add(rawRuleId);
            }
        });

        const byIssueId = new Map();
        const bySecondary = new Map();
        flattenedP1.forEach((item) => {
            const issueId = String(item.violation.issue_id || "").trim();
            if (issueId) {
                if (!byIssueId.has(issueId)) byIssueId.set(issueId, []);
                byIssueId.get(issueId).push(item);
            }
            const secKey = [
                fileIdentityKey(item.fileKey),
                positiveLineOrZero(item.violation.line),
                normalizeP1RuleId(item.violation.rule_id),
                String(item.violation.message || "").trim(),
            ].join("||");
            if (!bySecondary.has(secKey)) bySecondary.set(secKey, []);
            bySecondary.get(secKey).push(item);
        });

        const usedFlatKeys = new Set();
        const p1Rows = [];
        let syncedCount = 0;
        let reviewOnlyCount = 0;
        let violationOnlyCount = 0;
        const reviewOnlyGrouped = new Map();

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

        caches.reviewedTodoCacheByFile.forEach((blocks, reviewedFile) => {
            const fileBlocks = Array.isArray(blocks) ? blocks : [];
            mappingDiagnostics.reviewed_block_total += fileBlocks.length;
            fileBlocks.forEach((block, idx) => {
                const meta = (block && block.meta && typeof block.meta === "object") ? block.meta : {};
                const issueId = String(meta.issue_id || "").trim();
                const ruleId = String(meta.rule_id || "").trim();
                const lineNo = positiveLineOrZero(meta.line || 0);
                const normalizedRuleId = normalizeP1RuleId(ruleId);
                const inferred = inferRuleIdFromReviewedBlock(block);
                const inferredRuleId = normalizeP1RuleId(inferred.inferredRuleId);
                if (inferredRuleId !== "UNKNOWN" && inferred.source !== "meta") mappingDiagnostics.reviewed_inferred_rule_count += 1;
                if (!ruleId || normalizedRuleId === "UNKNOWN") {
                    mappingDiagnostics.reviewed_unknown_rule_count += 1;
                    if (lineNo <= 0) mappingDiagnostics.reviewed_unknown_with_no_line_count += 1;
                }
                const effectiveRuleId = normalizedRuleId !== "UNKNOWN" ? normalizedRuleId : inferredRuleId;
                const blockMessage = String(block.message || "").trim();
                const secondaryKey = [fileIdentityKey(meta.file || reviewedFile), lineNo, effectiveRuleId, blockMessage].join("||");

                let matched = [];
                let matchedReason = "";
                if (issueId && byIssueId.has(issueId)) {
                    matched = (byIssueId.get(issueId) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                    if (matched.length) matchedReason = "meta_exact";
                }
                if (!matched.length && (lineNo > 0 || ruleId || blockMessage) && bySecondary.has(secondaryKey)) {
                    matched = (bySecondary.get(secondaryKey) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                    if (matched.length) matchedReason = "secondary_exact";
                }
                if (!matched.length && effectiveRuleId !== "UNKNOWN") {
                    const targetFile = fileIdentityKey(meta.file || reviewedFile);
                    const targetLine = lineNo > 0 ? lineNo : positiveLineOrZero(block.todo_line);
                const inferredPrefix = p1RulePrefixGroup(effectiveRuleId);
                    const proximityCandidates = flattenedP1.filter((item) => {
                        if (usedFlatKeys.has(item.flatKey)) return false;
                        if (fileIdentityKey(item.fileKey) !== targetFile) return false;
                        const itemRule = normalizeP1RuleId(item.violation.rule_id);
                        if (itemRule === "UNKNOWN") return false;
                        const isDpGetVsGetMultiConflict = (
                            (effectiveRuleId === "PERF-DPGET-BATCH-01" && itemRule === "PERF-GETMULTIVALUE-ADOPT-01")
                            || (effectiveRuleId === "PERF-GETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPGET-BATCH-01")
                        );
                        const isDpSetVsSetMultiConflict = (
                            (effectiveRuleId === "PERF-DPSET-BATCH-01" && itemRule === "PERF-SETMULTIVALUE-ADOPT-01")
                            || (effectiveRuleId === "PERF-SETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPSET-BATCH-01")
                        );
                        if (isDpGetVsGetMultiConflict || isDpSetVsSetMultiConflict) return false;
                    const itemPrefix = p1RulePrefixGroup(itemRule);
                        if (!(itemRule === effectiveRuleId || itemPrefix === inferredPrefix)) return false;
                        const itemLine = positiveLineOrZero(item.violation.line);
                        if (targetLine <= 0 || itemLine <= 0) return false;
                        return Math.abs(itemLine - targetLine) <= 25;
                    });
                    if (proximityCandidates.length === 1) {
                        matched = proximityCandidates;
                        matchedReason = "inferred_proximity";
                        mappingDiagnostics.reviewed_inferred_match_success_count += 1;
                    } else if (proximityCandidates.length > 1) {
                        mappingDiagnostics.reviewed_inferred_match_ambiguous_count += 1;
                    }
                }

                if (matched.length) {
                    matched.forEach((item) => usedFlatKeys.add(item.flatKey));
                    const top = matched[0];
                    const representative = {
                        ...top.violation,
                        file: top.violation.file || reviewedFile,
                        file_path: top.violation.file_path || top.violation.file || reviewedFile,
                        object: top.violation.object || top.rowObject || reviewedFile,
                        message: top.violation.message || blockMessage,
                        line: positiveLineOrZero(top.violation.line) || lineNo || positiveLineOrZero(block.todo_line),
                        rule_id: top.violation.rule_id || effectiveRuleId || ruleId,
                        issue_id: top.violation.issue_id || issueId,
                        severity: top.violation.severity || block.severity || "Info",
                        _reviewed_todo_line: positiveLineOrZero(block.todo_line),
                        _reviewed_block_indexes: [idx + 1],
                        _reviewed_original_message: blockMessage || "",
                    };
                    if (normalizeReviewedMessageKey(blockMessage) && normalizeReviewedMessageKey(top.violation.message || "") && normalizeReviewedMessageKey(blockMessage) !== normalizeReviewedMessageKey(top.violation.message || "")) {
                        mappingDiagnostics.synced_message_mismatch_count += 1;
                        if (mappingDiagnostics.synced_rule_message_conflict_samples.length < 10) {
                            mappingDiagnostics.synced_rule_message_conflict_samples.push({
                                file: basenamePath(top.violation.file || reviewedFile),
                                line: positiveLineOrZero(top.violation.line),
                                rule_id: normalizeP1RuleId(top.violation.rule_id),
                                violation_message: String(top.violation.message || ""),
                                reviewed_message: String(blockMessage || ""),
                            });
                        }
                    }
                    pushP1Row(representative, top.eventName || "Global", "synced", "mixed", matched, "", matchedReason);
                    syncedCount += 1;
                } else {
                    const localState = issueId ? "review-only" : "partial";
                    const displayMessage = blockMessage || "REVIEWED TODO 항목";
                    const reviewFile = basenamePath(meta.file || reviewedFile);
                    const reviewKey = [fileIdentityKey(reviewFile), normalizeReviewedMessageKey(displayMessage)].join("||");
                    if (!reviewOnlyGrouped.has(reviewKey)) {
                        reviewOnlyGrouped.set(reviewKey, {
                            file: reviewFile,
                            message: displayMessage,
                            severity: resolveReviewedSeverity(block.severity, effectiveRuleId),
                            lines: [],
                            todoLines: [],
                            issueIds: [],
                            ruleIds: [],
                            states: new Set(),
                            blockIndexes: [],
                        });
                    }
                    const grouped = reviewOnlyGrouped.get(reviewKey);
                    grouped.severity = helpers.pickHigherSeverity(grouped.severity || "Info", resolveReviewedSeverity(block.severity, effectiveRuleId));
                    if (lineNo > 0) grouped.lines.push(lineNo);
                    if (positiveLineOrZero(block.todo_line) > 0) grouped.todoLines.push(positiveLineOrZero(block.todo_line));
                    grouped.issueIds.push(issueId || `REVIEW-ONLY-${reviewedFile}-${idx + 1}`);
                    grouped.ruleIds.push(effectiveRuleId || "UNKNOWN");
                    grouped.states.add(localState);
                    grouped.blockIndexes.push(idx + 1);
                    reviewOnlyCount += 1;
                    if ((effectiveRuleId || "UNKNOWN") === "UNKNOWN") mappingDiagnostics.reviewed_unknown_after_infer_count += 1;
                }
            });
        });

        reviewOnlyGrouped.forEach((grouped) => {
            const uniqueLines = Array.from(new Set((grouped.lines || []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
            const uniqueTodoLines = Array.from(new Set((grouped.todoLines || []).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
            const uniqueIssues = Array.from(new Set((grouped.issueIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
            const uniqueRules = Array.from(new Set((grouped.ruleIds || []).map((id) => String(id || "").trim()).filter(Boolean)));
            const uniqueBlocks = Array.from(new Set((grouped.blockIndexes || []).map((n) => Number.parseInt(n, 10)).filter((n) => Number.isFinite(n) && n > 0))).sort((a, b) => a - b);
            mappingDiagnostics.review_only_grouped_row_count += 1;
            mappingDiagnostics.review_only_grouped_collapsed_count += Math.max(0, uniqueIssues.length - 1);
            const synthetic = {
                priority_origin: "P1",
                issue_id: uniqueIssues[0] || `REVIEW-ONLY-${grouped.file || "UNKNOWN"}-1`,
                rule_id: uniqueRules[0] || "UNKNOWN",
                severity: grouped.severity || "Info",
                message: grouped.message || "REVIEWED TODO 항목",
                file: grouped.file || "",
                object: grouped.file || "Global",
                line: uniqueLines[0] || 0,
                _grouping_mode: "review_only_message",
                _group_rule_ids: uniqueRules,
                _group_messages: [grouped.message || "REVIEWED TODO 항목"],
                _group_issue_ids: uniqueIssues,
                _duplicate_count: Math.max(1, uniqueIssues.length),
                _duplicate_lines: uniqueLines,
                _primary_line: uniqueLines[0] || 0,
                _reviewed_todo_line: uniqueTodoLines[0] || 0,
                _reviewed_todo_lines: uniqueTodoLines,
                _reviewed_original_message: grouped.message || "REVIEWED TODO 항목",
                _reviewed_block_indexes: uniqueBlocks,
            };
            const localState = grouped.states.has("partial") ? "partial" : "review-only";
            pushP1Row(synthetic, "Global", localState, "reviewed", [], grouped.message || "REVIEWED TODO 항목", "review_only");
        });

        const leftovers = flattenedP1.filter((item) => !usedFlatKeys.has(item.flatKey));
        violationOnlyCount = leftovers.length;
        if (p1Rows.length > 0) {
            console.debug("[P1 sync]", {
                synced_count: syncedCount,
                review_only_count: reviewOnlyCount,
                violation_only_count: violationOnlyCount,
                rows: p1Rows.length,
            });
            console.debug("[P1 mapping diagnostics]", {
                ...mappingDiagnostics,
                violation_cfg_alias_unmapped_ids: Array.from(mappingDiagnostics.violation_cfg_alias_unmapped_ids).sort(),
            });
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
        chkAllLabel.textContent = "전체 선택";
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
            throw new Error(`파일 목록 로드 실패 (${response.status})`);
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
