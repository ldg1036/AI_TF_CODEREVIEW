import {
    applyP1TriageToRow,
    buildP1TriageKey,
    buildP1TriageMap,
    excludeSuppressedP1Rows,
    getP1TriageMeta,
    shouldHideSuppressedP1Row,
} from "./p1-triage.js";

describe("p1 triage helpers", () => {
    test("buildP1TriageKey normalizes file, rule, message, and line", () => {
        const key = buildP1TriageKey({
            file: "Folder\\Sample.ctl",
            line: "12",
            rule_id: "perf-setmultivalue-adopt-01",
            message: "Use grouped setter",
        });
        expect(key).toBe("folder/sample.ctl||PERF-SETMULTIVALUE-ADOPT-01||Use grouped setter||12");
    });

    test("buildP1TriageMap and getP1TriageMeta resolve suppressed entries", () => {
        const triageByKey = buildP1TriageMap([
            {
                triage_key: "sample.ctl||RULE-01||Token||12",
                status: "suppressed",
                reason: "already reviewed",
                note: "safe to ignore",
                match: { file: "sample.ctl", line: 12, rule_id: "RULE-01", message: "Token", issue_id: "P1-1" },
            },
        ]);
        const meta = getP1TriageMeta(
            {
                file: "sample.ctl",
                line: 12,
                rule_id: "RULE-01",
                message: "Token",
            },
            triageByKey,
        );
        expect(meta.suppressed).toBe(true);
        expect(meta.reason).toBe("already reviewed");
    });

    test("applyP1TriageToRow decorates P1 rows and leaves P2 rows open", () => {
        const triageByKey = buildP1TriageMap([
            {
                triage_key: "sample.ctl||RULE-01||Token||12",
                status: "suppressed",
                reason: "",
                note: "",
                match: { file: "sample.ctl", line: 12, rule_id: "RULE-01", message: "Token", issue_id: "P1-1" },
            },
        ]);
        const p1Row = applyP1TriageToRow({
            source: "P1",
            file: "sample.ctl",
            line: 12,
            ruleIds: ["RULE-01"],
            message: "Token",
            issueId: "P1-1",
        }, triageByKey);
        const p2Row = applyP1TriageToRow({
            source: "P2",
            file: "sample.ctl",
            line: 14,
            ruleIds: ["CTRLPP-01"],
            message: "Other",
        }, triageByKey);
        expect(p1Row.p1TriageSuppressed).toBe(true);
        expect(p2Row.p1TriageSuppressed).toBe(false);
    });

    test("suppressed rows are hidden by default but can be restored", () => {
        const rows = [
            { rowId: "p1", source: "P1", p1TriageSuppressed: true },
            { rowId: "p2", source: "P2", p1TriageSuppressed: false },
        ];
        expect(shouldHideSuppressedP1Row(rows[0], false)).toBe(true);
        expect(shouldHideSuppressedP1Row(rows[0], true)).toBe(false);
        expect(excludeSuppressedP1Rows(rows).map((row) => row.rowId)).toEqual(["p2"]);
    });
});
