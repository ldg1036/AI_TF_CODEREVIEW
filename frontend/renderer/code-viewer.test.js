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

    test("resolveReviewedJumpLineFromCache uses canonical pnl identity", () => {
        const controller = createCodeViewerController({
            dom: { codeViewer: document.createElement("div") },
            state: {
                currentViewerContent: "",
                currentViewerLines: [],
                currentHighlightedLine: null,
                currentHighlightedLineNear: false,
            },
            caches: {
                functionScopeCacheByFile: new Map(),
                reviewedTodoCacheByFile: new Map([
                    ["panel_pnl.txt", [
                        {
                            todo_line: 14,
                            message: "Avoid hardcoded path",
                            meta: { issue_id: "P1-HARD-1", rule_id: "HARD-01" },
                        },
                    ]],
                ]),
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
        expect(controller.resolveReviewedJumpLineFromCache("panel.pnl", {
            file_descriptor: { canonical_file_id: "panel_pnl.txt" },
            issue_id: "P1-HARD-1",
            rule_id: "HARD-01",
        })).toBe(14);
    });
});
