import {
    buildWorkspaceFileListEmptyMessage,
    buildWorkspaceSearchStateLabel,
    filterWorkspaceFilesByQuery,
    normalizeWorkspaceQuickPreset,
    rowMatchesWorkspaceQuickPreset,
    rowMatchesWorkspaceResultQuery,
} from "./workspace-search-helpers.js";

describe("workspace search helpers", () => {
    test("filterWorkspaceFilesByQuery narrows files by case-insensitive name", () => {
        const files = [{ name: "MainPanel.ctl" }, { name: "AlarmPanel.pnl" }, { name: "Helper.ctl" }];
        expect(filterWorkspaceFilesByQuery(files, "panel")).toEqual([
            { name: "MainPanel.ctl" },
            { name: "AlarmPanel.pnl" },
        ]);
    });

    test("rowMatchesWorkspaceResultQuery matches message, file, and rule ids", () => {
        const row = {
            source: "P1",
            severity: "Critical",
            object: "MainPanel",
            file: "MainPanel.ctl",
            message: "Timer leak in loop",
            rule_id: "P1-TIMER-001",
            ruleIds: ["P1-TIMER-001"],
        };
        expect(rowMatchesWorkspaceResultQuery(row, "timer")).toBe(true);
        expect(rowMatchesWorkspaceResultQuery(row, "mainpanel")).toBe(true);
        expect(rowMatchesWorkspaceResultQuery(row, "unknown")).toBe(false);
    });

    test("rowMatchesWorkspaceQuickPreset applies P1 and attention presets", () => {
        expect(rowMatchesWorkspaceQuickPreset({ source: "P1", severity: "Info" }, "p1_only")).toBe(true);
        expect(rowMatchesWorkspaceQuickPreset({ source: "P2", severity: "Warning" }, "p1_only")).toBe(false);
        expect(rowMatchesWorkspaceQuickPreset({ source: "P2", severity: "Warning" }, "attention_only")).toBe(true);
        expect(rowMatchesWorkspaceQuickPreset({ source: "P2", severity: "Info" }, "attention_only")).toBe(false);
    });

    test("normalizeWorkspaceQuickPreset falls back to all", () => {
        expect(normalizeWorkspaceQuickPreset("P1_ONLY")).toBe("p1_only");
        expect(normalizeWorkspaceQuickPreset("other")).toBe("all");
    });

    test("buildWorkspaceSearchStateLabel reports active preset and queries", () => {
        expect(buildWorkspaceSearchStateLabel({
            fileQuery: "panel",
            resultQuery: "timer",
            quickPreset: "attention_only",
        })).toBe('빠른 보기: 치명/경고 | 파일 검색: "panel" | 결과 검색: "timer"');
    });

    test("buildWorkspaceFileListEmptyMessage explains search misses", () => {
        expect(buildWorkspaceFileListEmptyMessage({ totalFileCount: 5, fileQuery: "zzz" }))
            .toContain('"zzz"');
        expect(buildWorkspaceFileListEmptyMessage({ totalFileCount: 0 }))
            .toBe("선택 가능한 파일이 아직 없습니다.");
    });
});
