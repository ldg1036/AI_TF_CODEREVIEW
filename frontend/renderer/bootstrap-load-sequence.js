export function createAnalyzeRunController({
    elements,
    state,
    caches,
    helpers,
}) {
    const {
        aiContextToggle,
        aiModelSelect,
        analyzeProgressBar,
        analyzeProgressMeta,
        analyzeProgressPanel,
        analyzeProgressStatus,
        btnAnalyze,
        ctrlppToggle,
        liveAiToggle,
        navWorkspace,
    } = elements;

    function formatDurationMs(ms) {
        const safeMs = Math.max(0, Number(ms) || 0);
        const totalSec = Math.floor(safeMs / 1000);
        const minutes = Math.floor(totalSec / 60);
        const seconds = totalSec % 60;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }

    function setAnalyzeProgressVisible(visible) {
        if (!analyzeProgressPanel) return;
        analyzeProgressPanel.style.display = visible ? "block" : "none";
        helpers.updateRendererDiagnostics({ progress_panel_visible: !!visible });
    }

    function updateAnalyzeProgressUi(statusPayload = {}) {
        const status = String(statusPayload.status || "queued");
        const progress = (statusPayload && statusPayload.progress) || {};
        const timing = (statusPayload && statusPayload.timing) || {};
        const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));
        const completed = Math.max(0, Number(progress.completed_files) || 0);
        const total = Math.max(0, Number(progress.total_files) || 0);
        const currentFile = String(progress.current_file || "");
        const phase = String(progress.phase || "");
        const etaMs = timing.eta_ms;
        const elapsedMs = timing.elapsed_ms;

        let phaseLabel = "";
        if (phase === "queued") phaseLabel = "Queued";
        else if (phase === "read_source") phaseLabel = "Read source";
        else if (phase === "heuristic_review") phaseLabel = "Heuristic review";
        else if (phase === "ctrlpp_check") phaseLabel = "CtrlppCheck";
        else if (phase === "live_ai_review") phaseLabel = "Live AI";
        else if (phase === "write_reports") phaseLabel = "Write reports";
        else if (phase === "analyze_file_done") phaseLabel = "File complete";
        else if (phase === "analyze_file_failed") phaseLabel = "File failed";

        if (analyzeProgressStatus) {
            const head = status === "queued" ? "Queued..." : status === "running" ? "Running..." : status === "completed" ? "Completed" : "Failed";
            const parts = [head];
            if (currentFile) parts.push(currentFile);
            if (phaseLabel) parts.push(phaseLabel);
            analyzeProgressStatus.textContent = parts.join(" | ");
        }
        if (analyzeProgressBar) {
            analyzeProgressBar.style.width = `${percent}%`;
        }
        if (analyzeProgressMeta) {
            const etaText = Number.isFinite(Number(etaMs)) && Number(etaMs) >= 0 ? formatDurationMs(Number(etaMs)) : "Calculating...";
            const elapsedText = Number.isFinite(Number(elapsedMs)) && Number(elapsedMs) >= 0 ? formatDurationMs(Number(elapsedMs)) : "00:00";
            analyzeProgressMeta.textContent = `${percent}% | ${completed}/${total} files | ETA ${etaText} | Elapsed ${elapsedText}`;
        }
        helpers.updateRendererDiagnostics({
            progress_panel_visible: !!(analyzeProgressPanel && analyzeProgressPanel.style.display !== "none"),
            progress_status_text: analyzeProgressStatus ? String(analyzeProgressStatus.textContent || "") : "",
            progress_meta_text: analyzeProgressMeta ? String(analyzeProgressMeta.textContent || "") : "",
        });
    }

    async function applyAnalyzePayload(payload) {
        await helpers.p1TriageLoadEntries();
        state.analysisData = {
            summary: payload.summary || { total: 0, critical: 0, warning: 0, info: 0, score: 0 },
            violations: payload.violations || { P1: [], P2: [], P3: [] },
            ai_review_statuses: payload.ai_review_statuses || [],
            output_dir: payload.output_dir || "",
            metrics: payload.metrics || {},
            report_jobs: payload.report_jobs || {},
            report_paths: payload.report_paths || {},
        };
        caches.viewerContentCache.clear();
        state.workspaceRowIndex = [];
        state.analysisInsights = {
            dedupe: { rawIssueCount: 0, displayedRowCount: 0, collapsedDuplicateCount: 0 },
            recommendations: [],
        };
        caches.functionScopeCacheByFile.clear();
        state.autofixProposalCache.clear();
        helpers.setActiveJumpRequestState("idle", 0);
        helpers.autofixSetAutofixDiffPanel("");
        helpers.setAutofixValidationPanel("");
        helpers.autofixCloseDiffModal();
        const selected = helpers.workspaceGetSelectedFiles();
        await helpers.prepareFunctionScopeCacheForSelectedFiles(selected);
        helpers.workspaceBuildWorkspaceRowIndex();

        helpers.workspaceRenderWorkspace();
        helpers.updateWorkspaceChrome();
        helpers.updateRendererDiagnostics({
            analyze_status: "completed",
            analyze_error: "",
            selected_file_count: selected.length,
            result_row_count: Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows.length : 0,
            last_analyze_result_summary: {
                total: Number((state.analysisData.summary && state.analysisData.summary.total) || 0),
                critical: Number((state.analysisData.summary && state.analysisData.summary.critical) || 0),
                warning: Number((state.analysisData.summary && state.analysisData.summary.warning) || 0),
                info: Number((state.analysisData.summary && state.analysisData.summary.info) || 0),
                score: Number((state.analysisData.summary && state.analysisData.summary.score) || 0),
            },
        });
        helpers.updateExcelJobUiFromAnalysis();
        helpers.updateAiContextHelpText();
        if (typeof navWorkspace.onclick === "function") {
            navWorkspace.onclick();
        }
        void helpers.loadLatestVerificationProfile();
        void helpers.loadLatestOperationalResults();
        void helpers.loadRulesHealth();

        const firstViewerTarget = selected[0] || String(((state.sessionInputSources[0] || {}).value) || "");
        if (firstViewerTarget) {
            void helpers.loadCodeViewer(firstViewerTarget).catch(() => {});
        }
    }

    async function sleepMs(ms) {
        await new Promise((resolve) => setTimeout(resolve, ms));
    }

    function bindAnalyzeButton() {
        if (!btnAnalyze) return;
        btnAnalyze.onclick = async () => {
            const originalText = btnAnalyze ? btnAnalyze.textContent : "";
            try {
                const allowRawTxt = false;
                const enableCtrlppcheck = !!(ctrlppToggle && ctrlppToggle.checked);
                const enableLiveAi = !!(liveAiToggle && liveAiToggle.checked);
                const aiWithContext = enableLiveAi && !!(aiContextToggle && aiContextToggle.checked);
                const selected_files = helpers.workspaceGetSelectedFiles();
                const input_sources = helpers.workspaceGetSelectedInputSources();
                const ai_model_name = enableLiveAi ? (state.selectedAiModel || (aiModelSelect && aiModelSelect.value) || "") : "";
                const totalRequestedCount = selected_files.length + input_sources.length;
                if (typeof window !== "undefined") {
                    window.__lastRendererError = null;
                }
                helpers.updateRendererDiagnostics({
                    analyze_status: "queued",
                    analyze_error: "",
                    selected_file_count: selected_files.length,
                    selected_input_source_count: input_sources.length,
                    result_row_count: 0,
                });

                if (btnAnalyze) {
                    btnAnalyze.disabled = true;
                    btnAnalyze.textContent = "Analyzing...";
                }
                setAnalyzeProgressVisible(true);
                updateAnalyzeProgressUi({
                    status: "queued",
                    progress: {
                        total_files: totalRequestedCount,
                        completed_files: 0,
                        failed_files: 0,
                        percent: 0,
                        current_file: "",
                        phase: "queued",
                    },
                    timing: { elapsed_ms: 0, eta_ms: null },
                });

                const response = await fetch("/api/analyze/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        mode: "AI Review",
                        selected_files,
                        input_sources,
                        allow_raw_txt: allowRawTxt,
                        enable_ctrlppcheck: enableCtrlppcheck,
                        enable_live_ai: enableLiveAi,
                        ai_model_name: ai_model_name || undefined,
                        ai_with_context: aiWithContext,
                        defer_excel_reports: true,
                    }),
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || "Analyze request failed");
                }
                helpers.updateRendererDiagnostics({
                    analyze_status: "accepted",
                    analyze_job_id: String(payload.job_id || ""),
                    analyze_poll_interval_ms: Math.max(200, Number(payload.poll_interval_ms) || 500),
                });

                const jobId = String(payload.job_id || "");
                if (!jobId) {
                    throw new Error("Analyze job id is missing from the response.");
                }
                const pollIntervalMs = Math.max(200, Number(payload.poll_interval_ms) || 500);

                for (;;) {
                    const statusResp = await fetch(`/api/analyze/status?job_id=${encodeURIComponent(jobId)}`);
                    const statusPayload = await statusResp.json();
                    if (!statusResp.ok) {
                        throw new Error(statusPayload.error || `Analyze status poll failed (${statusResp.status})`);
                    }
                    updateAnalyzeProgressUi(statusPayload);
                    const status = String(statusPayload.status || "");
                    helpers.updateRendererDiagnostics({
                        analyze_status: status || "running",
                        last_analyze_progress: statusPayload.progress || {},
                        last_analyze_poll: {
                            status,
                            request_id: String(statusPayload.request_id || ""),
                        },
                    });
                    if (status === "completed") {
                        await applyAnalyzePayload(statusPayload.result || {});
                        break;
                    }
                    if (status === "failed") {
                        throw new Error(String(statusPayload.error || "Analyze job failed"));
                    }
                    await sleepMs(pollIntervalMs);
                }
            } catch (err) {
                helpers.recordRendererError(err);
                helpers.updateRendererDiagnostics({
                    analyze_status: "failed",
                    analyze_error: (err && err.message) || String(err),
                });
                alert(`Analysis failed: ${(err && err.message) || String(err)}`);
            } finally {
                setAnalyzeProgressVisible(false);
                helpers.updateRendererDiagnostics({
                    progress_panel_visible: false,
                    result_row_count: Array.isArray(state.workspaceFilteredRows) ? state.workspaceFilteredRows.length : 0,
                });
                if (btnAnalyze) {
                    btnAnalyze.disabled = false;
                    btnAnalyze.textContent = originalText || "Start Analysis";
                }
            }
        };
    }

    return {
        applyAnalyzePayload,
        bindAnalyzeButton,
        setAnalyzeProgressVisible,
        updateAnalyzeProgressUi,
    };
}
