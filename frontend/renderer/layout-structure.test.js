import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

function loadIndexDom() {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const htmlPath = path.resolve(currentDir, "../index.html");
    const html = fs.readFileSync(htmlPath, "utf8");
    return new JSDOM(html).window.document;
}

describe("frontend layout structure", () => {
    test("keeps external input controls in the left file sidebar", () => {
        const document = loadIndexDom();
        const sidebar = document.getElementById("file-tree-sidebar");
        const headerStrip = document.querySelector(".header-action-row-analysis-strip");

        expect(sidebar).not.toBeNull();
        expect(headerStrip).not.toBeNull();
        if (!sidebar || !headerStrip) return;
        expect(sidebar.querySelector("#btn-add-external-files")).not.toBeNull();
        expect(sidebar.querySelector("#btn-add-external-folder")).not.toBeNull();
        expect(sidebar.querySelector("#external-input-summary")).not.toBeNull();
        expect(sidebar.querySelector("#external-input-list")).not.toBeNull();

        expect(headerStrip.querySelector("#btn-add-external-files")).toBeNull();
        expect(headerStrip.querySelector("#btn-add-external-folder")).toBeNull();
        expect(headerStrip.querySelector("#external-input-summary")).toBeNull();
        expect(headerStrip.querySelector("#external-input-list")).toBeNull();
    });

    test("keeps the top analysis strip focused on analyze, live ai, and advanced options", () => {
        const document = loadIndexDom();
        const headerStrip = document.querySelector(".header-action-row-analysis-strip");
        const advanced = document.getElementById("analysis-advanced-panel");
        const advancedButton = document.getElementById("workspace-command-advanced");
        const commandBar = document.getElementById("workspace-command-bar");

        expect(headerStrip).not.toBeNull();
        expect(advanced).not.toBeNull();
        expect(advancedButton).not.toBeNull();
        expect(commandBar).not.toBeNull();
        if (!headerStrip || !advanced || !advancedButton || !commandBar) return;
        expect(headerStrip.querySelector("#analysis-strip-summary-text")).not.toBeNull();
        expect(headerStrip.querySelector("#btn-analyze")).not.toBeNull();
        expect(headerStrip.querySelector("#toggle-live-ai")).not.toBeNull();
        expect(headerStrip.querySelector("#workspace-command-advanced")).not.toBeNull();
        expect(headerStrip.querySelector("#btn-flush-excel")).toBeNull();
        expect(headerStrip.querySelector("#verification-badge")).toBeNull();
        expect(advanced.hidden).toBe(true);
        expect(advancedButton.getAttribute("aria-controls")).toBe("analysis-advanced-panel");
        expect(document.body.classList.contains("workspace-advanced-open")).toBe(false);
        expect(document.querySelector(".header-group-status")).toBeNull();
        expect(document.querySelector(".header-group-artifacts")).toBeNull();
        expect(advanced.querySelector("#verification-badge")).not.toBeNull();
        expect(advanced.querySelector("#btn-flush-excel")).not.toBeNull();
        expect(advanced.querySelector("#workspace-command-show-suppressed")).not.toBeNull();
        expect(advanced.querySelector("#workspace-command-reset")).not.toBeNull();
        expect(commandBar.querySelector("#workspace-command-show-suppressed")).toBeNull();
        expect(commandBar.querySelector("#workspace-command-reset")).toBeNull();
        expect(advanced.textContent).toContain("AI 분석 강화 (추가 문맥 사용)");
        expect(advanced.textContent).not.toContain("MCP 문맥 포함");
    });

    test("uses the same analysis strip controls in dashboard and workspace", () => {
        const document = loadIndexDom();
        const workspaceStrip = document.querySelector(".header-action-row-analysis-strip .analysis-strip-main");
        const dashboardStrip = document.querySelector("#dashboard-analysis-module .analysis-strip-main");

        expect(workspaceStrip).not.toBeNull();
        expect(dashboardStrip).not.toBeNull();
        if (!workspaceStrip || !dashboardStrip) return;

        expect(dashboardStrip.querySelector("#dashboard-analysis-summary-text")).not.toBeNull();
        expect(dashboardStrip.querySelector("#dashboard-btn-analyze")).not.toBeNull();
        expect(dashboardStrip.querySelector("#dashboard-command-advanced")).not.toBeNull();
        expect(dashboardStrip.querySelector("#dashboard-toggle-live-ai")).not.toBeNull();
    });
});
