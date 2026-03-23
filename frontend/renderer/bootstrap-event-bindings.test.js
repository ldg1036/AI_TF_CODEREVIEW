import { JSDOM } from "jsdom";
import { bindRendererDomContentLoaded } from "./bootstrap-event-bindings.js";

describe("bootstrap event bindings", () => {
    test("DOMContentLoaded bootstraps the minimal workspace flow", async () => {
        const domEnv = new JSDOM("<body></body>", { url: "http://localhost/" });
        global.window = domEnv.window;
        global.document = domEnv.window.document;
        global.alert = () => {};

        const calls = [];
        bindRendererDomContentLoaded({
            dom: {},
            elements: {},
            state: { aiReviewExpanded: false, excelDownloadsExpanded: false, selectedAiModel: "", sessionInputSources: [] },
            helpers: {
                autofixCloseDiffModal: () => {},
                autofixSetAiReviewText: () => {},
                autofixSetDiffModalView: () => {},
                autofixSyncAiMoreMenuUi: () => calls.push("sync-ai-menu"),
                bindWorkspaceResizer: () => {},
                handleFlushExcelReportsClick: async () => {},
                loadLatestOperationalResults: async () => calls.push("ops"),
                loadLatestVerificationProfile: async () => calls.push("verify"),
                loadRulesHealth: async () => calls.push("rules"),
                p1TriageLoadEntries: async () => calls.push("triage"),
                p1TriageSetShowSuppressedP1: () => {},
                recordRendererError: () => {},
                setActivePrimaryView: () => calls.push("set-view"),
                setCodeViewerText: () => calls.push("viewer-text"),
                setExcelDownloadsExpanded: () => {},
                setInspectorTab: () => calls.push("inspector-tab"),
                toggleWorkspaceAdvanced: () => calls.push("toggle-advanced"),
                stageExternalInputs: async () => {},
                syncAiContextToggle: () => calls.push("sync-context"),
                toggleWorkspacePane: () => {},
                updateAiContextHelpText: () => {},
                updateDashboard: () => calls.push("dashboard"),
                updateExcelJobUiFromAnalysis: () => calls.push("excel"),
                updateRendererDiagnostics: () => {},
                updateWorkspaceChrome: () => calls.push("workspace-chrome"),
                updateWorkspacePaneUi: () => calls.push("pane-ui"),
                workspaceApplyCodePaneHeight: () => {},
                workspaceAttachResultTableVirtualScrollHandler: () => calls.push("attach-scroll"),
                workspaceFocusAdjacentWorkspaceRow: async () => {},
                workspaceInitFilterControls: () => calls.push("init-filters"),
                workspaceLoadFiles: async () => calls.push("load-files"),
                workspaceOpenActiveWorkspaceRow: async () => {},
                workspaceRenderWorkspace: () => {},
                workspaceRenderWorkspaceCommandBar: () => calls.push("command-bar"),
                workspaceRenderWorkspaceQuickFilter: () => calls.push("quick-filter"),
                workspaceResetWorkspaceFilters: () => {},
                workspaceSetWorkspaceFileQuery: () => {},
                workspaceSetWorkspaceQuickPreset: () => {},
                workspaceSetWorkspaceResultQuery: () => {},
            },
        });

        domEnv.window.dispatchEvent(new domEnv.window.Event("DOMContentLoaded"));
        await new Promise((resolve) => setTimeout(resolve, 0));

        expect(calls).toEqual(expect.arrayContaining([
            "triage",
            "init-filters",
            "attach-scroll",
            "command-bar",
            "quick-filter",
            "set-view",
            "excel",
            "dashboard",
            "verify",
            "ops",
            "rules",
            "viewer-text",
            "load-files",
        ]));
    });

    test("runs immediately when document is already ready", async () => {
        const domEnv = new JSDOM("<body></body>", { url: "http://localhost/" });
        global.window = domEnv.window;
        global.document = domEnv.window.document;
        global.alert = () => {};
        Object.defineProperty(domEnv.window.document, "readyState", {
            configurable: true,
            get: () => "complete",
        });

        const calls = [];
        bindRendererDomContentLoaded({
            dom: {},
            elements: {},
            state: { aiReviewExpanded: false, excelDownloadsExpanded: false, selectedAiModel: "", sessionInputSources: [] },
            helpers: {
                autofixCloseDiffModal: () => {},
                autofixSetAiReviewText: () => {},
                autofixSetDiffModalView: () => {},
                autofixSyncAiMoreMenuUi: () => {},
                bindWorkspaceResizer: () => {},
                handleFlushExcelReportsClick: async () => {},
                loadLatestOperationalResults: async () => {},
                loadLatestVerificationProfile: async () => {},
                loadRulesHealth: async () => {},
                p1TriageLoadEntries: async () => calls.push("triage"),
                p1TriageSetShowSuppressedP1: () => {},
                recordRendererError: () => {},
                setActivePrimaryView: () => {},
                setCodeViewerText: () => {},
                setExcelDownloadsExpanded: () => {},
                setInspectorTab: () => {},
                toggleWorkspaceAdvanced: () => {},
                stageExternalInputs: async () => {},
                syncAiContextToggle: () => {},
                toggleWorkspacePane: () => {},
                updateAiContextHelpText: () => {},
                updateDashboard: () => {},
                updateExcelJobUiFromAnalysis: () => {},
                updateRendererDiagnostics: () => {},
                updateWorkspaceChrome: () => {},
                updateWorkspacePaneUi: () => {},
                workspaceApplyCodePaneHeight: () => {},
                workspaceAttachResultTableVirtualScrollHandler: () => {},
                workspaceFocusAdjacentWorkspaceRow: async () => {},
                workspaceInitFilterControls: () => {},
                workspaceLoadFiles: async () => calls.push("load-files"),
                workspaceOpenActiveWorkspaceRow: async () => {},
                workspaceRenderWorkspace: () => {},
                workspaceRenderWorkspaceCommandBar: () => {},
                workspaceRenderWorkspaceQuickFilter: () => {},
                workspaceResetWorkspaceFilters: () => {},
                workspaceSetWorkspaceFileQuery: () => {},
                workspaceSetWorkspaceQuickPreset: () => {},
                workspaceSetWorkspaceResultQuery: () => {},
            },
        });

        await new Promise((resolve) => setTimeout(resolve, 0));

        expect(calls).toEqual(expect.arrayContaining([
            "triage",
            "load-files",
        ]));
    });
});
