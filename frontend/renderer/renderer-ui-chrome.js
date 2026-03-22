export function createRendererUiChromeController({
    dom,
    state,
    elements,
    helpers,
}) {
    const {
        aiContextHelp,
        aiContextLabel,
        aiContextToggle,
        aiModelSelect,
        dashboardOpenSettings,
        dashboardView,
        externalInputList,
        externalInputSummary,
        fileTreeSidebar,
        inspectorActionAi,
        inspectorActionCompare,
        inspectorActionDetail,
        inspectorActionJump,
        inspectorPanel,
        inspectorTabAi,
        liveAiToggle,
        navDashboard,
        navSettings,
        navWorkspace,
        settingsView,
        workspaceCodeShell,
        workspaceCommandAi,
        workspaceCommandDetail,
        workspaceCommandJump,
        workspacePaneCode,
        workspacePaneFiles,
        workspacePaneInspector,
        workspaceSurface,
        workspaceView,
    } = elements;

    function setActivePrimaryView(viewName) {
        const viewState = helpers.buildPrimaryViewState(viewName);
        if (dashboardView) {
            dashboardView.style.display = viewState.dashboardVisible ? "block" : "none";
        }
        if (workspaceView) {
            workspaceView.style.display = viewState.workspaceVisible ? "flex" : "none";
        }
        if (settingsView) {
            settingsView.style.display = viewState.settingsVisible ? "block" : "none";
        }
        [
            [navDashboard, viewState.nav.dashboard],
            [navWorkspace, viewState.nav.workspace],
            [navSettings, viewState.nav.settings],
        ].forEach(([button, isActive]) => {
            if (!button) return;
            button.classList.toggle("is-active", !!isActive);
            if (isActive) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        });
        helpers.updateRendererDiagnostics({ active_primary_view: viewState.activeView });
        if (viewState.workspaceVisible) {
            updateWorkspaceChrome();
            helpers.queueCodeViewerWindowRender(true);
        }
    }

    function bindPrimaryNavigation() {
        navDashboard.onclick = () => {
            setActivePrimaryView("dashboard");
        };

        navWorkspace.onclick = () => {
            setActivePrimaryView("workspace");
        };

        if (navSettings) {
            navSettings.onclick = () => {
                setActivePrimaryView("settings");
            };
        }

        if (dashboardOpenSettings) {
            dashboardOpenSettings.addEventListener("click", () => {
                if (navSettings && typeof navSettings.onclick === "function") {
                    navSettings.onclick();
                } else {
                    setActivePrimaryView("settings");
                }
            });
        }
    }

    function updateWorkspacePaneUi() {
        const panes = (state.workspaceUi && state.workspaceUi.paneVisibility) || {};
        const filesOpen = panes.files !== false;
        const codeOpen = panes.code !== false;
        const inspectorOpen = panes.inspector !== false;
        fileTreeSidebar?.classList.toggle("is-collapsed", !filesOpen);
        workspaceCodeShell?.classList.toggle("is-collapsed", !codeOpen);
        workspaceSurface?.classList.toggle("is-code-collapsed", !codeOpen);
        inspectorPanel?.classList.toggle("is-collapsed", !inspectorOpen);
        if (workspacePaneFiles) workspacePaneFiles.setAttribute("aria-pressed", filesOpen ? "true" : "false");
        if (workspacePaneCode) workspacePaneCode.setAttribute("aria-pressed", codeOpen ? "true" : "false");
        if (workspacePaneInspector) workspacePaneInspector.setAttribute("aria-pressed", inspectorOpen ? "true" : "false");
    }

    function updateInspectorActionStrip() {
        const hasActiveSelection = !!String(state.activeWorkspaceRowId || "").trim();
        const aiEnabled = !!(inspectorTabAi && !inspectorTabAi.disabled);
        const compareBtn = document.getElementById("btn-ai-diff");
        const actionState = helpers.deriveInspectorActionState({
            hasActiveSelection,
            aiEnabled,
            compareEnabled: !!(compareBtn && !compareBtn.disabled),
            activeInspectorTab: state.activeInspectorTab,
        });
        if (workspaceCommandJump) workspaceCommandJump.disabled = actionState.jumpDisabled;
        if (workspaceCommandDetail) {
            workspaceCommandDetail.disabled = actionState.detailDisabled;
            workspaceCommandDetail.setAttribute("aria-pressed", actionState.detailPressed ? "true" : "false");
            workspaceCommandDetail.title = actionState.detailTitle;
        }
        if (workspaceCommandAi) {
            workspaceCommandAi.disabled = actionState.aiDisabled;
            workspaceCommandAi.setAttribute("aria-pressed", actionState.aiPressed ? "true" : "false");
            workspaceCommandAi.title = actionState.aiTitle;
        }
        if (workspaceCommandJump) workspaceCommandJump.title = actionState.jumpTitle;
        if (inspectorActionJump) {
            inspectorActionJump.disabled = actionState.jumpDisabled;
            inspectorActionJump.title = actionState.jumpTitle;
        }
        if (inspectorActionDetail) {
            inspectorActionDetail.disabled = actionState.detailDisabled;
            inspectorActionDetail.setAttribute("aria-pressed", actionState.detailPressed ? "true" : "false");
            inspectorActionDetail.title = actionState.detailTitle;
        }
        if (inspectorActionAi) {
            inspectorActionAi.disabled = actionState.aiDisabled;
            inspectorActionAi.setAttribute("aria-pressed", actionState.aiPressed ? "true" : "false");
            inspectorActionAi.title = actionState.aiTitle;
        }
        if (inspectorActionCompare) {
            inspectorActionCompare.disabled = actionState.compareDisabled;
            inspectorActionCompare.title = actionState.compareTitle;
        }
    }

    function updateWorkspaceChrome() {
        updateWorkspacePaneUi();
        helpers.workspaceRenderWorkspaceCommandBar();
        updateInspectorActionStrip();
    }

    function refreshWorkspaceAfterTriage() {
        helpers.workspaceBuildWorkspaceRowIndex();
        helpers.workspaceRenderWorkspace({ autoSelect: true, resetScroll: false });
        updateWorkspaceChrome();
    }

    function toggleWorkspacePane(paneName) {
        state.workspaceUi = {
            ...(state.workspaceUi || {}),
            paneVisibility: helpers.toggleWorkspacePaneVisibility((state.workspaceUi && state.workspaceUi.paneVisibility) || {}, paneName),
        };
        updateWorkspacePaneUi();
        helpers.workspaceRefreshSplitLayout({ rerender: true });
    }

    function syncAiContextToggle() {
        const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
        if (aiContextToggle) {
            aiContextToggle.disabled = !liveEnabled;
            if (!liveEnabled) {
                aiContextToggle.checked = false;
            }
        }
        if (aiContextLabel) {
            aiContextLabel.style.opacity = liveEnabled ? "1" : "0.7";
        }
        if (aiModelSelect) {
            if (!liveEnabled) {
                aiModelSelect.disabled = true;
            } else if (!state.aiModelCatalogLoaded) {
                void helpers.loadAiModels();
            } else {
                aiModelSelect.disabled = !aiModelSelect.options.length;
            }
        }
        updateAiContextHelpText();
    }

    function updateAiContextHelpText() {
        if (aiContextHelp) {
            const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
            const contextEnabled = !!(aiContextToggle && aiContextToggle.checked);
            if (!liveEnabled) {
                aiContextHelp.textContent = "";
                aiContextHelp.title = "Turn on Live AI to request MCP-backed context.";
                aiContextHelp.classList.add("is-hidden");
                return;
            }
            if (!contextEnabled) {
                aiContextHelp.textContent = "";
                aiContextHelp.title = "Turn on AI context to use MCP-backed context with Live AI.";
                aiContextHelp.classList.add("is-hidden");
                return;
            }

            const timings = (state.analysisData && state.analysisData.metrics && state.analysisData.metrics.timings_ms) || {};
            const mcpMs = Number(timings.mcp_context);
            if (Number.isFinite(mcpMs) && mcpMs > 0) {
                aiContextHelp.classList.remove("is-hidden");
                aiContextHelp.textContent = `MCP ${Math.round(mcpMs)}ms`;
                aiContextHelp.title = `MCP context loaded for this review in ${Math.round(mcpMs)}ms. Hover to confirm that extra context was attached to the Live AI request.`;
            } else {
                aiContextHelp.textContent = "";
                aiContextHelp.title = "MCP context is enabled, but no attached context timing was reported for the latest Live AI request.";
                aiContextHelp.classList.add("is-hidden");
            }
        }
    }

    function renderExternalInputSources() {
        if (externalInputSummary) {
            externalInputSummary.textContent = state.sessionInputSources.length
                ? `Session inputs ${state.sessionInputSources.length}`
                : "No session inputs";
        }
        if (!externalInputList) return;
        externalInputList.replaceChildren();
        state.sessionInputSources.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "external-input-chip";
            const label = document.createElement("span");
            const itemTypeLabel = item.type === "folder_path" ? "Folder" : "File";
            label.textContent = itemTypeLabel + " - " + (item.label || helpers.basenamePath(item.value));
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.textContent = "x";
            removeBtn.addEventListener("click", () => {
                state.sessionInputSources.splice(index, 1);
                renderExternalInputSources();
            });
            row.append(label, removeBtn);
            externalInputList.appendChild(row);
        });
    }

    return {
        bindPrimaryNavigation,
        refreshWorkspaceAfterTriage,
        renderExternalInputSources,
        setActivePrimaryView,
        syncAiContextToggle,
        toggleWorkspacePane,
        updateAiContextHelpText,
        updateInspectorActionStrip,
        updateWorkspaceChrome,
        updateWorkspacePaneUi,
    };
}
