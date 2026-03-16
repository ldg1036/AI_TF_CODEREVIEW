import { createCodeViewerController } from "./code-viewer.js";

describe("code viewer controller", () => {
    test("pendingJumpLineForViolation prefers reviewed and precomputed targets", () => {
        const container = document.createElement("div");
        const controller = createCodeViewerController({
            dom: { codeViewer: container },
            state: {
                currentViewerContent: "",
                currentViewerLines: [],
                currentHighlightedLine: null,
                currentHighlightedLineNear: false,
            },
            caches: {
                functionScopeCacheByFile: new Map(),
                reviewedTodoCacheByFile: new Map(),
                viewerContentCache: new Map(),
            },
            virtualState: {
                codeViewerVirtualState: {
                    headerEl: null,
                    linesWrap: null,
                    topSpacer: null,
                    visibleHost: null,
                    bottomSpacer: null,
                    lineHeight: 20,
                    renderedStart: -1,
                    renderedEnd: -1,
                    scrollHandlerAttached: false,
                },
                codeViewerWindowRenderQueued: false,
            },
            helpers: {
                buildRecommendationWorkspaceFilterText: () => "",
                sourceFilterKey: () => "p1",
            },
        });
        expect(controller.pendingJumpLineForViolation({ _jump_target_line: 44, _reviewed_todo_line: 12, line: 9 })).toBe(44);
        expect(controller.pendingJumpLineForViolation({ _reviewed_todo_line: 12, line: 9 })).toBe(12);
        expect(controller.pendingJumpLineForViolation({ line: 9 })).toBe(9);
    });
});
