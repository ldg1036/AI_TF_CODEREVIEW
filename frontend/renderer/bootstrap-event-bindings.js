export function bindRendererDomContentLoaded({ dom, elements, state, helpers }) {
    const {
        aiCard,
        aiTextFull,
        btnAddExternalFiles,
        btnAddExternalFolder,
        diffModalBackdrop,
        diffModalClose,
        diffModalViewSplit,
        diffModalViewUnified,
        excelDownloadToggle,
        externalFileInput,
        externalFolderInput,
        flushExcelBtn,
        inspectorActionAi,
        inspectorActionCompare,
        inspectorActionDetail,
        inspectorActionJump,
        inspectorTabAi,
        inspectorTabDetail,
        aiReviewToggleBtn,
        dashboardAdvanced,
        dashboardAnalyze,
        dashboardLiveAiToggle,
        liveAiToggle,
        aiModelSelect,
        aiContextToggle,
        workspaceCommandPrev,
        workspaceCommandNext,
        workspaceCommandJump,
        workspaceCommandDetail,
        workspaceCommandAi,
        workspaceCommandAdvanced,
        workspaceCommandReset,
        workspaceCommandShowSuppressed,
        workspaceFileSearch,
        workspaceResultSearch,
        workspacePresetAll,
        workspacePresetP1,
        workspacePresetAttention,
        workspacePaneFiles,
        workspacePaneCode,
        workspacePaneInspector,
        workspaceResizer,
    } = elements;

    const runBootSequence = async () => {
        helpers.updateRendererDiagnostics({ boot_status: "domcontentloaded" });
        await helpers.p1TriageLoadEntries();
        helpers.workspaceInitFilterControls();
        helpers.workspaceAttachResultTableVirtualScrollHandler();
        helpers.workspaceRenderWorkspaceQuickFilter();
        helpers.workspaceRenderWorkspaceCommandBar();
        helpers.updateWorkspacePaneUi();
        helpers.setInspectorTab("detail", false);
        if (inspectorTabDetail) {
            inspectorTabDetail.addEventListener("click", () => helpers.setInspectorTab("detail", !!(aiCard && aiCard.style.display !== "none")));
        }
        if (inspectorTabAi) {
            inspectorTabAi.addEventListener("click", () => {
                if (inspectorTabAi.disabled) return;
                helpers.setInspectorTab("ai", true);
            });
        }
        helpers.autofixSyncAiMoreMenuUi();
        if (aiReviewToggleBtn) {
            aiReviewToggleBtn.addEventListener("click", () => {
                state.aiReviewExpanded = !state.aiReviewExpanded;
                const currentFull = (aiTextFull && aiTextFull.textContent) ? aiTextFull.textContent : "";
                helpers.autofixSetAiReviewText(currentFull);
            });
        }
        if (diffModalBackdrop) {
            diffModalBackdrop.addEventListener("click", helpers.autofixCloseDiffModal);
        }
        if (diffModalClose) {
            diffModalClose.addEventListener("click", helpers.autofixCloseDiffModal);
        }
        if (diffModalViewSplit) {
            diffModalViewSplit.addEventListener("click", () => helpers.autofixSetDiffModalView("split"));
        }
        if (diffModalViewUnified) {
            diffModalViewUnified.addEventListener("click", () => helpers.autofixSetDiffModalView("unified"));
        }
        if (workspaceCommandPrev) {
            workspaceCommandPrev.addEventListener("click", () => {
                void helpers.workspaceFocusAdjacentWorkspaceRow(-1);
            });
        }
        if (workspaceCommandNext) {
            workspaceCommandNext.addEventListener("click", () => {
                void helpers.workspaceFocusAdjacentWorkspaceRow(1);
            });
        }
        if (workspaceCommandJump) {
            workspaceCommandJump.addEventListener("click", () => {
                void helpers.workspaceOpenActiveWorkspaceRow();
            });
        }
        if (workspaceCommandDetail) {
            workspaceCommandDetail.addEventListener("click", () => {
                helpers.setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
            });
        }
        if (workspaceCommandAi) {
            workspaceCommandAi.addEventListener("click", () => {
                if (inspectorTabAi && !inspectorTabAi.disabled) {
                    helpers.setInspectorTab("ai", true);
                }
            });
        }
        if (workspaceCommandAdvanced) {
            workspaceCommandAdvanced.addEventListener("click", () => helpers.toggleWorkspaceAdvanced());
        }
        if (dashboardAdvanced) {
            dashboardAdvanced.addEventListener("click", () => helpers.toggleWorkspaceAdvanced());
        }
        if (dashboardAnalyze) {
            dashboardAnalyze.addEventListener("click", () => {
                if (elements.btnAnalyze && typeof elements.btnAnalyze.click === "function") {
                    elements.btnAnalyze.click();
                }
            });
        }
        if (workspaceCommandReset) {
            workspaceCommandReset.addEventListener("click", () => helpers.workspaceResetWorkspaceFilters());
        }
        if (workspaceCommandShowSuppressed) {
            workspaceCommandShowSuppressed.addEventListener("change", () => {
                helpers.p1TriageSetShowSuppressedP1(!!workspaceCommandShowSuppressed.checked);
                helpers.workspaceRenderWorkspace({ autoSelect: true, resetScroll: false });
                helpers.updateWorkspaceChrome();
            });
        }
        if (workspaceFileSearch) {
            workspaceFileSearch.addEventListener("input", (event) => {
                helpers.workspaceSetWorkspaceFileQuery(event.target && event.target.value ? event.target.value : "");
            });
        }
        if (workspaceResultSearch) {
            workspaceResultSearch.addEventListener("input", (event) => {
                helpers.workspaceSetWorkspaceResultQuery(event.target && event.target.value ? event.target.value : "");
            });
        }
        if (workspacePresetAll) {
            workspacePresetAll.addEventListener("click", () => helpers.workspaceSetWorkspaceQuickPreset("all"));
        }
        if (workspacePresetP1) {
            workspacePresetP1.addEventListener("click", () => helpers.workspaceSetWorkspaceQuickPreset("p1_only"));
        }
        if (workspacePresetAttention) {
            workspacePresetAttention.addEventListener("click", () => helpers.workspaceSetWorkspaceQuickPreset("attention_only"));
        }
        if (workspacePaneFiles) {
            workspacePaneFiles.addEventListener("click", () => helpers.toggleWorkspacePane("files"));
        }
        if (workspacePaneCode) {
            workspacePaneCode.addEventListener("click", () => helpers.toggleWorkspacePane("code"));
        }
        if (workspacePaneInspector) {
            workspacePaneInspector.addEventListener("click", () => helpers.toggleWorkspacePane("inspector"));
        }
        if (workspaceResizer) {
            helpers.bindWorkspaceResizer();
            helpers.workspaceApplyCodePaneHeight();
        }
        if (inspectorActionJump) {
            inspectorActionJump.addEventListener("click", () => {
                void helpers.workspaceOpenActiveWorkspaceRow();
            });
        }
        if (inspectorActionDetail) {
            inspectorActionDetail.addEventListener("click", () => {
                helpers.setInspectorTab("detail", !!(inspectorTabAi && !inspectorTabAi.disabled));
            });
        }
        if (inspectorActionAi) {
            inspectorActionAi.addEventListener("click", () => {
                if (inspectorTabAi && !inspectorTabAi.disabled) {
                    helpers.setInspectorTab("ai", true);
                }
            });
        }
        if (inspectorActionCompare) {
            inspectorActionCompare.addEventListener("click", () => {
                const compareBtn = document.getElementById("btn-ai-diff");
                if (compareBtn && !compareBtn.disabled) {
                    compareBtn.click();
                }
            });
        }
        if (liveAiToggle) {
            liveAiToggle.addEventListener("change", helpers.syncAiContextToggle);
        }
        if (dashboardLiveAiToggle && liveAiToggle) {
            dashboardLiveAiToggle.addEventListener("change", () => {
                liveAiToggle.checked = !!dashboardLiveAiToggle.checked;
                helpers.syncAiContextToggle();
            });
        }
        if (aiModelSelect) {
            aiModelSelect.addEventListener("change", () => {
                state.selectedAiModel = String(aiModelSelect.value || "");
            });
        }
        if (aiContextToggle) {
            aiContextToggle.addEventListener("change", helpers.updateAiContextHelpText);
        }
        if (flushExcelBtn) {
            flushExcelBtn.addEventListener("click", () => {
                void helpers.handleFlushExcelReportsClick();
            });
        }
        if (excelDownloadToggle) {
            excelDownloadToggle.addEventListener("click", () => {
                helpers.setExcelDownloadsExpanded(!state.excelDownloadsExpanded);
            });
        }
        if (btnAddExternalFiles && externalFileInput) {
            btnAddExternalFiles.addEventListener("click", () => externalFileInput.click());
            externalFileInput.addEventListener("change", async () => {
                try {
                    await helpers.stageExternalInputs(externalFileInput.files, "files");
                } catch (err) {
                    alert(`외부 파일을 추가하지 못했습니다: ${String((err && err.message) || err || "")}`);
                } finally {
                    externalFileInput.value = "";
                }
            });
        }
        if (btnAddExternalFolder && externalFolderInput) {
            btnAddExternalFolder.addEventListener("click", () => externalFolderInput.click());
            externalFolderInput.addEventListener("change", async () => {
                try {
                    await helpers.stageExternalInputs(externalFolderInput.files, "folder");
                } catch (err) {
                    alert(`외부 폴더를 추가하지 못했습니다: ${String((err && err.message) || err || "")}`);
                } finally {
                    externalFolderInput.value = "";
                }
            });
        }
        helpers.syncAiContextToggle();
        helpers.setActivePrimaryView("dashboard");
        helpers.updateExcelJobUiFromAnalysis();
        helpers.updateDashboard();
        await helpers.loadLatestVerificationProfile();
        await helpers.loadLatestOperationalResults();
        await helpers.loadRulesHealth();
        helpers.setCodeViewerText("// 파일을 선택하면 원본 코드와 검토 세부 정보를 여기에 표시합니다.");
        try {
            await helpers.workspaceLoadFiles();
            helpers.updateRendererDiagnostics({ boot_status: "ready" });
            helpers.updateWorkspaceChrome();
        } catch (err) {
            helpers.recordRendererError(err);
            helpers.updateRendererDiagnostics({
                boot_status: "file_load_failed",
                file_list_status: "load_failed",
            });
            alert(`파일 목록을 불러오지 못했습니다: ${(err && err.message) || String(err)}`);
        }
    };

    if (document.readyState === "loading") {
        window.addEventListener("DOMContentLoaded", () => {
            void runBootSequence();
        }, { once: true });
        return;
    }
    void runBootSequence();
}
