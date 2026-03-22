export function bindRendererGlobalShortcuts({ elements, helpers }) {
    const {
        diffModal,
        inspectorTabAi,
        workspaceView,
    } = elements;

    window.addEventListener("resize", () => {
        helpers.workspaceRefreshSplitLayout({ rerender: true });
    });

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && diffModal && !diffModal.classList.contains("hidden")) {
            helpers.autofixCloseDiffModal();
            return;
        }
        if (!workspaceView || workspaceView.style.display === "none") return;
        if (helpers.shouldIgnoreWorkspaceShortcut(event)) return;

        if (event.key === "ArrowDown" || event.key === "j" || event.key === "J" || event.key === "]") {
            event.preventDefault();
            void helpers.workspaceFocusAdjacentWorkspaceRow(1);
            return;
        }
        if (event.key === "ArrowUp" || event.key === "k" || event.key === "K" || event.key === "[") {
            event.preventDefault();
            void helpers.workspaceFocusAdjacentWorkspaceRow(-1);
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            void helpers.workspaceOpenActiveWorkspaceRow();
            return;
        }
        if (event.key === "d" || event.key === "D") {
            event.preventDefault();
            helpers.setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
            return;
        }
        if (event.key === "a" || event.key === "A") {
            if (inspectorTabAi && !inspectorTabAi.disabled) {
                event.preventDefault();
                helpers.setInspectorTab("ai", true);
            }
        }
    });
}
