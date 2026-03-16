import {
    buildAnalysisDiffModel,
    buildDashboardSummaryState,
    buildOperationsCompareModel,
    deriveRulesHealthState,
    deriveVerificationBadgeState,
    deriveVerificationProfileState,
} from "./dashboard-state-helpers.js";

describe("dashboard state helpers", () => {
    test("deriveVerificationBadgeState maps verification levels", () => {
        expect(deriveVerificationBadgeState({
            summary: { verification_level: "CORE+REPORT" },
            metrics: { optional_dependencies: { openpyxl: { available: true } } },
        })).toEqual({
            text: "검증 레벨 CORE+REPORT",
            className: "verification-badge--core-report",
            title: "verification_level=CORE+REPORT, openpyxl=사용 가능",
        });
    });

    test("deriveVerificationProfileState returns unknown when payload is missing", () => {
        expect(deriveVerificationProfileState(null, "missing"))
            .toEqual({
                className: "verification-profile-card--unknown",
                text: "검증 프로파일 없음",
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
        expect(model.items[0].metrics).toEqual([
            { label: "소요 시간", valueText: "812ms" },
            { label: "행 수", valueText: "6" },
        ]);
        expect(model.items[0].footnote).toContain("대상=A.ctl");
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
                    file_type_counts: { Client: 7, Server: 5 },
                },
                dependencies: {
                    openpyxl: { available: true },
                    ctrlppcheck: { available: false },
                    playwright: { available: true },
                },
            },
            rulesManageOpen: true,
        });
        expect(state.summaryItems[0]).toEqual({ label: "P1 사용", value: "10/12" });
        expect(state.dependencyBadges[1]).toEqual({ label: "Ctrlpp", available: false });
        expect(state.manageButtonText).toBe("규칙 관리 닫기");
    });

    test("buildDashboardSummaryState returns dashboard counters", () => {
        expect(buildDashboardSummaryState({ total: 9, critical: 1, warning: 4, score: 88 }, { currentReviewCount: 5 }))
            .toEqual({
                totalText: 9,
                currentReviewText: 5,
                criticalText: 1,
                warningText: 4,
                scoreWidth: "88%",
                scoreText: "품질 점수 88/100",
            });
    });

    test("buildAnalysisDiffModel returns an empty-state model when no payload is available", () => {
        expect(buildAnalysisDiffModel(null, "", { hasRunOptions: true }))
            .toEqual({
                className: "analysis-diff-list",
                emptyMessage: "최근 분석 실행 비교 결과가 없습니다.",
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
        expect(model.summaryItems[0]).toEqual({ label: "전체", valueText: "+3" });
        expect(model.changedFiles).toEqual([
            { file: "Main.ctl", status: "changed", metaText: "전체 +3 | P1 +2 | P2 0 | P3 +1" },
        ]);
    });
});
