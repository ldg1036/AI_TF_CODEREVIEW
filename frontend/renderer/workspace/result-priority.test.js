import { buildWorkspacePriorityModel, deriveWorkspaceRowPriorityMeta } from "./result-priority.js";

describe("workspace result priority", () => {
    test("groups prepared clean proposal as ready to apply", () => {
        const violation = {
            file: "sample.ctl",
            object: "sample.ctl",
            issue_id: "P1-EXC-DP-01-sample",
            rule_id: "EXC-DP-01",
            message: "Guard dpGet return value.",
            line: 17,
            priority_origin: "P1",
        };
        const row = {
            rowId: "p1:sample",
            source: "P1",
            severity: "Warning",
            violation,
            eventName: "Global",
        };
        const analysisData = {
            violations: {
                P3: [
                    {
                        file: "sample.ctl",
                        object: "sample.ctl",
                        event: "Global",
                        parent_issue_id: "P1-EXC-DP-01-sample",
                        parent_source: "P1",
                        parent_rule_id: "EXC-DP-01",
                        parent_line: 17,
                        review: "```ctl\nif (!dpGet()) return;\n```",
                        status: "Generated",
                    },
                ],
            },
        };
        const cache = new Map([
            [
                "sample.ctl||sample.ctl||Global||```ctl\nif (!dpGet()) return;\n```",
                {
                    proposals: [
                        {
                            proposal_id: "p-clean",
                            instruction_preview: { valid: true },
                            quality_preview: {
                                syntax_check_passed: true,
                                validation_errors: [],
                                blocking_errors: [],
                                identifier_reuse_confirmed: true,
                            },
                        },
                    ],
                    active_proposal_id: "p-clean",
                },
            ],
        ]);

        const meta = deriveWorkspaceRowPriorityMeta({
            row,
            analysisData,
            autofixProposalCache: cache,
        });
        expect(meta.group).toBe("ready");
        expect(meta.label).toBe("바로 적용 가능");
    });

    test("groups blocked prepared proposal as blocked", () => {
        const violation = {
            file: "sample.ctl",
            object: "sample.ctl",
            issue_id: "P1-EXC-DP-01-sample",
            rule_id: "EXC-DP-01",
            message: "Guard dpGet return value.",
            line: 17,
            priority_origin: "P1",
        };
        const row = {
            rowId: "p1:sample",
            source: "P1",
            severity: "Warning",
            violation,
            eventName: "Global",
        };
        const analysisData = {
            violations: {
                P3: [
                    {
                        file: "sample.ctl",
                        object: "sample.ctl",
                        event: "Global",
                        parent_issue_id: "P1-EXC-DP-01-sample",
                        parent_source: "P1",
                        parent_rule_id: "EXC-DP-01",
                        parent_line: 17,
                        review: "```ctl\nif (!dpGet()) return;\n```",
                        status: "Generated",
                    },
                ],
            },
        };
        const cache = new Map([
            [
                "sample.ctl||sample.ctl||Global||```ctl\nif (!dpGet()) return;\n```",
                {
                    proposals: [
                        {
                            proposal_id: "p-blocked",
                            instruction_preview: { valid: true },
                            quality_preview: {
                                syntax_check_passed: true,
                                validation_errors: [],
                                blocking_errors: ["target_issue_not_reduced"],
                                blocked_reason_text: "Preview reanalysis did not reduce the target issue.",
                                identifier_reuse_confirmed: true,
                            },
                        },
                    ],
                    active_proposal_id: "p-blocked",
                },
            ],
        ]);

        const meta = deriveWorkspaceRowPriorityMeta({
            row,
            analysisData,
            autofixProposalCache: cache,
        });
        expect(meta.group).toBe("blocked");
        expect(meta.label).toBe("적용 차단");
    });

    test("buildWorkspacePriorityModel returns grouped rows and summary counts", () => {
        const rows = [
            {
                rowId: "p1:ready",
                source: "P1",
                severity: "Critical",
                file: "a.ctl",
                line: 4,
                violation: {
                    file: "a.ctl",
                    object: "a.ctl",
                    rule_id: "EXC-DP-01",
                    message: "Guard dpGet return value.",
                    line: 4,
                    priority_origin: "P1",
                },
                eventName: "Global",
            },
            {
                rowId: "p1:review",
                source: "P1",
                severity: "Warning",
                file: "b.ctl",
                line: 8,
                violation: {
                    file: "b.ctl",
                    object: "b.ctl",
                    rule_id: "ACTIVE-01",
                    message: "Add active guard.",
                    line: 8,
                    priority_origin: "P1",
                },
                eventName: "Global",
            },
        ];
        const model = buildWorkspacePriorityModel({
            rows,
            analysisData: { violations: { P3: [] } },
            autofixProposalCache: new Map(),
        });
        expect(model.summary.total).toBe(2);
        expect(model.summary.critical).toBe(1);
        expect(model.summary.warning).toBe(1);
        expect(model.groupedRows[0].rowType).toBe("group");
        expect(model.groupedRows.some((item) => item.rowId === "p1:review")).toBe(true);
    });
});
