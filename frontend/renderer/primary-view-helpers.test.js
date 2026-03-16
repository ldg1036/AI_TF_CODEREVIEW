import { buildPrimaryViewState, normalizePrimaryView } from "./primary-view-helpers.js";

describe("primary view helpers", () => {
    test("normalizePrimaryView falls back to dashboard", () => {
        expect(normalizePrimaryView("SETTINGS")).toBe("settings");
        expect(normalizePrimaryView("unknown")).toBe("dashboard");
        expect(normalizePrimaryView("")).toBe("dashboard");
    });

    test("buildPrimaryViewState marks the active nav and visible view", () => {
        expect(buildPrimaryViewState("settings")).toEqual({
            activeView: "settings",
            dashboardVisible: false,
            workspaceVisible: false,
            settingsVisible: true,
            nav: {
                dashboard: false,
                workspace: false,
                settings: true,
            },
        });
    });
});
