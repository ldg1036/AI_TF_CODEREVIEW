export function deriveVerificationBadgeState(analysisData = {}) {
    const summary = (analysisData && analysisData.summary) || {};
    const metrics = (analysisData && analysisData.metrics) || {};
    const level = String(summary.verification_level || "").trim().toUpperCase();
    const optionalDeps = metrics.optional_dependencies || {};
    const openpyxlAvailable = !!(optionalDeps.openpyxl && optionalDeps.openpyxl.available);
    const openpyxlText = openpyxlAvailable ? "available" : "missing";
    if (level === "CORE_ONLY") {
        return {
            text: "Level CORE_ONLY",
            className: "verification-badge--core-only",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    if (level === "CORE+REPORT") {
        return {
            text: "Level CORE+REPORT",
            className: "verification-badge--core-report",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    if (level === "FULL_WITH_OPTIONALS") {
        return {
            text: "Level FULL_WITH_OPTIONALS",
            className: "verification-badge--full",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    return {
        text: "Level UNKNOWN",
        className: "verification-badge--unknown",
        title: `verification_level=${level || "UNKNOWN"}, openpyxl=${openpyxlText}`,
    };
}

export function deriveVerificationProfileState(payload = null, errorMessage = "") {
    if (!payload || typeof payload !== "object") {
        return {
            className: "verification-profile-card--unknown",
            text: "Profile unavailable",
            title: errorMessage || "No verification profile result is available yet.",
        };
    }
    const summary = payload.summary || {};
    const failed = Number(summary.failed || 0);
    const skipped = Number(summary.skipped_optional_missing || 0);
    const passed = Number(summary.passed || 0);
    const sourceFile = String(payload.source_file || "");
    if (failed > 0) {
        return {
            className: "verification-profile-card--failed",
            text: `Profile failed ${failed}`,
            title: sourceFile ? `latest=${sourceFile}` : "Latest verification profile",
        };
    }
    if (skipped > 0) {
        return {
            className: "verification-profile-card--degraded",
            text: `Profile passed ${passed} | skipped ${skipped}`,
            title: sourceFile ? `latest=${sourceFile}` : "Latest verification profile",
        };
    }
    return {
        className: "verification-profile-card--ok",
        text: `Profile passed ${passed}`,
        title: sourceFile ? `latest=${sourceFile}` : "Latest verification profile",
    };
}

export function formatOperationsDelta(value, unit = "ms") {
    const number = Number(value);
    if (!Number.isFinite(number) || number === 0) return "No change";
    const rounded = Math.round(number * 100) / 100;
    const sign = rounded > 0 ? "+" : "";
    return `${sign}${rounded}${unit}`;
}

export function buildOperationsCompareModel(payload = null, errorMessage = "") {
    if (!payload || typeof payload !== "object" || !payload.categories) {
        return {
            className: "review-insight-empty",
            emptyMessage: errorMessage || "Latest benchmark and smoke results are not available yet.",
            items: [],
        };
    }

    const entries = Object.entries(payload.categories || {});
    if (!entries.length) {
        return {
            className: "review-insight-empty",
            emptyMessage: "No operational verification results are available yet.",
            items: [],
        };
    }

    return {
        className: "operations-compare-list",
        emptyMessage: "",
        items: entries.map(([key, item]) => {
            const latest = item && item.latest ? item.latest : null;
            const previous = item && item.previous ? item.previous : null;
            const delta = item && item.delta ? item.delta : {};
            const status = String((latest && latest.status) || "unknown").toLowerCase();
            if (!latest) {
                return {
                    key,
                    label: String((item && item.label) || key),
                    badgeClass: "unknown",
                    badgeText: "missing",
                    metrics: [],
                    footnote: "",
                    emptyMessage: "Latest result is not available yet.",
                };
            }

            let metrics = [
                { label: "Elapsed", valueText: `${Math.round(Number(latest.elapsed_ms || 0))}ms` },
                { label: "Findings", valueText: `${Number(latest.finding_count || 0)}` },
            ];
            if (key === "ui_benchmark") {
                metrics = [
                    { label: "Analyze avg", valueText: `${Math.round(Number(latest.analyze_ui_avg_ms || 0))}ms` },
                    { label: "Code jump avg", valueText: `${Math.round(Number(latest.code_jump_avg_ms || 0))}ms` },
                ];
            } else if (key === "ui_real_smoke") {
                metrics = [
                    { label: "Elapsed", valueText: `${Math.round(Number(latest.elapsed_ms || 0))}ms` },
                    { label: "Rows", valueText: `${Number(latest.rows || 0)}` },
                ];
            }

            const footnoteParts = [];
            footnoteParts.push(`latest=${String(latest.source_file || "").trim() || "-"}`);
            if (latest.finished_at) {
                footnoteParts.push(`finished=${String(latest.finished_at)}`);
            }
            if (previous) {
                const deltaLabel = key === "ui_benchmark"
                    ? formatOperationsDelta(delta.analyze_ui_avg_ms, "ms")
                    : formatOperationsDelta(delta.elapsed_ms, "ms");
                footnoteParts.push(`prev=${String(previous.source_file || "").trim() || "-"}`);
                footnoteParts.push(`delta=${deltaLabel}`);
            }
            if (key === "ui_real_smoke" && latest.selected_file) {
                footnoteParts.push(`target=${String(latest.selected_file)}`);
            }
            if (key === "ctrlpp_integration") {
                footnoteParts.push(`binary=${latest.binary_exists ? "ready" : "missing"}`);
            }

            return {
                key,
                label: String((item && item.label) || key),
                badgeClass: status === "passed" ? "passed" : status === "failed" ? "failed" : "unknown",
                badgeText: status,
                metrics,
                footnote: footnoteParts.join(" | "),
                emptyMessage: "",
            };
        }),
    };
}

export function deriveRulesHealthState({
    payload = null,
    errorMessage = "",
    rulesManageOpen = false,
} = {}) {
    if (!payload || typeof payload !== "object") {
        return {
            className: "review-insight-empty",
            emptyMessage: errorMessage || "Could not load rules and dependency status.",
            summaryItems: [],
            dependencyBadges: [],
            footnoteText: "",
            manageButtonText: "",
        };
    }

    const rules = payload.rules || {};
    const deps = payload.dependencies || {};
    const fileTypes = rules.file_type_counts || {};
    const footnoteParts = [
        `Client=${Number(fileTypes.Client || 0)}`,
        `Server=${Number(fileTypes.Server || 0)}`,
    ];
    const message = String(payload.message || "").trim();
    if (message) {
        footnoteParts.push(`degraded=${message}`);
    }

    return {
        className: "rules-health-list",
        emptyMessage: "",
        summaryItems: [
            { label: "P1 enabled", value: `${Number(rules.p1_enabled || 0)}/${Number(rules.p1_total || 0)}` },
            { label: "regex", value: `${Number(rules.regex_count || 0)}` },
            { label: "composite", value: `${Number(rules.composite_count || 0)}` },
            { label: "line_repeat", value: `${Number(rules.line_repeat_count || 0)}` },
        ],
        dependencyBadges: [
            { label: "openpyxl", available: !!((deps.openpyxl || {}).available) },
            { label: "Ctrlpp", available: !!((deps.ctrlppcheck || {}).available) },
            { label: "Playwright", available: !!((deps.playwright || {}).available) },
        ],
        footnoteText: footnoteParts.join(" | "),
        manageButtonText: rulesManageOpen ? "Close rules manage" : "Open rules manage",
    };
}

export function buildDashboardSummaryState(summary = {}) {
    const score = Number(summary.score || 0);
    return {
        totalText: Number(summary.total || 0),
        criticalText: Number(summary.critical || 0),
        warningText: Number(summary.warning || 0),
        scoreWidth: `${score}%`,
        scoreText: `Score: ${score}/100`,
    };
}

export function buildAnalysisDiffModel(payload = null, errorMessage = "", { hasRunOptions = false } = {}) {
    if (!payload || typeof payload !== "object" || !payload.available) {
        return {
            className: hasRunOptions ? "analysis-diff-list" : "review-insight-empty",
            emptyMessage: errorMessage || String((payload && payload.message) || "No recent analysis runs are available for comparison."),
            hasRunOptions,
            latestTimestamp: "",
            previousTimestamp: "",
            headerText: "",
            warningText: "",
            summaryItems: [],
            changedFiles: [],
            noChangedFilesMessage: "",
        };
    }

    const latest = payload.latest || {};
    const previous = payload.previous || {};
    const summaryDelta = ((payload.delta || {}).summary) || {};
    const fileDiffs = Array.isArray(payload.file_diffs) ? payload.file_diffs : [];
    const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
    const changedFiles = fileDiffs
        .filter((item) => {
            const status = String((item && item.status) || "");
            return status === "changed" || status === "added" || status === "removed";
        })
        .slice(0, 5)
        .map((item) => {
            const deltaCounts = item.delta_counts || {};
            return {
                file: String(item.file || "(unknown)"),
                status: String(item.status || ""),
                metaText: [
                    `total ${Number(deltaCounts.total || 0) > 0 ? "+" : ""}${Number(deltaCounts.total || 0)}`,
                    `P1 ${Number(deltaCounts.p1_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p1_total || 0)}`,
                    `P2 ${Number(deltaCounts.p2_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p2_total || 0)}`,
                    `P3 ${Number(deltaCounts.p3_total || 0) > 0 ? "+" : ""}${Number(deltaCounts.p3_total || 0)}`,
                ].join(" | "),
            };
        });

    return {
        className: "analysis-diff-list",
        emptyMessage: "",
        hasRunOptions,
        latestTimestamp: String(latest.timestamp || ""),
        previousTimestamp: String(previous.timestamp || ""),
        headerText: `latest=${String(latest.timestamp || latest.output_dir || "-")} | prev=${String(previous.timestamp || previous.output_dir || "-")}`,
        warningText: warnings[0] || "",
        summaryItems: [
            { label: "Total", valueText: `${Number(summaryDelta.total || 0) > 0 ? "+" : ""}${Number(summaryDelta.total || 0)}` },
            { label: "P1", valueText: `${Number(summaryDelta.p1_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p1_total || 0)}` },
            { label: "P2", valueText: `${Number(summaryDelta.p2_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p2_total || 0)}` },
            { label: "P3", valueText: `${Number(summaryDelta.p3_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p3_total || 0)}` },
            { label: "Critical", valueText: `${Number(summaryDelta.critical || 0) > 0 ? "+" : ""}${Number(summaryDelta.critical || 0)}` },
            { label: "Warning", valueText: `${Number(summaryDelta.warning || 0) > 0 ? "+" : ""}${Number(summaryDelta.warning || 0)}` },
        ],
        changedFiles,
        noChangedFilesMessage: "No files changed between the selected analysis runs.",
    };
}
