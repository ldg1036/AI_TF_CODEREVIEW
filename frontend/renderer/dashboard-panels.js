import {
    buildAnalysisDiffModel,
    buildDashboardSummaryState,
    buildDashboardSystemSummaryModel,
    buildOperationsCompareModel,
    deriveRulesHealthState,
    deriveVerificationBadgeState,
    deriveVerificationProfileState,
} from "./dashboard-state-helpers.js";

export function createDashboardPanelsController({ dom, state, helpers }) {
    let latestVerificationPayload = null;
    let latestVerificationError = "";
    let latestOperationsPayload = null;
    let latestOperationsError = "";

    function updateVerificationBadge() {
        if (!dom.verificationBadge) return;
        const badgeState = deriveVerificationBadgeState(state.analysisData);
        dom.verificationBadge.classList.remove(
            "verification-badge--core-only",
            "verification-badge--core-report",
            "verification-badge--full",
            "verification-badge--unknown",
        );
        dom.verificationBadge.textContent = badgeState.text;
        dom.verificationBadge.classList.add(badgeState.className);
        dom.verificationBadge.title = badgeState.title;
    }

    function updateVerificationProfileCard(payload = null, errorMessage = "") {
        if (!dom.verificationProfileCard) return;
        const profileState = deriveVerificationProfileState(payload, errorMessage);
        dom.verificationProfileCard.classList.remove(
            "verification-profile-card--ok",
            "verification-profile-card--degraded",
            "verification-profile-card--failed",
            "verification-profile-card--unknown",
        );
        dom.verificationProfileCard.classList.add(profileState.className);
        dom.verificationProfileCard.textContent = profileState.text;
        dom.verificationProfileCard.title = profileState.title;
    }

    function renderDashboardSystemSummary() {
        if (!dom.dashboardSystemSummary) return;
        dom.dashboardSystemSummary.replaceChildren();
        dom.dashboardSystemSummary.className = "dashboard-system-summary";

        const model = buildDashboardSystemSummaryModel({
            analysisData: state.analysisData,
            verificationPayload: latestVerificationPayload,
            verificationErrorMessage: latestVerificationError,
            operationsPayload: latestOperationsPayload,
            operationsErrorMessage: latestOperationsError,
            rulesHealthPayload: state.latestRulesHealthPayload,
        });

        const topRow = document.createElement("div");
        topRow.className = "dashboard-system-summary-top";

        const badge = document.createElement("span");
        badge.className = `verification-badge ${model.verificationBadgeState.className}`;
        badge.textContent = model.verificationBadgeState.text;
        badge.title = model.verificationBadgeState.title;

        const profile = document.createElement("span");
        profile.className = `verification-profile-card ${model.verificationProfileState.className}`;
        profile.textContent = model.verificationProfileState.text;
        profile.title = model.verificationProfileState.title;

        topRow.append(badge, profile);
        dom.dashboardSystemSummary.appendChild(topRow);

        if (model.dependencyBadges.length) {
            const depWrap = document.createElement("div");
            depWrap.className = "dashboard-system-summary-badges";
            model.dependencyBadges.forEach(({ label, available }) => {
                depWrap.appendChild(createRulesHealthBadge(label, available));
            });
            dom.dashboardSystemSummary.appendChild(depWrap);
        }

        const opList = document.createElement("div");
        opList.className = "dashboard-system-summary-lines";
        model.operationLines.forEach((line) => {
            const item = document.createElement("div");
            item.className = "dashboard-system-summary-line";
            item.textContent = line;
            opList.appendChild(item);
        });
        dom.dashboardSystemSummary.appendChild(opList);

        if (model.dependencyFootnote) {
            const footnote = document.createElement("div");
            footnote.className = "dashboard-system-summary-footnote";
            footnote.textContent = model.dependencyFootnote;
            dom.dashboardSystemSummary.appendChild(footnote);
        }
    }

    async function loadLatestVerificationProfile() {
        try {
            const response = await fetch("/api/verification/latest");
            const payload = await response.json();
            if (!response.ok) {
                if (response.status === 404) {
                    latestVerificationPayload = null;
                    latestVerificationError = "검증 산출물이 아직 없습니다.";
                    updateVerificationProfileCard(null, "검증 산출물이 아직 없습니다.");
                    renderDashboardSystemSummary();
                    return;
                }
                latestVerificationPayload = null;
                latestVerificationError = payload.error || `검증 프로파일 조회 실패 (${response.status})`;
                updateVerificationProfileCard(null, latestVerificationError);
                renderDashboardSystemSummary();
                return;
            }
            if (payload && payload.available === false) {
                latestVerificationPayload = null;
                latestVerificationError = payload.message || "검증 산출물이 아직 없습니다.";
                updateVerificationProfileCard(null, latestVerificationError);
                renderDashboardSystemSummary();
                return;
            }
            latestVerificationPayload = payload;
            latestVerificationError = "";
            updateVerificationProfileCard(payload, "");
            renderDashboardSystemSummary();
        } catch (err) {
            latestVerificationPayload = null;
            latestVerificationError = (err && err.message) || String(err);
            updateVerificationProfileCard(null, latestVerificationError);
            renderDashboardSystemSummary();
        }
    }

    function createOperationMetric(label, valueText) {
        const metric = document.createElement("div");
        metric.className = "operations-compare-metric";
        const strong = document.createElement("strong");
        strong.textContent = valueText;
        metric.append(strong, document.createTextNode(label));
        return metric;
    }

    function renderOperationsCompare(payload = null, errorMessage = "") {
        if (!dom.operationsCompare) return;
        dom.operationsCompare.replaceChildren();
        const model = buildOperationsCompareModel(payload, errorMessage);
        dom.operationsCompare.className = model.className;
        if (model.emptyMessage) {
            dom.operationsCompare.textContent = model.emptyMessage;
            return;
        }

        model.items.forEach((item) => {
            const block = document.createElement("div");
            block.className = "operations-compare-item";

            const header = document.createElement("div");
            header.className = "operations-compare-header";
            const title = document.createElement("div");
            title.className = "operations-compare-title";
            title.textContent = item.label;
            const badge = document.createElement("span");
            badge.className = `operations-compare-badge operations-compare-badge--${item.badgeClass}`;
            badge.textContent = item.badgeText;
            header.append(title, badge);
            block.appendChild(header);

            if (item.emptyMessage) {
                const empty = document.createElement("div");
                empty.className = "operations-compare-footnote";
                empty.textContent = item.emptyMessage;
                block.appendChild(empty);
                dom.operationsCompare.appendChild(block);
                return;
            }

            const metrics = document.createElement("div");
            metrics.className = "operations-compare-meta";
            item.metrics.forEach((metric) => {
                metrics.appendChild(createOperationMetric(metric.label, metric.valueText));
            });
            block.appendChild(metrics);

            const footnote = document.createElement("div");
            footnote.className = "operations-compare-footnote";
            footnote.textContent = item.footnote;
            block.appendChild(footnote);
            dom.operationsCompare.appendChild(block);
        });
    }

    async function loadLatestOperationalResults() {
        try {
            const response = await fetch("/api/operations/latest");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                latestOperationsPayload = null;
                latestOperationsError = payload.error || `운영 검증 비교 조회 실패 (${response.status})`;
                renderOperationsCompare(null, latestOperationsError);
                renderDashboardSystemSummary();
                return;
            }
            latestOperationsPayload = payload;
            latestOperationsError = "";
            renderOperationsCompare(payload, "");
            renderDashboardSystemSummary();
        } catch (err) {
            latestOperationsPayload = null;
            latestOperationsError = (err && err.message) || String(err);
            renderOperationsCompare(null, latestOperationsError);
            renderDashboardSystemSummary();
        }
    }

    function createRulesHealthBadge(label, available) {
        const badge = document.createElement("span");
        badge.className = `operations-compare-badge operations-compare-badge--${available ? "passed" : "unknown"}`;
        badge.textContent = `${label} ${available ? "ready" : "missing"}`;
        return badge;
    }

    function renderRulesHealth(payload = null, errorMessage = "") {
        if (!dom.rulesHealthCompare) return;
        dom.rulesHealthCompare.replaceChildren();
        state.latestRulesHealthPayload = payload && typeof payload === "object" ? payload : null;
        const healthState = deriveRulesHealthState({
            payload,
            errorMessage,
            rulesManageOpen: state.rulesManageOpen,
        });
        dom.rulesHealthCompare.className = healthState.className;
        if (healthState.emptyMessage) {
            dom.rulesHealthCompare.textContent = healthState.emptyMessage;
            return;
        }
        const summary = document.createElement("div");
        summary.className = "rules-health-summary";
        healthState.summaryItems.forEach(({ label, value }) => {
            const item = document.createElement("div");
            item.className = "analysis-diff-summary-item";
            const strong = document.createElement("strong");
            strong.textContent = String(value);
            item.append(strong, document.createTextNode(label));
            summary.appendChild(item);
        });
        dom.rulesHealthCompare.appendChild(summary);

        const depWrap = document.createElement("div");
        depWrap.className = "rules-health-badges";
        healthState.dependencyBadges.forEach(({ label, available }) => {
            depWrap.appendChild(createRulesHealthBadge(label, available));
        });
        dom.rulesHealthCompare.appendChild(depWrap);

        const footnote = document.createElement("div");
        footnote.className = "operations-compare-footnote";
        footnote.textContent = healthState.footnoteText;
        dom.rulesHealthCompare.appendChild(footnote);

        const actionRow = document.createElement("div");
        actionRow.className = "rules-manage-actions";
        const manageButton = document.createElement("button");
        manageButton.type = "button";
        manageButton.className = "rules-manage-button";
        manageButton.textContent = healthState.manageButtonText;
        manageButton.disabled = state.rulesManageSaving;
        manageButton.addEventListener("click", () => {
            state.rulesManageOpen = !state.rulesManageOpen;
            if (state.rulesManageOpen && !state.rulesManageRows.length && !state.rulesManageLoading && helpers.loadRulesList) {
                void helpers.loadRulesList(false);
            }
            renderRulesHealth(state.latestRulesHealthPayload, "");
        });
        actionRow.appendChild(manageButton);
        dom.rulesHealthCompare.appendChild(actionRow);

        if (state.rulesManageOpen && helpers.renderRulesManagePanel) {
            helpers.renderRulesManagePanel(dom.rulesHealthCompare);
        }
    }

    async function loadRulesHealth() {
        try {
            const response = await fetch("/api/rules/health");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                renderRulesHealth(null, payload.error || `규칙 상태 조회 실패 (${response.status})`);
                renderDashboardSystemSummary();
                return;
            }
            renderRulesHealth(payload, "");
            renderDashboardSystemSummary();
        } catch (err) {
            renderRulesHealth(null, (err && err.message) || String(err));
            renderDashboardSystemSummary();
        }
    }

    function renderAnalysisDiffCompare(payload = null, errorMessage = "") {
        if (!dom.analysisDiffCompare) return;
        dom.analysisDiffCompare.replaceChildren();
        const hasRunOptions = Array.isArray(state.analysisDiffRunOptions) && state.analysisDiffRunOptions.length >= 2;
        const model = buildAnalysisDiffModel(payload, errorMessage, { hasRunOptions });
        dom.analysisDiffCompare.className = model.className;
        if (model.latestTimestamp) {
            state.selectedAnalysisDiffLatest = model.latestTimestamp;
        }
        if (model.previousTimestamp) {
            state.selectedAnalysisDiffPrevious = model.previousTimestamp;
        }
        if (model.hasRunOptions) {
            dom.analysisDiffCompare.appendChild(createAnalysisDiffControls());
        }
        if (model.emptyMessage) {
            if (model.hasRunOptions) {
                const empty = document.createElement("div");
                empty.className = "review-insight-empty";
                empty.textContent = model.emptyMessage;
                dom.analysisDiffCompare.appendChild(empty);
                return;
            }
            dom.analysisDiffCompare.textContent = model.emptyMessage;
            return;
        }

        const header = document.createElement("div");
        header.className = "analysis-diff-header";
        header.textContent = model.headerText;
        dom.analysisDiffCompare.appendChild(header);

        if (model.warningText) {
            const warning = document.createElement("div");
            warning.className = "analysis-diff-header";
            warning.textContent = model.warningText;
            dom.analysisDiffCompare.appendChild(warning);
        }

        const summaryWrap = document.createElement("div");
        summaryWrap.className = "analysis-diff-summary";
        model.summaryItems.forEach(({ label, valueText }) => {
            const item = document.createElement("div");
            item.className = "analysis-diff-summary-item";
            const strong = document.createElement("strong");
            strong.textContent = valueText;
            item.append(strong, document.createTextNode(label));
            summaryWrap.appendChild(item);
        });
        dom.analysisDiffCompare.appendChild(summaryWrap);

        if (!model.changedFiles.length) {
            const empty = document.createElement("div");
            empty.className = "analysis-diff-header";
            empty.textContent = model.noChangedFilesMessage;
            dom.analysisDiffCompare.appendChild(empty);
            return;
        }

        const fileList = document.createElement("div");
        fileList.className = "analysis-diff-file-list";
        model.changedFiles.forEach((item) => {
            const fileItem = document.createElement("div");
            fileItem.className = "analysis-diff-file-item";

            const title = document.createElement("div");
            title.className = "analysis-diff-file-title";
            const name = document.createElement("span");
            name.textContent = String(item.file || "(unknown)");
            const status = document.createElement("span");
            status.className = "analysis-diff-file-status";
            status.textContent = String(item.status || "");
            title.append(name, status);

            const meta = document.createElement("div");
            meta.className = "analysis-diff-file-meta";
            meta.textContent = item.metaText;

            fileItem.append(title, meta);
            fileList.appendChild(fileItem);
        });
        dom.analysisDiffCompare.appendChild(fileList);
    }

    function createAnalysisDiffControls() {
        const controls = document.createElement("div");
        controls.className = "analysis-diff-controls";

        const latestSelect = document.createElement("select");
        latestSelect.className = "analysis-diff-select";
        state.analysisDiffRunOptions.forEach((run) => {
            const option = document.createElement("option");
            option.value = String(run.timestamp || "");
            option.textContent = String(run.timestamp || run.output_dir || "-");
            option.selected = option.value === state.selectedAnalysisDiffLatest;
            latestSelect.appendChild(option);
        });
        latestSelect.addEventListener("change", () => {
            state.selectedAnalysisDiffLatest = latestSelect.value;
        });

        const previousSelect = document.createElement("select");
        previousSelect.className = "analysis-diff-select";
        state.analysisDiffRunOptions.forEach((run) => {
            const option = document.createElement("option");
            option.value = String(run.timestamp || "");
            option.textContent = String(run.timestamp || run.output_dir || "-");
            option.selected = option.value === state.selectedAnalysisDiffPrevious;
            previousSelect.appendChild(option);
        });
        previousSelect.addEventListener("change", () => {
            state.selectedAnalysisDiffPrevious = previousSelect.value;
        });

        const button = document.createElement("button");
        button.type = "button";
        button.className = "rules-manage-button";
        button.textContent = "Compare selected";
        button.disabled = !state.selectedAnalysisDiffLatest || !state.selectedAnalysisDiffPrevious;
        button.addEventListener("click", () => {
            void loadSelectedAnalysisDiff();
        });

        controls.append(latestSelect, previousSelect, button);
        return controls;
    }

    async function loadAnalysisDiffRuns(force = false) {
        if (state.analysisDiffRunOptions.length && !force) {
            return;
        }
        try {
            const response = await fetch("/api/analysis-diff/runs");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                return;
            }
            state.analysisDiffRunOptions = Array.isArray(payload.runs) ? payload.runs : [];
            if (!state.selectedAnalysisDiffLatest && state.analysisDiffRunOptions[0]) {
                state.selectedAnalysisDiffLatest = String(state.analysisDiffRunOptions[0].timestamp || "");
            }
            if (!state.selectedAnalysisDiffPrevious && state.analysisDiffRunOptions[1]) {
                state.selectedAnalysisDiffPrevious = String(state.analysisDiffRunOptions[1].timestamp || "");
            }
        } catch (err) {
            console.error(err);
        }
    }

    async function loadSelectedAnalysisDiff() {
        if (!state.selectedAnalysisDiffLatest || !state.selectedAnalysisDiffPrevious) {
            return;
        }
        try {
            const params = new URLSearchParams({
                latest: state.selectedAnalysisDiffLatest,
                previous: state.selectedAnalysisDiffPrevious,
            });
            const response = await fetch(`/api/analysis-diff/compare?${params.toString()}`);
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                renderAnalysisDiffCompare(null, payload.error || `Analysis diff fetch failed (${response.status})`);
                return;
            }
            renderAnalysisDiffCompare(payload, "");
        } catch (err) {
            renderAnalysisDiffCompare(null, (err && err.message) || String(err));
        }
    }

    async function loadLatestAnalysisDiff() {
        try {
            await loadAnalysisDiffRuns(false);
            const response = await fetch("/api/analysis-diff/latest");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                renderAnalysisDiffCompare(null, payload.error || `Analysis diff fetch failed (${response.status})`);
                return;
            }
            renderAnalysisDiffCompare(payload, "");
        } catch (err) {
            renderAnalysisDiffCompare(null, (err && err.message) || String(err));
        }
    }

    function updateDashboard() {
        const summaryState = buildDashboardSummaryState(
            (state.analysisData && state.analysisData.summary) || {},
            { currentReviewCount: Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows.length : 0 },
        );
        if (dom.totalText) dom.totalText.textContent = summaryState.totalText;
        if (dom.currentReviewText) dom.currentReviewText.textContent = summaryState.currentReviewText;
        if (dom.criticalText) dom.criticalText.textContent = summaryState.criticalText;
        if (dom.warningText) dom.warningText.textContent = summaryState.warningText;
        if (dom.scoreBar) dom.scoreBar.style.width = summaryState.scoreWidth;
        if (dom.scoreText) dom.scoreText.textContent = summaryState.scoreText;
        updateVerificationBadge();
        renderDashboardSystemSummary();
        if (helpers.renderAnalysisInsights) {
            helpers.renderAnalysisInsights();
        }
    }

    return {
        loadAnalysisDiffRuns,
        loadLatestAnalysisDiff,
        loadLatestOperationalResults,
        loadLatestVerificationProfile,
        loadRulesHealth,
        loadSelectedAnalysisDiff,
        renderAnalysisDiffCompare,
        renderDashboardSystemSummary,
        renderOperationsCompare,
        renderRulesHealth,
        updateDashboard,
        updateVerificationBadge,
        updateVerificationProfileCard,
    };
}
