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
});
