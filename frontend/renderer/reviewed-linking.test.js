import { buildReviewedP1SyncPlan, extractReviewCodeBlocks, reviewHasGroupedExample } from "./reviewed-linking.js";

describe("reviewed linking", () => {
    test("extractReviewCodeBlocks returns fenced blocks", () => {
        const blocks = extractReviewCodeBlocks("Before\n```ctl\nDebugN(\"x\");\n```\nAfter");
        expect(blocks).toEqual(['DebugN("x");']);
    });

    test("reviewHasGroupedExample detects grouped setter examples", () => {
        const review = "```ctl\nsetMultiValue('a', 'b', 'c');\n```";
        expect(reviewHasGroupedExample("PERF-SETMULTIVALUE-ADOPT-01", review)).toBe(true);
    });

    test("buildReviewedP1SyncPlan matches reviewed todo blocks to p1 violations", () => {
        const reviewedTodoCacheByFile = new Map([
            ["sample_reviewed.txt", [
                {
                    todo_line: 3,
                    message: "Use grouped setter",
                    severity: "Warning",
                    meta: {
                        issue_id: "P1-1",
                        file: "sample.ctl",
                        line: "12",
                        rule_id: "PERF-SETMULTIVALUE-ADOPT-01",
                    },
                },
            ]],
        ]);
        const p1Groups = [
            {
                object: "sample.ctl",
                event: "Global",
                violations: [
                    {
                        issue_id: "P1-1",
                        line: 12,
                        rule_id: "PERF-SETMULTIVALUE-ADOPT-01",
                        severity: "Warning",
                        message: "Use grouped setter",
                    },
                ],
            },
        ];
        const plan = buildReviewedP1SyncPlan({
            p1Groups,
            reviewedTodoCacheByFile,
            pickHigherSeverity: (left, right) => right || left,
        });
        expect(plan.rowPlans).toHaveLength(1);
        expect(plan.rowPlans[0].syncState).toBe("synced");
        expect(plan.mappingDiagnostics.reviewed_block_total).toBe(1);
    });

    test("buildReviewedP1SyncPlan keeps backend rule and severity for matched rows", () => {
        const reviewedTodoCacheByFile = new Map([
            ["sample_reviewed.txt", [
                {
                    todo_line: 9,
                    message: "Wrap dpGet with try/catch",
                    severity: "Info",
                    meta: {
                        issue_id: "shared-issue",
                        file: "sample.ctl",
                        line: "18",
                        rule_id: "EXC-DP-01",
                    },
                },
            ]],
        ]);
        const p1Groups = [
            {
                object: "sample.ctl",
                event: "Global",
                violations: [
                    {
                        issue_id: "shared-issue",
                        line: 18,
                        rule_id: "EXC-TRY-01",
                        severity: "Info",
                        message: "Use try/catch",
                    },
                    {
                        issue_id: "shared-issue",
                        line: 18,
                        rule_id: "EXC-DP-01",
                        severity: "Critical",
                        message: "Guard dpGet with error handling",
                    },
                ],
            },
        ];
        const plan = buildReviewedP1SyncPlan({
            p1Groups,
            reviewedTodoCacheByFile,
            pickHigherSeverity: (left, right) => right || left,
        });
        expect(plan.rowPlans).toHaveLength(1);
        expect(plan.rowPlans[0].syncState).toBe("synced");
        expect(plan.rowPlans[0].baseViolation.rule_id).toBe("EXC-DP-01");
        expect(plan.rowPlans[0].baseViolation.severity).toBe("Critical");
        expect(plan.rowPlans[0].matchedItems[0].violation.rule_id).toBe("EXC-DP-01");
    });

    test("buildReviewedP1SyncPlan creates REVIEW-ONLY synthetic rows only for unmatched reviewed blocks", () => {
        const reviewedTodoCacheByFile = new Map([
            ["sample_reviewed.txt", [
                {
                    todo_line: 5,
                    message: "Unmatched reviewed note",
                    severity: "Warning",
                    meta: {
                        file: "sample.ctl",
                        line: "27",
                    },
                },
            ]],
        ]);
        const plan = buildReviewedP1SyncPlan({
            p1Groups: [],
            reviewedTodoCacheByFile,
            pickHigherSeverity: (left, right) => right || left,
        });
        expect(plan.rowPlans).toHaveLength(1);
        expect(plan.rowPlans[0].syncState).toBe("partial");
        expect(plan.rowPlans[0].matchedItems).toEqual([]);
        expect(plan.rowPlans[0].baseViolation.issue_id).toContain("REVIEW-ONLY-");
    });

    test("buildReviewedP1SyncPlan matches reviewed aliases and still keeps backend-only rows", () => {
        const reviewedTodoCacheByFile = new Map([
            ["BenchmarkP1Fixture_REVIEWED.txt", [
                {
                    todo_line: 8,
                    message: "다중 Set 업데이트 감지, setMultiValue 구문 적용 권장.",
                    severity: "Warning",
                    meta: {},
                },
            ]],
        ]);
        const p1Groups = [
            {
                object: "BenchmarkP1Fixture.ctl",
                event: "Global",
                violations: [
                    {
                        issue_id: "P1-1",
                        line: 14,
                        rule_id: "PERF-SETMULTIVALUE-ADOPT-01",
                        severity: "Warning",
                        message: "Batch repeated setValue calls should use setMultiValue.",
                    },
                    {
                        issue_id: "P1-2",
                        line: 26,
                        rule_id: "EXC-DP-01",
                        severity: "Critical",
                        message: "dpSet requires explicit error handling.",
                    },
                ],
            },
        ];
        const plan = buildReviewedP1SyncPlan({
            p1Groups,
            reviewedTodoCacheByFile,
            pickHigherSeverity: (left, right) => right || left,
        });
        expect(plan.rowPlans).toHaveLength(2);
        expect(plan.rowPlans[0].syncState).toBe("synced");
        expect(plan.rowPlans[0].baseViolation.rule_id).toBe("PERF-SETMULTIVALUE-ADOPT-01");
        expect(plan.rowPlans[1].syncState).toBe("violation-only");
        expect(plan.rowPlans[1].baseViolation.rule_id).toBe("EXC-DP-01");
        expect(plan.leftoverCount).toBe(1);
    });
});
