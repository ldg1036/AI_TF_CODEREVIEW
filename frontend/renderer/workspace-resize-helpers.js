export const DEFAULT_WORKSPACE_CODE_PANE_HEIGHT = 380;
export const MIN_WORKSPACE_CODE_PANE_HEIGHT = 260;
export const MIN_WORKSPACE_RESULTS_PANE_HEIGHT = 150;

export function clampWorkspaceCodePaneHeight(
    heightPx,
    containerHeightPx,
    options = {},
) {
    const minCodePaneHeight = Math.max(
        120,
        Number.parseInt(options.minCodePaneHeight, 10) || MIN_WORKSPACE_CODE_PANE_HEIGHT,
    );
    const minResultsPaneHeight = Math.max(
        120,
        Number.parseInt(options.minResultsPaneHeight, 10) || MIN_WORKSPACE_RESULTS_PANE_HEIGHT,
    );
    const safeContainerHeight = Math.max(
        minCodePaneHeight + minResultsPaneHeight,
        Number.parseInt(containerHeightPx, 10) || 0,
    );
    const maxCodePaneHeight = Math.max(
        minCodePaneHeight,
        safeContainerHeight - minResultsPaneHeight,
    );
    const fallbackHeight = Math.min(DEFAULT_WORKSPACE_CODE_PANE_HEIGHT, maxCodePaneHeight);
    const candidateHeight = Number.parseFloat(heightPx);
    if (!Number.isFinite(candidateHeight)) {
        return Math.round(fallbackHeight);
    }
    return Math.round(Math.min(maxCodePaneHeight, Math.max(minCodePaneHeight, candidateHeight)));
}

export function calculateWorkspaceCodePaneHeightFromPointer({
    startHeightPx,
    startPointerY,
    nextPointerY,
    containerHeightPx,
    minCodePaneHeight,
    minResultsPaneHeight,
}) {
    const startHeight = Number.parseFloat(startHeightPx);
    const initialHeight = Number.isFinite(startHeight) ? startHeight : DEFAULT_WORKSPACE_CODE_PANE_HEIGHT;
    const startY = Number.parseFloat(startPointerY);
    const nextY = Number.parseFloat(nextPointerY);
    const deltaY = Number.isFinite(startY) && Number.isFinite(nextY) ? nextY - startY : 0;
    return clampWorkspaceCodePaneHeight(
        initialHeight + deltaY,
        containerHeightPx,
        { minCodePaneHeight, minResultsPaneHeight },
    );
}
