import {
    DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
    calculateWorkspaceCodePaneHeightFromPointer,
    clampWorkspaceCodePaneHeight,
} from "../workspace-resize-helpers.js";

export function createWorkspacePaneLayoutController({
    dom,
    state,
    helpers,
    onQueueResultRender,
}) {
    let activeResizeSession = null;

    function ensureWorkspaceUiState() {
        const current = (state.workspaceUi && typeof state.workspaceUi === "object") ? state.workspaceUi : {};
        if (!current.paneVisibility || typeof current.paneVisibility !== "object") {
            current.paneVisibility = { files: true, code: true, inspector: true };
        }
        if (!Number.isFinite(Number.parseInt(current.codePaneHeightPx, 10))) {
            current.codePaneHeightPx = DEFAULT_WORKSPACE_CODE_PANE_HEIGHT;
        }
        current.isResizingCodePane = !!current.isResizingCodePane;
        state.workspaceUi = current;
        return current;
    }

    function getWorkspaceResizableHeight() {
        const surfaceHeight = Math.max(0, Number.parseInt(dom.workspaceSurface && dom.workspaceSurface.clientHeight, 10) || 0);
        const resizerHeight = Math.max(0, Math.round(dom.workspaceResizer && dom.workspaceResizer.getBoundingClientRect
            ? dom.workspaceResizer.getBoundingClientRect().height
            : 0));
        return Math.max(0, surfaceHeight - resizerHeight);
    }

    function syncWorkspaceResizeUi() {
        const ui = ensureWorkspaceUiState();
        const isCodeVisible = ui.paneVisibility.code !== false;
        if (dom.workspaceSurface) {
            dom.workspaceSurface.classList.toggle("is-resizing", !!ui.isResizingCodePane);
            if (!isCodeVisible) {
                dom.workspaceSurface.style.removeProperty("--workspace-code-pane-height");
            }
        }
        if (dom.workspaceResizer) {
            dom.workspaceResizer.hidden = !isCodeVisible;
            dom.workspaceResizer.setAttribute("aria-hidden", isCodeVisible ? "false" : "true");
        }
        if (typeof document !== "undefined" && document.body) {
            document.body.classList.toggle("workspace-resize-active", !!ui.isResizingCodePane);
        }
        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                workspace_code_pane_height_px: Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
                workspace_resize_active: !!ui.isResizingCodePane,
            });
        }
    }

    function applyWorkspaceCodePaneHeight(options = {}) {
        const ui = ensureWorkspaceUiState();
        const isCodeVisible = ui.paneVisibility.code !== false;
        if (!isCodeVisible) {
            syncWorkspaceResizeUi();
            return 0;
        }
        const resizableHeight = getWorkspaceResizableHeight();
        const clampedHeight = resizableHeight > 0
            ? clampWorkspaceCodePaneHeight(ui.codePaneHeightPx, resizableHeight)
            : (Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT);
        ui.codePaneHeightPx = clampedHeight;
        state.workspaceUi = ui;
        if (dom.workspaceSurface) {
            dom.workspaceSurface.style.setProperty("--workspace-code-pane-height", `${clampedHeight}px`);
        }
        syncWorkspaceResizeUi();
        if (options.rerender) {
            if (typeof helpers.queueCodeViewerWindowRender === "function") {
                helpers.queueCodeViewerWindowRender(true);
            }
            if (typeof onQueueResultRender === "function") {
                onQueueResultRender(true);
            }
        }
        return clampedHeight;
    }

    function setWorkspaceCodePaneHeight(nextHeight, options = {}) {
        const ui = ensureWorkspaceUiState();
        ui.codePaneHeightPx = clampWorkspaceCodePaneHeight(nextHeight, getWorkspaceResizableHeight());
        state.workspaceUi = ui;
        return applyWorkspaceCodePaneHeight({ rerender: !!options.rerender });
    }

    function refreshWorkspaceSplitLayout(options = {}) {
        return applyWorkspaceCodePaneHeight({ rerender: !!options.rerender });
    }

    function stopWorkspaceResize(pointerId = null) {
        const ui = ensureWorkspaceUiState();
        ui.isResizingCodePane = false;
        state.workspaceUi = ui;
        if (dom.workspaceResizer && pointerId !== null && typeof dom.workspaceResizer.releasePointerCapture === "function") {
            try {
                dom.workspaceResizer.releasePointerCapture(pointerId);
            } catch (_) {
                // Ignore stale capture release errors.
            }
        }
        activeResizeSession = null;
        refreshWorkspaceSplitLayout({ rerender: true });
    }

    function bindWorkspaceResizer() {
        if (!dom.workspaceResizer || dom.workspaceResizer.dataset.resizeBound === "true") return;
        dom.workspaceResizer.dataset.resizeBound = "true";
        dom.workspaceResizer.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) return;
            if (event.pointerType && event.pointerType !== "mouse") return;
            const ui = ensureWorkspaceUiState();
            if (ui.paneVisibility.code === false) return;
            activeResizeSession = {
                pointerId: event.pointerId,
                startY: event.clientY,
                startHeightPx: Number.parseInt(ui.codePaneHeightPx, 10) || DEFAULT_WORKSPACE_CODE_PANE_HEIGHT,
            };
            ui.isResizingCodePane = true;
            state.workspaceUi = ui;
            syncWorkspaceResizeUi();
            if (typeof dom.workspaceResizer.setPointerCapture === "function") {
                dom.workspaceResizer.setPointerCapture(event.pointerId);
            }
            event.preventDefault();
        });
        dom.workspaceResizer.addEventListener("pointermove", (event) => {
            if (!activeResizeSession || event.pointerId !== activeResizeSession.pointerId) return;
            const nextHeight = calculateWorkspaceCodePaneHeightFromPointer({
                startHeightPx: activeResizeSession.startHeightPx,
                startPointerY: activeResizeSession.startY,
                nextPointerY: event.clientY,
                containerHeightPx: getWorkspaceResizableHeight(),
            });
            setWorkspaceCodePaneHeight(nextHeight, { rerender: false });
            event.preventDefault();
        });
        const finishResize = (event) => {
            if (!activeResizeSession) return;
            if (event && event.pointerId !== activeResizeSession.pointerId) return;
            stopWorkspaceResize(activeResizeSession.pointerId);
        };
        dom.workspaceResizer.addEventListener("pointerup", finishResize);
        dom.workspaceResizer.addEventListener("pointercancel", finishResize);
        dom.workspaceResizer.addEventListener("lostpointercapture", () => {
            if (!activeResizeSession) return;
            stopWorkspaceResize(null);
        });
    }

    return {
        applyWorkspaceCodePaneHeight,
        bindWorkspaceResizer,
        ensureWorkspaceUiState,
        refreshWorkspaceSplitLayout,
        setWorkspaceCodePaneHeight,
    };
}
