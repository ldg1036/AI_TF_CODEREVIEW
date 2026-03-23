import {
    DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
    MIN_WORKSPACE_CODE_PANE_HEIGHT,
    MIN_WORKSPACE_RESULTS_PANE_HEIGHT,
    calculateWorkspaceCodePaneHeightFromPointer,
    clampWorkspaceCodePaneHeight,
} from "./workspace-resize-helpers.js";

describe("workspace resize helpers", () => {
    test("clampWorkspaceCodePaneHeight keeps the code pane within safe bounds", () => {
        expect(clampWorkspaceCodePaneHeight(120, 700)).toBe(MIN_WORKSPACE_CODE_PANE_HEIGHT);
        expect(clampWorkspaceCodePaneHeight(900, 700)).toBe(700 - MIN_WORKSPACE_RESULTS_PANE_HEIGHT);
    });

    test("clampWorkspaceCodePaneHeight falls back to the default height", () => {
        expect(clampWorkspaceCodePaneHeight(undefined, 720)).toBe(DEFAULT_WORKSPACE_CODE_PANE_HEIGHT);
    });

    test("calculateWorkspaceCodePaneHeightFromPointer grows the code pane when dragging downward", () => {
        expect(calculateWorkspaceCodePaneHeightFromPointer({
            startHeightPx: 380,
            startPointerY: 300,
            nextPointerY: 360,
            containerHeightPx: 760,
        })).toBe(440);
    });

    test("calculateWorkspaceCodePaneHeightFromPointer respects the maximum code height when dragging downward", () => {
        expect(calculateWorkspaceCodePaneHeightFromPointer({
            startHeightPx: 380,
            startPointerY: 300,
            nextPointerY: 640,
            containerHeightPx: 720,
        })).toBe(720 - MIN_WORKSPACE_RESULTS_PANE_HEIGHT);
    });

    test("calculateWorkspaceCodePaneHeightFromPointer respects the minimum code height when dragging upward", () => {
        expect(calculateWorkspaceCodePaneHeightFromPointer({
            startHeightPx: 380,
            startPointerY: 420,
            nextPointerY: 40,
            containerHeightPx: 720,
        })).toBe(MIN_WORKSPACE_CODE_PANE_HEIGHT);
    });
});
