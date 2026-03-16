import {
    buildWorkspaceEmptyStateReason,
    getAdjacentWorkspaceRowId,
    resolveWorkspaceSelection,
    shouldIgnoreWorkspaceShortcut,
    toggleWorkspacePaneVisibility,
} from "./workspace-interaction-helpers.js";

describe("workspace interaction helpers", () => {
    test("resolveWorkspaceSelection keeps the active row when it is still visible", () => {
        const rows = [{ rowId: "a" }, { rowId: "b" }, { rowId: "c" }];
        const result = resolveWorkspaceSelection({
            previousRows: rows,
            nextRows: rows,
            activeRowId: "b",
        });
        expect(result.activeRowId).toBe("b");
        expect(result.preserved).toBe(true);
        expect(result.autoSelected).toBe(false);
    });

    test("resolveWorkspaceSelection falls back to the nearest surviving row", () => {
        const result = resolveWorkspaceSelection({
            previousRows: [{ rowId: "a" }, { rowId: "b" }, { rowId: "c" }],
            nextRows: [{ rowId: "a" }, { rowId: "c" }],
            activeRowId: "b",
        });
        expect(result.activeRowId).toBe("c");
        expect(result.autoSelected).toBe(true);
        expect(result.reason).toBe("fallback_nearest");
    });

    test("getAdjacentWorkspaceRowId moves to next and previous rows safely", () => {
        const rows = [{ rowId: "a" }, { rowId: "b" }, { rowId: "c" }];
        expect(getAdjacentWorkspaceRowId(rows, "b", 1)).toBe("c");
        expect(getAdjacentWorkspaceRowId(rows, "b", -1)).toBe("a");
        expect(getAdjacentWorkspaceRowId(rows, "", 1)).toBe("a");
    });

    test("buildWorkspaceEmptyStateReason explains why the table is empty", () => {
        expect(buildWorkspaceEmptyStateReason({ totalRowCount: 0 })).toContain("분석을 실행");
        expect(buildWorkspaceEmptyStateReason({ totalRowCount: 12, quickFilterText: "활성 hotspot 필터: Main" })).toContain("빠른 보기 기준");
        expect(buildWorkspaceEmptyStateReason({ totalRowCount: 3, resultQuery: "timer" })).toContain("결과 검색");
        expect(buildWorkspaceEmptyStateReason({ totalRowCount: 3, suppressedHiddenCount: 3 })).toContain("숨김 처리 포함");
    });

    test("toggleWorkspacePaneVisibility flips only the requested pane", () => {
        const next = toggleWorkspacePaneVisibility({ files: true, code: true, inspector: false }, "code");
        expect(next).toEqual({ files: true, code: false, inspector: false });
    });

    test("shouldIgnoreWorkspaceShortcut skips editable targets", () => {
        expect(shouldIgnoreWorkspaceShortcut({ target: document.createElement("input") })).toBe(true);
        expect(shouldIgnoreWorkspaceShortcut({ target: document.createElement("button") })).toBe(true);
        expect(shouldIgnoreWorkspaceShortcut({ target: document.createElement("div") })).toBe(false);
    });
});
