import { JSDOM } from "jsdom";
import { createWorkspaceRecommendationController } from "./recommendation-filters.js";

describe("workspace recommendation controller", () => {
    test("renderWorkspaceQuickFilter shows canonical summary for active filter", () => {
        const { window } = new JSDOM("<div id='quick' class='hidden'></div><div id='text'></div>");
        global.document = window.document;

        const dom = {
            workspaceQuickFilter: window.document.getElementById("quick"),
            workspaceQuickFilterText: window.document.getElementById("text"),
            workspaceFilterSummaryText: window.document.createElement("div"),
            workspaceCommandSummaryText: window.document.createElement("div"),
            workspaceCommandSelectionText: window.document.createElement("div"),
        };
        const state = {
            activeWorkspaceRowId: "",
            activeRecommendationRowId: "",
            analysisInsights: { dedupe: { rawIssueCount: 3, displayedRowCount: 3 } },
            workspaceAnalysisInsights: {
                dedupe: { rawIssueCount: 1, displayedRowCount: 1 },
                recommendations: [{ dominantRuleFamily: "PERF", rowCount: 1, duplicateCount: 1, source: "P1" }],
            },
            recommendationInsightByRowId: new Map(),
            recommendationWorkspaceFilter: { mode: "rule_family", label: "PERF", value: "perf", source: "p1" },
            workspaceRecommendationInsightByRowId: new Map(),
            workspaceFileQuery: "",
            workspaceQuickPreset: "all",
            workspaceResultQuery: "",
            workspaceFilteredRows: [],
            workspaceRowIndex: [],
            showSuppressedP1: false,
            p1TriageLoading: false,
            p1TriageError: "",
            filterControls: {},
        };
        const headerUpdates = [];
        const controller = createWorkspaceRecommendationController({
            dom,
            state,
            helpers: {
                getInspectorAiEnabled: () => false,
                navWorkspace: () => {},
                normalizeSeverityKeyword: (value) => String(value || ""),
                severityFilterKey: (value) => String(value || "").toLowerCase() || "info",
                sourceFilterKey: (value) => String(value || "").toLowerCase() || "p1",
                updateCodeViewerHeaderMeta: () => headerUpdates.push("updated"),
                updateRendererDiagnostics: () => {},
            },
            getSelectedFiles: () => ["sample.ctl"],
            findWorkspaceRowById: () => null,
            markWorkspaceRowActive: () => {},
            focusWorkspaceRow: () => {},
            renderWorkspace: () => {},
            queueResultTableWindowRender: () => {},
        });

        controller.renderWorkspaceQuickFilter();
        expect(dom.workspaceQuickFilter.classList.contains("hidden")).toBe(false);
        expect(dom.workspaceQuickFilterText.textContent).toContain("PERF");
        expect(dom.workspaceQuickFilterText.textContent).toContain("행 1");
        expect(headerUpdates.length).toBe(1);
    });
});
