import {
    buildAnalysisDiffModel,
    buildDashboardSummaryState,
    buildDashboardSystemSummaryModel,
    buildOperationsCompareModel,
    deriveRulesHealthState,
    deriveVerificationBadgeState,
    deriveVerificationProfileState,
} from "./dashboard-state-helpers.js";

describe("dashboard state helpers", () => {
    test("deriveVerificationBadgeState maps verification levels", () => {
        const state = deriveVerificationBadgeState({
            summary: { verification_level: "CORE+REPORT" },
            metrics: { optional_dependencies: { openpyxl: { available: true } } },
        });
        expect(state.className).toBe("verification-badge--core-report");
        expect(state.title).toContain("verification_level=CORE+REPORT");
        expect(state.title).toContain("openpyxl=");
    });

    test("deriveVerificationProfileState returns unknown when payload is missing", () => {
        expect(deriveVerificationProfileState(null, "missing")).toEqual({
            className: "verification-profile-card--unknown",
            text: expect.any(String),
            title: "missing",
        });
    });

    test("buildOperationsCompareModel builds metrics for ui_real_smoke", () => {
        const model = buildOperationsCompareModel({
            categories: {
                ui_real_smoke: {
                    label: "UI smoke",
                    latest: { status: "passed", elapsed_ms: 812, rows: 6, source_file: "latest.json", selected_file: "A.ctl" },
                    previous: { source_file: "prev.json" },
                    delta: { elapsed_ms: 12 },
                },
            },
        });
        expect(model.className).toBe("operations-compare-list");
        expect(model.items[0].metrics).toHaveLength(2);
        expect(model.items[0].metrics[0].valueText).toBe("812ms");
        expect(model.items[0].metrics[1].valueText).toBe("6");
        expect(model.items[0].footnote).toContain("A.ctl");
    });

    test("buildOperationsCompareModel renders backend-provided ui_real_smoke row counts verbatim", () => {
        const model = buildOperationsCompareModel({
            categories: {
                ui_real_smoke: {
                    label: "UI smoke",
                    latest: { status: "passed", elapsed_ms: 1200, rows: 32, selected_file: "BenchmarkP1Fixture.ctl" },
                    previous: null,
                    delta: {},
                },
            },
        });
        expect(model.items[0].metrics[1].valueText).toBe("32");
        expect(model.items[0].footnote).toContain("BenchmarkP1Fixture.ctl");
    });

    test("deriveRulesHealthState summarizes rule health and dependencies", () => {
        const state = deriveRulesHealthState({
            payload: {
                rules: {
                    p1_enabled: 10,
                    p1_total: 12,
                    regex_count: 8,
                    composite_count: 2,
                    line_repeat_count: 1,
                    review_applicability_unknown_rule_id_count: 3,
                    file_type_counts: { Client: 7, Server: 5 },
                },
                p1_config_health: {
                    mode: "degraded_fallback",
                    degraded: true,
                    enabled_rule_count: 10,
                    unknown_review_rule_id_count: 3,
                    reason_codes: ["unknown_rule_ids"],
                    unsupported_detector_ops: ["RULE-01:composite:missing_op"],
                },
                dependencies: {
                    openpyxl: { available: true },
                    ctrlppcheck: { available: false },
                    playwright: { available: true },
                },
            },
            rulesManageOpen: true,
        });
        expect(state.summaryItems[0].value).toBe("10");
        expect(state.summaryItems[1].value).toBe("3");
        expect(state.summaryItems[2]).toEqual({ label: "Degraded", value: "YES" });
        expect(state.summaryItems[3]).toEqual({ label: "Mode", value: "degraded_fallback" });
        expect(state.footnoteText).toContain("p1_health=unknown_rule_ids");
        expect(state.footnoteText).toContain("unsupported=RULE-01:composite:missing_op");
        expect(state.dependencyBadges[1]).toEqual({ label: "Ctrlpp", available: false });
        expect(state.manageButtonText).toBeTruthy();
    });

    test("buildDashboardSummaryState returns dashboard counters", () => {
        expect(buildDashboardSummaryState({ total: 9, critical: 1, warning: 4, score: 88 }, { currentReviewCount: 5 })).toEqual({
            totalText: 9,
            currentReviewText: 5,
            criticalText: 1,
            warningText: 4,
            scoreWidth: "88%",
            scoreText: expect.any(String),
        });
    });

    test("buildDashboardSystemSummaryModel creates a compact status snapshot", () => {
        const model = buildDashboardSystemSummaryModel({
            analysisData: {
                summary: { verification_level: "CORE+REPORT" },
                metrics: { optional_dependencies: { openpyxl: { available: true } } },
            },
            verificationPayload: {
                summary: { passed: 6, failed: 0, skipped_optional_missing: 0 },
                source_file: "verification.json",
            },
            operationsPayload: {
                categories: {
                    ui_real_smoke: {
                        label: "UI Real Smoke",
                        latest: { status: "passed", elapsed_ms: 1856, rows: 6 },
                    },
                },
            },
            rulesHealthPayload: {
                rules: {
                    p1_enabled: 1,
                    p1_total: 1,
                    regex_count: 1,
                    composite_count: 0,
                    line_repeat_count: 0,
                    file_type_counts: { Client: 3, Server: 4 },
                },
                dependencies: {
                    openpyxl: { available: true },
                    ctrlppcheck: { available: true },
                    playwright: { available: false },
                },
            },
        });
        expect(model.verificationBadgeState.className).toBe("verification-badge--core-report");
        expect(model.verificationProfileState.className).toBe("verification-profile-card--ok");
        expect(model.dependencyBadges).toHaveLength(3);
        expect(model.operationLines[0]).toContain("UI Real Smoke");
        expect(model.operationLines[0]).toContain("PASSED");
    });

    test("buildAnalysisDiffModel returns an empty-state model when no payload is available", () => {
        expect(buildAnalysisDiffModel(null, "", { hasRunOptions: true })).toEqual({
            className: "analysis-diff-list",
            emptyMessage: expect.any(String),
            hasRunOptions: true,
            latestTimestamp: "",
            previousTimestamp: "",
            headerText: "",
            warningText: "",
            summaryItems: [],
            changedFiles: [],
            noChangedFilesMessage: "",
        });
    });

    test("buildAnalysisDiffModel summarizes changed files and deltas", () => {
        const model = buildAnalysisDiffModel({
            available: true,
            latest: { timestamp: "20260316_1" },
            previous: { timestamp: "20260315_1" },
            delta: { summary: { total: 3, p1_total: 2, p2_total: 0, p3_total: 1, critical: 1, warning: 2 } },
            warnings: ["One generated file was skipped."],
            file_diffs: [
                { file: "Main.ctl", status: "changed", delta_counts: { total: 3, p1_total: 2, p2_total: 0, p3_total: 1 } },
                { file: "Other.ctl", status: "unchanged", delta_counts: { total: 0 } },
            ],
        }, "", { hasRunOptions: false });
        expect(model.headerText).toBe("latest=20260316_1 | prev=20260315_1");
        expect(model.warningText).toBe("One generated file was skipped.");
        expect(model.summaryItems[0].valueText).toBe("+3");
        expect(model.changedFiles).toEqual([
            { file: "Main.ctl", status: "changed", metaText: expect.any(String) },
        ]);
    });
});
