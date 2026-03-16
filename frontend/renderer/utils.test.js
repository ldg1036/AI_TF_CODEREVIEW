import {
    messageSearchToken,
    normalizeP1RuleId,
    parseUnifiedDiffForSplit,
} from "./utils.js";

describe("renderer utils", () => {
    test("normalizeP1RuleId maps known cfg aliases", () => {
        expect(normalizeP1RuleId("cfg-getmultivalue-adopt-01")).toBe("PERF-GETMULTIVALUE-ADOPT-01");
        expect(normalizeP1RuleId("perf-demo-01")).toBe("PERF-DEMO-01");
    });

    test("messageSearchToken extracts a useful search key", () => {
        expect(messageSearchToken("Uninitialized variable: speedValue")).toBe("speedValue");
        expect(messageSearchToken("Please review function checkAlarm(state) call path")).toBe("checkAlarm(state)");
    });

    test("parseUnifiedDiffForSplit groups before and after rows", () => {
        const diff = [
            "@@ -1,3 +1,3 @@",
            " line-1",
            "-old-value",
            "+new-value",
        ].join("\n");
        const parsed = parseUnifiedDiffForSplit(diff);
        expect(parsed.beforeRows.some((row) => row.text === "old-value")).toBe(true);
        expect(parsed.afterRows.some((row) => row.text === "new-value")).toBe(true);
    });
});
