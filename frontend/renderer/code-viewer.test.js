import { createCodeViewerController } from "./code-viewer.js";

describe("code viewer controller", () => {
    function createControllerWithViewer() {
        const container = document.createElement("div");
        Object.defineProperty(container, "clientHeight", {
            configurable: true,
            get: () => 320,
        });
        container.scrollTop = 0;
        window.requestAnimationFrame = (callback) => {
            callback();
            return 1;
        };
        return {
            container,
            controller: createCodeViewerController({
                dom: { codeViewer: container },
                state: {
                    currentViewerContent: "",
                    currentViewerLines: [],
                    currentHighlightedLine: null,
                    currentHighlightedLineNear: false,
                    activeJumpRequestState: { status: "idle", line: 0 },
                    recommendationWorkspaceFilter: { mode: "", label: "", value: "", source: "" },
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
            }),
        };
    }

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

    test("renderCodeViewerContent renders short files without leaving an empty virtual viewport", () => {
        const { container, controller } = createControllerWithViewer();
        controller.renderCodeViewerContent("header", "one\ntwo\nthree");
        const rows = container.querySelectorAll(".code-line");
        expect(rows).toHaveLength(3);
        expect(container.querySelector('.code-line[data-line="3"]')).not.toBeNull();
    });

    test("renderCodeViewerWindow keeps the last lines visible near the bottom of a long file", () => {
        const { container, controller } = createControllerWithViewer();
        const longContent = Array.from({ length: 500 }, (_, index) => `line ${index + 1}`).join("\n");
        controller.renderCodeViewerContent("header", longContent);
        controller.scrollCodeViewerToLine(500);
        expect(container.querySelectorAll(".code-line").length).toBeGreaterThan(0);
        expect(container.querySelector('.code-line[data-line="500"]')).not.toBeNull();
    });
});
