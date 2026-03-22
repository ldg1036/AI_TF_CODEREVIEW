import { JSDOM } from "jsdom";
import { createWorkspacePaneLayoutController } from "./pane-layout.js";

describe("workspace pane layout controller", () => {
    test("applyWorkspaceCodePaneHeight updates style and diagnostics", () => {
        const { window } = new JSDOM("<body></body>");
        global.document = window.document;

        const workspaceSurface = window.document.createElement("div");
        Object.defineProperty(workspaceSurface, "clientHeight", { value: 720, configurable: true });
        const workspaceResizer = window.document.createElement("div");
        workspaceResizer.getBoundingClientRect = () => ({ height: 8 });

        const diagnostics = [];
        const controller = createWorkspacePaneLayoutController({
            dom: { workspaceSurface, workspaceResizer },
            state: { workspaceUi: { paneVisibility: { code: true }, codePaneHeightPx: 410 } },
            helpers: {
                queueCodeViewerWindowRender: () => {},
                updateRendererDiagnostics: (payload) => diagnostics.push(payload),
            },
            onQueueResultRender: () => {},
        });

        const applied = controller.applyWorkspaceCodePaneHeight();
        expect(applied).toBeGreaterThan(0);
        expect(workspaceSurface.style.getPropertyValue("--workspace-code-pane-height")).toContain("px");
        expect(diagnostics.at(-1)).toEqual(expect.objectContaining({
            workspace_code_pane_height_px: applied,
            workspace_resize_active: false,
        }));
    });
});
