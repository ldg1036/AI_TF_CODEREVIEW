export function deriveVerificationBadgeState(analysisData = {}) {
    const summary = (analysisData && analysisData.summary) || {};
    const metrics = (analysisData && analysisData.metrics) || {};
    const level = String(summary.verification_level || "").trim().toUpperCase();
    const optionalDeps = metrics.optional_dependencies || {};
    const openpyxlAvailable = !!(optionalDeps.openpyxl && optionalDeps.openpyxl.available);
    const openpyxlText = openpyxlAvailable ? "사용 가능" : "없음";
    if (level === "CORE_ONLY") {
        return {
            text: "검증 레벨 CORE_ONLY",
            className: "verification-badge--core-only",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    if (level === "CORE+REPORT") {
        return {
            text: "검증 레벨 CORE+REPORT",
            className: "verification-badge--core-report",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    if (level === "FULL_WITH_OPTIONALS") {
        return {
            text: "검증 레벨 FULL_WITH_OPTIONALS",
            className: "verification-badge--full",
            title: `verification_level=${level}, openpyxl=${openpyxlText}`,
        };
    }
    return {
        text: "검증 레벨 UNKNOWN",
        className: "verification-badge--unknown",
        title: `verification_level=${level || "UNKNOWN"}, openpyxl=${openpyxlText}`,
    };
}

export function deriveVerificationProfileState(payload = null, errorMessage = "") {
    if (!payload || typeof payload !== "object") {
        return {
            className: "verification-profile-card--unknown",
            text: "검증 프로파일 없음",
            title: errorMessage || "검증 프로파일 결과가 아직 없습니다.",
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
            text: `검증 실패 ${failed}건`,
            title: sourceFile ? `latest=${sourceFile}` : "최신 검증 프로파일",
        };
    }
    if (skipped > 0) {
        return {
            className: "verification-profile-card--degraded",
            text: `검증 통과 ${passed}건 | 선택 건너뜀 ${skipped}건`,
            title: sourceFile ? `latest=${sourceFile}` : "최신 검증 프로파일",
        };
    }
    return {
        className: "verification-profile-card--ok",
        text: `검증 통과 ${passed}건`,
        title: sourceFile ? `latest=${sourceFile}` : "최신 검증 프로파일",
    };
}

export function formatOperationsDelta(value, unit = "ms") {
    const number = Number(value);
    if (!Number.isFinite(number) || number === 0) return "변화 없음";
    const rounded = Math.round(number * 100) / 100;
    const sign = rounded > 0 ? "+" : "";
    return `${sign}${rounded}${unit}`;
}

export function buildOperationsCompareModel(payload = null, errorMessage = "") {
    if (!payload || typeof payload !== "object" || !payload.categories) {
        return {
            className: "review-insight-empty",
            emptyMessage: errorMessage || "최근 benchmark/smoke 결과가 아직 없습니다.",
            items: [],
        };
    }

    const entries = Object.entries(payload.categories || {});
    if (!entries.length) {
        return {
            className: "review-insight-empty",
            emptyMessage: "운영 검증 결과가 아직 없습니다.",
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
                    badgeText: "없음",
                    metrics: [],
                    footnote: "",
                    emptyMessage: "최신 결과가 아직 없습니다.",
                };
            }

            let metrics = [
                { label: "소요 시간", valueText: `${Math.round(Number(latest.elapsed_ms || 0))}ms` },
                { label: "검출 수", valueText: `${Number(latest.finding_count || 0)}` },
            ];
            if (key === "ui_benchmark") {
                metrics = [
                    { label: "분석 평균", valueText: `${Math.round(Number(latest.analyze_ui_avg_ms || 0))}ms` },
                    { label: "코드 이동 평균", valueText: `${Math.round(Number(latest.code_jump_avg_ms || 0))}ms` },
                ];
            } else if (key === "ui_real_smoke") {
                metrics = [
                    { label: "소요 시간", valueText: `${Math.round(Number(latest.elapsed_ms || 0))}ms` },
                    { label: "행 수", valueText: `${Number(latest.rows || 0)}` },
                ];
            }

            const footnoteParts = [];
            footnoteParts.push(`latest=${String(latest.source_file || "").trim() || "-"}`);
            if (latest.finished_at) {
                footnoteParts.push(`완료=${String(latest.finished_at)}`);
            }
            if (previous) {
                const deltaLabel = key === "ui_benchmark"
                    ? formatOperationsDelta(delta.analyze_ui_avg_ms, "ms")
                    : formatOperationsDelta(delta.elapsed_ms, "ms");
                footnoteParts.push(`prev=${String(previous.source_file || "").trim() || "-"}`);
                footnoteParts.push(`변화=${deltaLabel}`);
            }
            if (key === "ui_real_smoke" && latest.selected_file) {
                footnoteParts.push(`대상=${String(latest.selected_file)}`);
            }
            if (key === "ctrlpp_integration") {
                footnoteParts.push(`바이너리=${latest.binary_exists ? "준비됨" : "없음"}`);
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
    const p1Health = payload.p1_config_health || {};
    const fileTypes = rules.file_type_counts || {};
    const footnoteParts = [
        `P1_total=${Number(rules.p1_total || 0)}`,
        `Client=${Number(fileTypes.Client || 0)}`,
        `Server=${Number(fileTypes.Server || 0)}`,
    ];
    const reasonCodes = Array.isArray(p1Health.reason_codes)
        ? p1Health.reason_codes.filter((value) => String(value || "").trim())
        : [];
    const message = String(payload.message || "").trim();
    if (message) {
        footnoteParts.push(`status=${message}`);
    }
    if (reasonCodes.length) {
        footnoteParts.push(`p1_health=${reasonCodes.join(",")}`);
    }
    const unsupported = Array.isArray(p1Health.unsupported_detector_ops)
        ? p1Health.unsupported_detector_ops.filter((value) => String(value || "").trim())
        : [];
    if (unsupported.length) {
        footnoteParts.push(`unsupported=${unsupported.join(", ")}`);
    }

    return {
        className: "rules-health-list",
        emptyMessage: "",
        summaryItems: [
            { label: "P1 활성", value: `${Number(p1Health.enabled_rule_count ?? rules.p1_enabled ?? 0)}` },
            { label: "미참조 rule_id", value: `${Number(p1Health.unknown_review_rule_id_count ?? rules.review_applicability_unknown_rule_id_count ?? 0)}` },
            { label: "Degraded", value: p1Health.degraded ? "YES" : "NO" },
            { label: "Mode", value: String(p1Health.mode || "configured") },
        ],
        dependencyBadges: [
            { label: "openpyxl", available: !!((deps.openpyxl || {}).available) },
            { label: "Ctrlpp", available: !!((deps.ctrlppcheck || {}).available) },
            { label: "Playwright", available: !!((deps.playwright || {}).available) },
        ],
        footnoteText: footnoteParts.join(" | "),
        manageButtonText: rulesManageOpen ? "규칙 관리 닫기" : "규칙 관리 열기",
    };
}

export function buildDashboardSummaryState(summary = {}, { currentReviewCount = 0 } = {}) {
    const score = Number(summary.score || 0);
    return {
        totalText: Number(summary.total || 0),
        currentReviewText: Math.max(0, Number.parseInt(currentReviewCount, 10) || 0),
        criticalText: Number(summary.critical || 0),
        warningText: Number(summary.warning || 0),
        scoreWidth: `${score}%`,
        scoreText: `품질 점수 ${score}/100`,
    };
}

export function buildDashboardSystemSummaryModel({
    analysisData = {},
    verificationPayload = null,
    verificationErrorMessage = "",
    operationsPayload = null,
    operationsErrorMessage = "",
    rulesHealthPayload = null,
    rulesHealthErrorMessage = "",
} = {}) {
    const verificationBadgeState = deriveVerificationBadgeState(analysisData);
    const verificationProfileState = deriveVerificationProfileState(verificationPayload, verificationErrorMessage);
    const rulesHealthState = deriveRulesHealthState({
        payload: rulesHealthPayload,
        errorMessage: rulesHealthErrorMessage,
        rulesManageOpen: false,
    });
    const operationsModel = buildOperationsCompareModel(operationsPayload, operationsErrorMessage);
    const operationLines = operationsModel.emptyMessage
        ? [operationsModel.emptyMessage]
        : operationsModel.items.slice(0, 3).map((item) => {
            const metricTexts = Array.isArray(item.metrics)
                ? item.metrics
                    .filter((metric) => metric && metric.valueText)
                    .slice(0, 2)
                    .map((metric) => `${metric.label} ${metric.valueText}`)
                : [];
            const lineParts = [`${item.label}: ${String(item.badgeText || "unknown").toUpperCase()}`];
            if (metricTexts.length) {
                lineParts.push(metricTexts.join(" | "));
            }
            return lineParts.join(" | ");
        });

    return {
        verificationBadgeState,
        verificationProfileState,
        dependencyBadges: rulesHealthState.emptyMessage ? [] : rulesHealthState.dependencyBadges,
        dependencyFootnote: rulesHealthState.emptyMessage ? rulesHealthState.emptyMessage : rulesHealthState.footnoteText,
        operationLines,
    };
}

export function buildAnalysisDiffModel(payload = null, errorMessage = "", { hasRunOptions = false } = {}) {
    if (!payload || typeof payload !== "object" || !payload.available) {
        return {
            className: hasRunOptions ? "analysis-diff-list" : "review-insight-empty",
            emptyMessage: errorMessage || String((payload && payload.message) || "최근 분석 실행 비교 결과가 없습니다."),
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
                    `전체 ${Number(deltaCounts.total || 0) > 0 ? "+" : ""}${Number(deltaCounts.total || 0)}`,
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
            { label: "전체", valueText: `${Number(summaryDelta.total || 0) > 0 ? "+" : ""}${Number(summaryDelta.total || 0)}` },
            { label: "P1", valueText: `${Number(summaryDelta.p1_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p1_total || 0)}` },
            { label: "P2", valueText: `${Number(summaryDelta.p2_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p2_total || 0)}` },
            { label: "P3", valueText: `${Number(summaryDelta.p3_total || 0) > 0 ? "+" : ""}${Number(summaryDelta.p3_total || 0)}` },
            { label: "치명", valueText: `${Number(summaryDelta.critical || 0) > 0 ? "+" : ""}${Number(summaryDelta.critical || 0)}` },
            { label: "경고", valueText: `${Number(summaryDelta.warning || 0) > 0 ? "+" : ""}${Number(summaryDelta.warning || 0)}` },
        ],
        changedFiles,
        noChangedFilesMessage: "선택한 분석 실행 간 변경된 파일이 없습니다.",
    };
}
