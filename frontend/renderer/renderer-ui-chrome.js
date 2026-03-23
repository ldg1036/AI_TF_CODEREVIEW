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
        analysisAdvancedPanel,
        dashboardAdvanced,
        dashboardAnalyze,
        dashboardLiveAiToggle,
        dashboardOpenSettings,
        dashboardOpenWorkspace,
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
        workspaceCommandAdvanced,
        workspaceCommandDetail,
        workspaceCommandJump,
        workspacePaneCode,
        workspacePaneFiles,
        workspacePaneInspector,
        workspaceSurface,
        workspaceView,
    } = elements;

    let advancedDismissBound = false;

    function isWorkspaceViewActive(activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard")) {
        return String(activeView || "").trim().toLowerCase() === "workspace";
    }

    function isDashboardViewActive(activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard")) {
        return String(activeView || "").trim().toLowerCase() === "dashboard";
    }

    function closeWorkspaceAdvanced({ restoreFocus = false } = {}) {
        const currentUi = (state.workspaceUi && typeof state.workspaceUi === "object") ? state.workspaceUi : {};
        if (!currentUi.advancedOpen) {
            syncWorkspaceFocusMode();
            return;
        }
        state.workspaceUi = {
            ...currentUi,
            advancedOpen: false,
        };
        syncWorkspaceFocusMode();
        if (restoreFocus && workspaceCommandAdvanced && typeof workspaceCommandAdvanced.focus === "function") {
            workspaceCommandAdvanced.focus();
        }
    }

    function bindWorkspaceAdvancedDismissHandlers() {
        if (advancedDismissBound || typeof document === "undefined") return;
        advancedDismissBound = true;

        document.addEventListener("pointerdown", (event) => {
            const activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard");
            if (!isWorkspaceViewActive(activeView) && !isDashboardViewActive(activeView)) return;
            if (!state.workspaceUi || !state.workspaceUi.advancedOpen) return;
            const target = event.target;
            if (!(target instanceof Node)) return;
            if (analysisAdvancedPanel && analysisAdvancedPanel.contains(target)) return;
            if (workspaceCommandAdvanced && workspaceCommandAdvanced.contains(target)) return;
            if (dashboardAdvanced && dashboardAdvanced.contains(target)) return;
            closeWorkspaceAdvanced();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;
            const activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard");
            if (!isWorkspaceViewActive(activeView) && !isDashboardViewActive(activeView)) return;
            if (!state.workspaceUi || !state.workspaceUi.advancedOpen) return;
            closeWorkspaceAdvanced({ restoreFocus: true });
        });
    }

    function syncWorkspaceFocusMode(activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard")) {
        const workspaceActive = isWorkspaceViewActive(activeView);
        const dashboardActive = isDashboardViewActive(activeView);
        const analysisOverlayAllowed = workspaceActive || dashboardActive;
        const currentUi = (state.workspaceUi && typeof state.workspaceUi === "object") ? state.workspaceUi : {};
        if (!analysisOverlayAllowed && currentUi.advancedOpen) {
            state.workspaceUi = {
                ...currentUi,
                advancedOpen: false,
            };
        }
        const advancedOpen = analysisOverlayAllowed && !!(state.workspaceUi && state.workspaceUi.advancedOpen);
        if (typeof document !== "undefined" && document.body) {
            document.body.classList.toggle("workspace-simplified-mode", workspaceActive);
            document.body.classList.toggle("workspace-advanced-open", advancedOpen);
        }
        if (workspaceCommandAdvanced) {
            workspaceCommandAdvanced.hidden = !workspaceActive;
            workspaceCommandAdvanced.textContent = advancedOpen ? "고급 닫기" : "고급";
            workspaceCommandAdvanced.title = advancedOpen
                ? "숨겨진 운영 옵션을 닫습니다."
                : "Ctrlpp, Excel, triage, 필터 같은 운영 옵션을 엽니다.";
            workspaceCommandAdvanced.setAttribute("aria-expanded", advancedOpen ? "true" : "false");
            workspaceCommandAdvanced.textContent = advancedOpen ? "고급 닫기" : "고급";
            workspaceCommandAdvanced.title = advancedOpen
                ? "열린 고급 분석 옵션을 닫습니다."
                : "Ctrlpp, Excel, 숨김 보기 같은 고급 옵션을 엽니다.";
        }
        if (dashboardAdvanced) {
            dashboardAdvanced.hidden = !dashboardActive;
            dashboardAdvanced.textContent = advancedOpen ? "고급 닫기" : "고급";
            dashboardAdvanced.title = advancedOpen
                ? "열린 고급 분석 옵션을 닫습니다."
                : "Ctrlpp, Excel, 숨김 보기 같은 고급 옵션을 엽니다.";
            dashboardAdvanced.setAttribute("aria-expanded", advancedOpen ? "true" : "false");
        }
        if (workspaceCommandAdvanced) {
            workspaceCommandAdvanced.textContent = advancedOpen ? "고급 닫기" : "고급";
            workspaceCommandAdvanced.title = advancedOpen
                ? "고급 분석 옵션을 닫습니다."
                : "Ctrlpp, Excel, 숨김 보기 같은 고급 옵션을 엽니다.";
        }
        if (dashboardAdvanced) {
            dashboardAdvanced.textContent = advancedOpen ? "고급 닫기" : "고급";
            dashboardAdvanced.title = advancedOpen
                ? "고급 분석 옵션을 닫습니다."
                : "Ctrlpp, Excel, 숨김 보기 같은 고급 옵션을 엽니다.";
        }
        if (analysisAdvancedPanel) {
            analysisAdvancedPanel.hidden = !advancedOpen;
        }
        if (dashboardLiveAiToggle && liveAiToggle) {
            dashboardLiveAiToggle.checked = !!liveAiToggle.checked;
            dashboardLiveAiToggle.disabled = !!liveAiToggle.disabled;
        }
        if (dashboardAnalyze && elements.btnAnalyze) {
            dashboardAnalyze.disabled = !!elements.btnAnalyze.disabled;
            dashboardAnalyze.textContent = String(elements.btnAnalyze.textContent || "\uC120\uD0DD \uD56D\uBAA9 \uBD84\uC11D");
        } else if (dashboardAnalyze && !String(dashboardAnalyze.textContent || "").trim()) {
            dashboardAnalyze.textContent = "\uC120\uD0DD \uD56D\uBAA9 \uBD84\uC11D";
        }
    }

    function setActivePrimaryView(viewName) {
        const viewState = helpers.buildPrimaryViewState(viewName);
        const currentUi = (state.workspaceUi && typeof state.workspaceUi === "object") ? state.workspaceUi : {};
        state.workspaceUi = {
            ...currentUi,
            activePrimaryView: viewState.activeView,
            advancedOpen: viewState.workspaceVisible ? !!currentUi.advancedOpen : false,
        };
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
        syncWorkspaceFocusMode(viewState.activeView);
        if (viewState.workspaceVisible) {
            updateWorkspaceChrome();
            helpers.queueCodeViewerWindowRender(true);
        }
    }

    function bindPrimaryNavigation() {
        bindWorkspaceAdvancedDismissHandlers();

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

        if (dashboardOpenWorkspace) {
            dashboardOpenWorkspace.addEventListener("click", () => {
                if (navWorkspace && typeof navWorkspace.onclick === "function") {
                    navWorkspace.onclick();
                } else {
                    setActivePrimaryView("workspace");
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
        syncWorkspaceFocusMode();
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

    function toggleWorkspaceAdvanced() {
        const activeView = String((state.workspaceUi && state.workspaceUi.activePrimaryView) || "dashboard");
        if (!isWorkspaceViewActive(activeView) && !isDashboardViewActive(activeView)) return;
        state.workspaceUi = {
            ...(state.workspaceUi || {}),
            advancedOpen: !((state.workspaceUi && state.workspaceUi.advancedOpen) || false),
        };
        syncWorkspaceFocusMode();
        updateWorkspaceChrome();
    }

    function syncAiContextToggle() {
        const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
        if (dashboardLiveAiToggle) {
            dashboardLiveAiToggle.checked = liveEnabled;
            dashboardLiveAiToggle.disabled = false;
        }
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
        updateAiContextHelpTextLocalized();
    }

    function updateAiContextHelpText() {
        if (!aiContextHelp) return;
        const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
        const contextEnabled = !!(aiContextToggle && aiContextToggle.checked);
        if (!liveEnabled) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "Live AI를 켜면 추가 코드 문맥을 함께 사용해 제안 품질을 높일 수 있습니다.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }
        if (!contextEnabled) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "AI 분석 강화 옵션을 켜면 관련 코드 문맥을 더 함께 읽어 제안 품질을 높입니다.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }

        const timings = (state.analysisData && state.analysisData.metrics && state.analysisData.metrics.timings_ms) || {};
        const mcpMs = Number(timings.mcp_context);
        aiContextHelp.classList.remove("is-hidden");
        if (Number.isFinite(mcpMs) && mcpMs > 0) {
            aiContextHelp.textContent = `추가 문맥 적용 · ${Math.round(mcpMs)}ms`;
            aiContextHelp.title = `관련 코드 문맥을 더 함께 읽어 AI 제안 품질을 높였습니다. 이번 요청의 추가 문맥 로딩 시간은 ${Math.round(mcpMs)}ms입니다.`;
            return;
        }
        aiContextHelp.textContent = "추가 코드 문맥을 함께 읽어 AI 제안 품질을 높일 수 있습니다.";
        aiContextHelp.title = "AI 분석 강화가 켜져 있습니다. 관련 코드 문맥을 더 읽어 제안 품질을 높이며, 분석 시간이 조금 늘 수 있습니다.";
    }

    function updateAiContextHelpTextLocalized() {
        if (!aiContextHelp) return;
        const liveEnabled = !!(liveAiToggle && liveAiToggle.checked);
        const contextEnabled = !!(aiContextToggle && aiContextToggle.checked);
        if (!liveEnabled) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "Live AI를 켜면 추가 코드 문맥을 함께 읽는 강화 옵션을 사용할 수 있습니다.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }
        if (!contextEnabled) {
            aiContextHelp.textContent = "";
            aiContextHelp.title = "AI 분석 강화를 켜면 관련 코드 문맥을 더 읽어 제안 품질을 높일 수 있습니다.";
            aiContextHelp.classList.add("is-hidden");
            return;
        }
        const timings = (state.analysisData && state.analysisData.metrics && state.analysisData.metrics.timings_ms) || {};
        const mcpMs = Number(timings.mcp_context);
        aiContextHelp.classList.remove("is-hidden");
        if (Number.isFinite(mcpMs) && mcpMs > 0) {
            aiContextHelp.textContent = `추가 문맥 적용 · ${Math.round(mcpMs)}ms`;
            aiContextHelp.title = `관련 코드 문맥을 함께 읽어 AI 제안 품질을 높였습니다. 이번 요청의 추가 문맥 로딩 시간은 ${Math.round(mcpMs)}ms입니다.`;
            return;
        }
        aiContextHelp.textContent = "추가 코드 문맥을 함께 읽어 AI 제안 품질을 높일 수 있습니다.";
        aiContextHelp.title = "AI 분석 강화가 켜져 있습니다. 관련 코드 문맥을 더 읽어 제안 품질을 높이지만 분석 시간이 조금 늘 수 있습니다.";
    }

    function renderExternalInputSources() {
        if (externalInputSummary) {
            externalInputSummary.textContent = state.sessionInputSources.length
                ? `세션 입력 ${state.sessionInputSources.length}개`
                : "세션 입력 없음";
        }
        if (!externalInputList) return;
        externalInputList.replaceChildren();
        state.sessionInputSources.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "external-input-chip";
            const label = document.createElement("span");
            const itemTypeLabel = item.type === "folder_path" ? "폴더" : "파일";
            label.textContent = `${itemTypeLabel} · ${item.label || helpers.basenamePath(item.value)}`;
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.textContent = "제거";
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
        toggleWorkspaceAdvanced,
        toggleWorkspacePane,
        updateAiContextHelpText: updateAiContextHelpTextLocalized,
        updateInspectorActionStrip,
        updateWorkspaceChrome,
        updateWorkspacePaneUi,
    };
}
