export function createDashboardPanelsController({ dom, state, helpers }) {
    function updateVerificationBadge() {
        if (!dom.verificationBadge) return;
        const summary = (state.analysisData && state.analysisData.summary) || {};
        const metrics = (state.analysisData && state.analysisData.metrics) || {};
        const level = String(summary.verification_level || "").trim().toUpperCase();
        const optionalDeps = metrics.optional_dependencies || {};
        const openpyxlAvailable = !!(optionalDeps.openpyxl && optionalDeps.openpyxl.available);

        dom.verificationBadge.classList.remove(
            "verification-badge--core-only",
            "verification-badge--core-report",
            "verification-badge--full",
            "verification-badge--unknown",
        );

        if (level === "CORE_ONLY") {
            dom.verificationBadge.textContent = "레벨 CORE_ONLY";
            dom.verificationBadge.classList.add("verification-badge--core-only");
        } else if (level === "CORE+REPORT") {
            dom.verificationBadge.textContent = "레벨 CORE+REPORT";
            dom.verificationBadge.classList.add("verification-badge--core-report");
        } else if (level === "FULL_WITH_OPTIONALS") {
            dom.verificationBadge.textContent = "레벨 FULL_WITH_OPTIONALS";
            dom.verificationBadge.classList.add("verification-badge--full");
        } else {
            dom.verificationBadge.textContent = "레벨 UNKNOWN";
            dom.verificationBadge.classList.add("verification-badge--unknown");
        }

        const openpyxlText = openpyxlAvailable ? "available" : "missing";
        dom.verificationBadge.title = `verification_level=${level || "UNKNOWN"}, openpyxl=${openpyxlText}`;
    }

    function updateVerificationProfileCard(payload = null, errorMessage = "") {
        if (!dom.verificationProfileCard) return;
        dom.verificationProfileCard.classList.remove(
            "verification-profile-card--ok",
            "verification-profile-card--degraded",
            "verification-profile-card--failed",
            "verification-profile-card--unknown",
        );

        if (!payload || typeof payload !== "object") {
            dom.verificationProfileCard.classList.add("verification-profile-card--unknown");
            dom.verificationProfileCard.textContent = "프로파일 없음";
            dom.verificationProfileCard.title = errorMessage || "검증 프로파일 결과 파일이 없습니다.";
            return;
        }

        const summary = payload.summary || {};
        const failed = Number(summary.failed || 0);
        const skipped = Number(summary.skipped_optional_missing || 0);
        const passed = Number(summary.passed || 0);
        if (failed > 0) {
            dom.verificationProfileCard.classList.add("verification-profile-card--failed");
            dom.verificationProfileCard.textContent = `프로파일 실패 ${failed}`;
        } else if (skipped > 0) {
            dom.verificationProfileCard.classList.add("verification-profile-card--degraded");
            dom.verificationProfileCard.textContent = `프로파일 통과 ${passed} · 스킵 ${skipped}`;
        } else {
            dom.verificationProfileCard.classList.add("verification-profile-card--ok");
            dom.verificationProfileCard.textContent = `프로파일 통과 ${passed}`;
        }

        const sourceFile = String(payload.source_file || "");
        dom.verificationProfileCard.title = sourceFile ? `latest=${sourceFile}` : "최신 검증 프로파일";
    }

    async function loadLatestVerificationProfile() {
        try {
            const response = await fetch("/api/verification/latest");
            const payload = await response.json();
            if (!response.ok) {
                if (response.status === 404) {
                    updateVerificationProfileCard(null, "검증 산출물이 아직 없습니다.");
                    return;
                }
                updateVerificationProfileCard(null, payload.error || `검증 프로파일 조회 실패 (${response.status})`);
                return;
            }
            if (payload && payload.available === false) {
                updateVerificationProfileCard(null, payload.message || "검증 산출물이 아직 없습니다.");
                return;
            }
            updateVerificationProfileCard(payload, "");
        } catch (err) {
            updateVerificationProfileCard(null, (err && err.message) || String(err));
        }
    }

    function formatOperationsDelta(value, unit = "ms") {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return "변화 없음";
        const rounded = Math.round(number * 100) / 100;
        const sign = rounded > 0 ? "+" : "";
        return `${sign}${rounded}${unit}`;
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
        if (!payload || typeof payload !== "object" || !payload.categories) {
            dom.operationsCompare.className = "review-insight-empty";
            dom.operationsCompare.textContent = errorMessage || "최근 benchmark/smoke 결과가 없습니다.";
            return;
        }

        const categories = payload.categories || {};
        const entries = Object.entries(categories);
        if (!entries.length) {
            dom.operationsCompare.className = "review-insight-empty";
            dom.operationsCompare.textContent = "표시할 운영 검증 결과가 없습니다.";
            return;
        }

        dom.operationsCompare.className = "operations-compare-list";
        entries.forEach(([key, item]) => {
            const block = document.createElement("div");
            block.className = "operations-compare-item";
            const latest = item && item.latest ? item.latest : null;
            const previous = item && item.previous ? item.previous : null;
            const delta = item && item.delta ? item.delta : {};
            const status = String((latest && latest.status) || "unknown").toLowerCase();

            const header = document.createElement("div");
            header.className = "operations-compare-header";
            const title = document.createElement("div");
            title.className = "operations-compare-title";
            title.textContent = String((item && item.label) || key);
            const badge = document.createElement("span");
            badge.className = `operations-compare-badge operations-compare-badge--${status === "passed" ? "passed" : status === "failed" ? "failed" : "unknown"}`;
            badge.textContent = latest ? status : "missing";
            header.append(title, badge);
            block.appendChild(header);

            if (!latest) {
                const empty = document.createElement("div");
                empty.className = "operations-compare-footnote";
                empty.textContent = "최근 결과가 아직 없습니다.";
                block.appendChild(empty);
                dom.operationsCompare.appendChild(block);
                return;
            }

            const metrics = document.createElement("div");
            metrics.className = "operations-compare-meta";
            if (key === "ui_benchmark") {
                metrics.append(
                    createOperationMetric("Analyze avg", `${Math.round(Number(latest.analyze_ui_avg_ms || 0))}ms`),
                    createOperationMetric("Code jump avg", `${Math.round(Number(latest.code_jump_avg_ms || 0))}ms`),
                );
            } else if (key === "ui_real_smoke") {
                metrics.append(
                    createOperationMetric("Elapsed", `${Math.round(Number(latest.elapsed_ms || 0))}ms`),
                    createOperationMetric("Rows", `${Number(latest.rows || 0)}`),
                );
            } else {
                metrics.append(
                    createOperationMetric("Elapsed", `${Math.round(Number(latest.elapsed_ms || 0))}ms`),
                    createOperationMetric("Findings", `${Number(latest.finding_count || 0)}`),
                );
            }
            block.appendChild(metrics);

            const footnote = document.createElement("div");
            footnote.className = "operations-compare-footnote";
            const parts = [];
            parts.push(`latest=${String(latest.source_file || "").trim() || "-"}`);
            if (latest.finished_at) {
                parts.push(`finished=${String(latest.finished_at)}`);
            }
            if (previous) {
                const deltaLabel =
                    key === "ui_benchmark"
                        ? formatOperationsDelta(delta.analyze_ui_avg_ms, "ms")
                        : formatOperationsDelta(delta.elapsed_ms, "ms");
                parts.push(`prev=${String(previous.source_file || "").trim() || "-"}`);
                parts.push(`delta=${deltaLabel}`);
            }
            if (key === "ui_real_smoke" && latest.selected_file) {
                parts.push(`target=${String(latest.selected_file)}`);
            }
            if (key === "ctrlpp_integration") {
                parts.push(`binary=${latest.binary_exists ? "ready" : "missing"}`);
            }
            footnote.textContent = parts.join(" | ");
            block.appendChild(footnote);
            dom.operationsCompare.appendChild(block);
        });
    }

    async function loadLatestOperationalResults() {
        try {
            const response = await fetch("/api/operations/latest");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                renderOperationsCompare(null, payload.error || `운영 검증 비교 조회 실패 (${response.status})`);
                return;
            }
            renderOperationsCompare(payload, "");
        } catch (err) {
            renderOperationsCompare(null, (err && err.message) || String(err));
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
        if (!payload || typeof payload !== "object") {
            dom.rulesHealthCompare.className = "review-insight-empty";
            dom.rulesHealthCompare.textContent = errorMessage || "규칙 및 의존성 상태를 불러오지 못했습니다.";
            return;
        }
        state.latestRulesHealthPayload = payload;

        const rules = payload.rules || {};
        const deps = payload.dependencies || {};
        dom.rulesHealthCompare.className = "rules-health-list";

        const summary = document.createElement("div");
        summary.className = "rules-health-summary";
        [
            ["P1 enabled", `${Number(rules.p1_enabled || 0)}/${Number(rules.p1_total || 0)}`],
            ["regex", `${Number(rules.regex_count || 0)}`],
            ["composite", `${Number(rules.composite_count || 0)}`],
            ["line_repeat", `${Number(rules.line_repeat_count || 0)}`],
        ].forEach(([label, value]) => {
            const item = document.createElement("div");
            item.className = "analysis-diff-summary-item";
            const strong = document.createElement("strong");
            strong.textContent = String(value);
            item.append(strong, document.createTextNode(String(label)));
            summary.appendChild(item);
        });
        dom.rulesHealthCompare.appendChild(summary);

        const depWrap = document.createElement("div");
        depWrap.className = "rules-health-badges";
        depWrap.append(
            createRulesHealthBadge("openpyxl", !!((deps.openpyxl || {}).available)),
            createRulesHealthBadge("Ctrlpp", !!((deps.ctrlppcheck || {}).available)),
            createRulesHealthBadge("Playwright", !!((deps.playwright || {}).available)),
        );
        dom.rulesHealthCompare.appendChild(depWrap);

        const fileTypes = (rules.file_type_counts || {});
        const footnote = document.createElement("div");
        footnote.className = "operations-compare-footnote";
        const parts = [
            `Client=${Number(fileTypes.Client || 0)}`,
            `Server=${Number(fileTypes.Server || 0)}`,
        ];
        const message = String(payload.message || "").trim();
        if (message) {
            parts.push(`degraded=${message}`);
        }
        footnote.textContent = parts.join(" | ");
        dom.rulesHealthCompare.appendChild(footnote);

        const actionRow = document.createElement("div");
        actionRow.className = "rules-manage-actions";
        const manageButton = document.createElement("button");
        manageButton.type = "button";
        manageButton.className = "rules-manage-button";
        manageButton.textContent = state.rulesManageOpen ? "규칙 관리 닫기" : "규칙 관리";
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
                return;
            }
            renderRulesHealth(payload, "");
        } catch (err) {
            renderRulesHealth(null, (err && err.message) || String(err));
        }
    }

    function renderAnalysisDiffCompare(payload = null, errorMessage = "") {
        if (!dom.analysisDiffCompare) return;
        dom.analysisDiffCompare.replaceChildren();
        const hasRunOptions = Array.isArray(state.analysisDiffRunOptions) && state.analysisDiffRunOptions.length >= 2;
        if (!payload || typeof payload !== "object" || !payload.available) {
            dom.analysisDiffCompare.className = hasRunOptions ? "analysis-diff-list" : "review-insight-empty";
            if (hasRunOptions) {
                dom.analysisDiffCompare.appendChild(createAnalysisDiffControls());
                const empty = document.createElement("div");
                empty.className = "review-insight-empty";
                empty.textContent = errorMessage || String((payload && payload.message) || "비교 가능한 최근 2회 분석 결과가 없음");
                dom.analysisDiffCompare.appendChild(empty);
                return;
            }
            dom.analysisDiffCompare.textContent = errorMessage || String((payload && payload.message) || "비교 가능한 최근 2회 분석 결과가 없음");
            return;
        }

        const latest = payload.latest || {};
        const previous = payload.previous || {};
        const summaryDelta = ((payload.delta || {}).summary) || {};
        const fileDiffs = Array.isArray(payload.file_diffs) ? payload.file_diffs : [];
        const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
        const changedFiles = fileDiffs.filter((item) => {
            const status = String((item && item.status) || "");
            return status === "changed" || status === "added" || status === "removed";
        }).slice(0, 5);

        dom.analysisDiffCompare.className = "analysis-diff-list";
        if (String(latest.timestamp || "").trim()) {
            state.selectedAnalysisDiffLatest = String(latest.timestamp || "");
        }
        if (String(previous.timestamp || "").trim()) {
            state.selectedAnalysisDiffPrevious = String(previous.timestamp || "");
        }
        if (hasRunOptions) {
            dom.analysisDiffCompare.appendChild(createAnalysisDiffControls());
        }

        const header = document.createElement("div");
        header.className = "analysis-diff-header";
        header.textContent = `latest=${String(latest.timestamp || latest.output_dir || "-")} | prev=${String(previous.timestamp || previous.output_dir || "-")}`;
        dom.analysisDiffCompare.appendChild(header);

        if (warnings.length) {
            const warning = document.createElement("div");
            warning.className = "analysis-diff-header";
            warning.textContent = warnings[0];
            dom.analysisDiffCompare.appendChild(warning);
        }

        const summaryWrap = document.createElement("div");
        summaryWrap.className = "analysis-diff-summary";
        [
            ["전체", Number(summaryDelta.total || 0)],
            ["P1", Number(summaryDelta.p1_total || 0)],
            ["P2", Number(summaryDelta.p2_total || 0)],
            ["P3", Number(summaryDelta.p3_total || 0)],
            ["치명", Number(summaryDelta.critical || 0)],
            ["경고", Number(summaryDelta.warning || 0)],
        ].forEach(([label, value]) => {
            const item = document.createElement("div");
            item.className = "analysis-diff-summary-item";
            const strong = document.createElement("strong");
            strong.textContent = `${value > 0 ? "+" : ""}${value}`;
            item.append(strong, document.createTextNode(String(label)));
            summaryWrap.appendChild(item);
        });
        dom.analysisDiffCompare.appendChild(summaryWrap);

        if (!changedFiles.length) {
            const empty = document.createElement("div");
            empty.className = "analysis-diff-header";
            empty.textContent = "변화가 있는 파일이 없습니다.";
            dom.analysisDiffCompare.appendChild(empty);
            return;
        }

        const fileList = document.createElement("div");
        fileList.className = "analysis-diff-file-list";
        changedFiles.forEach((item) => {
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

            const deltaCounts = item.delta_counts || {};
            const meta = document.createElement("div");
            meta.className = "analysis-diff-file-meta";
            meta.textContent = [
                `total ${Number(deltaCounts.total || 0) > 0 ? "+" : ""}${Number(deltaCounts.total || 0)}`,
                `P1 ${Number(deltaCounts.p1_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p1_total || 0)}`,
                `P2 ${Number(deltaCounts.p2_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p2_total || 0)}`,
                `P3 ${Number(deltaCounts.p3_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p3_total || 0)}`,
            ].join(" | ");

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
        button.textContent = "선택 비교";
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
                renderAnalysisDiffCompare(null, payload.error || `분석 결과 diff 조회 실패 (${response.status})`);
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
                renderAnalysisDiffCompare(null, payload.error || `분석 결과 diff 조회 실패 (${response.status})`);
                return;
            }
            renderAnalysisDiffCompare(payload, "");
        } catch (err) {
            renderAnalysisDiffCompare(null, (err && err.message) || String(err));
        }
    }

    function updateDashboard() {
        const summary = (state.analysisData && state.analysisData.summary) || {};
        if (dom.totalText) dom.totalText.textContent = summary.total || 0;
        if (dom.criticalText) dom.criticalText.textContent = summary.critical || 0;
        if (dom.warningText) dom.warningText.textContent = summary.warning || 0;
        if (dom.scoreBar) dom.scoreBar.style.width = `${summary.score || 0}%`;
        if (dom.scoreText) dom.scoreText.textContent = `점수: ${summary.score || 0}/100`;
        updateVerificationBadge();
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
        renderOperationsCompare,
        renderRulesHealth,
        updateDashboard,
        updateVerificationBadge,
        updateVerificationProfileCard,
    };
}
