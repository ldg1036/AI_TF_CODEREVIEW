import {
    canonicalFileId,
    messageSearchToken,
    normalizeP1RuleId,
    parseUnifiedDiffForSplit,
    sameFileIdentity,
    violationDisplayFile,
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

    test("canonicalFileId normalizes pnl aliases and reviewed txt", () => {
        expect(canonicalFileId("panel.pnl")).toBe("panel_pnl.txt");
        expect(canonicalFileId("panel_pnl_REVIEWED.txt")).toBe("panel_pnl.txt");
    });

    test("sameFileIdentity treats pnl alias and canonical txt as equal", () => {
        expect(sameFileIdentity("panel.pnl", "panel_pnl.txt")).toBe(true);
        expect(sameFileIdentity("panel_pnl_REVIEWED.txt", "panel.pnl")).toBe(true);
    });

    test("violationDisplayFile resolves nested file descriptors from proposal-like objects", () => {
        expect(violationDisplayFile({
            file: {
                requested_name: "panel.pnl",
                canonical_name: "panel_pnl.txt",
                canonical_file_id: "panel_pnl.txt",
                display_name: "panel_pnl.txt",
            },
        })).toBe("panel_pnl.txt");
    });
});
