export function normalizePrimaryView(viewName) {
    const normalized = String(viewName || "").trim().toLowerCase();
    if (normalized === "workspace" || normalized === "settings") {
        return normalized;
    }
    return "dashboard";
}

export function buildPrimaryViewState(viewName) {
    const activeView = normalizePrimaryView(viewName);
    return {
        activeView,
        dashboardVisible: activeView === "dashboard",
        workspaceVisible: activeView === "workspace",
        settingsVisible: activeView === "settings",
        nav: {
            dashboard: activeView === "dashboard",
            workspace: activeView === "workspace",
            settings: activeView === "settings",
        },
    };
}
