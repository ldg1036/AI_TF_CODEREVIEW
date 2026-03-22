export function createExcelJobsController({
    elements,
    state,
}) {
    const {
        excelDownloadList,
        excelDownloadPanel,
        excelDownloadToggle,
        excelJobStatusText,
        flushExcelBtn,
    } = elements;

    function setExcelJobStatus(message, color = "") {
        if (!excelJobStatusText) return;
        excelJobStatusText.textContent = String(message || "");
        if (color) {
            excelJobStatusText.style.color = color;
        } else {
            excelJobStatusText.style.color = "rgba(255,255,255,0.92)";
        }
    }

    function excelJobsFromAnalysis() {
        const reportJobs = (state.analysisData && state.analysisData.report_jobs) || {};
        const excel = (reportJobs && reportJobs.excel) || {};
        return excel;
    }

    function excelFilesFromAnalysis() {
        const reportPaths = (state.analysisData && state.analysisData.report_paths) || {};
        return Array.isArray(reportPaths.excel) ? reportPaths.excel.filter(Boolean).map((name) => String(name)) : [];
    }

    function isExcelSupportAvailable() {
        const metrics = (state.analysisData && state.analysisData.metrics) || {};
        const optionalDependencies = (metrics && metrics.optional_dependencies) || {};
        const openpyxl = (optionalDependencies && optionalDependencies.openpyxl) || {};
        return openpyxl.available !== false;
    }

    function makeExcelDownloadUrl(name) {
        const outputDir = String((state.analysisData && state.analysisData.output_dir) || "").trim();
        const fileName = String(name || "").trim();
        if (!outputDir || !fileName) return "";
        const query = new URLSearchParams();
        query.set("output_dir", outputDir);
        query.set("name", fileName);
        return `/api/report/excel/download?${query.toString()}`;
    }

    function triggerExcelDownload(name) {
        const url = makeExcelDownloadUrl(name);
        if (!url) return;
        const link = document.createElement("a");
        link.href = url;
        link.download = String(name || "report.xlsx");
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function shortenExcelDownloadName(name, maxLength = 48) {
        const raw = String(name || "report.xlsx").trim();
        const compact = raw.replace(/^CodeReview_Submission_/, "");
        if (compact.length <= maxLength) {
            return compact;
        }
        const head = Math.max(18, Math.floor((maxLength - 1) / 2));
        const tail = Math.max(12, maxLength - head - 1);
        return `${compact.slice(0, head)}...${compact.slice(-tail)}`;
    }

    function setExcelDownloadsExpanded(expanded) {
        state.excelDownloadsExpanded = !!expanded;
        if (excelDownloadToggle) {
            excelDownloadToggle.setAttribute("aria-expanded", state.excelDownloadsExpanded ? "true" : "false");
        }
        if (excelDownloadPanel) {
            const hasFiles = !!excelFilesFromAnalysis().length;
            excelDownloadPanel.hidden = !hasFiles || !state.excelDownloadsExpanded;
        }
    }

    function renderExcelDownloadList() {
        if (!excelDownloadList) return;
        excelDownloadList.innerHTML = "";
        if (!((state.analysisData && state.analysisData.output_dir) || "").trim()) {
            if (excelDownloadToggle) {
                excelDownloadToggle.hidden = true;
            }
            setExcelDownloadsExpanded(false);
            return;
        }
        const files = excelFilesFromAnalysis();
        if (!files.length) {
            if (excelDownloadToggle) {
                excelDownloadToggle.hidden = true;
            }
            setExcelDownloadsExpanded(false);
            return;
        }
        if (excelDownloadToggle) {
            excelDownloadToggle.hidden = false;
            excelDownloadToggle.textContent = `Excel ${files.length}`;
            excelDownloadToggle.title = `${files.length} Excel files ready to download`;
        }
        files.forEach((name) => {
            const item = document.createElement("div");
            item.className = "excel-download-item";
            item.title = String(name || "");
            const label = document.createElement("span");
            label.className = "excel-download-name";
            label.textContent = shortenExcelDownloadName(name);
            const button = document.createElement("button");
            button.type = "button";
            button.className = "excel-download-button";
            button.textContent = "Download";
            button.title = String(name || "");
            button.addEventListener("click", () => triggerExcelDownload(name));
            item.appendChild(label);
            item.appendChild(button);
            excelDownloadList.appendChild(item);
        });
        setExcelDownloadsExpanded(state.excelDownloadsExpanded);
    }

    function updateExcelJobUiFromAnalysis() {
        const excel = excelJobsFromAnalysis();
        const excelFiles = excelFilesFromAnalysis();
        const excelAvailable = isExcelSupportAvailable();
        const pending = Number.parseInt(excel.pending_count || 0, 10) || 0;
        const running = Number.parseInt(excel.running_count || 0, 10) || 0;
        const completed = Number.parseInt(excel.completed_count || 0, 10) || 0;
        const failed = Number.parseInt(excel.failed_count || 0, 10) || 0;
        const total = (Array.isArray(excel.jobs) ? excel.jobs.length : 0);
        const hasSession = !!(state.analysisData && state.analysisData.output_dir);
        if (flushExcelBtn) {
            flushExcelBtn.disabled = !hasSession || !excelAvailable || (total === 0 && excelFiles.length === 0);
            flushExcelBtn.textContent = (pending > 0 || running > 0) ? "Flush Excel queue" : "Flush Excel queue";
        }
        if (!hasSession) {
            setExcelJobStatus("");
            renderExcelDownloadList();
            return;
        }
        if (!excelAvailable) {
            setExcelJobStatus("openpyxl unavailable", "#ffcdd2");
            renderExcelDownloadList();
            return;
        }
        if (total === 0 && excelFiles.length === 0) {
            setExcelJobStatus("", "");
            renderExcelDownloadList();
            return;
        }
        if (excelFiles.length > 0 && pending === 0 && running === 0 && failed === 0) {
            setExcelJobStatus(`Excel ${excelFiles.length} files ready`, "#c8e6c9");
            renderExcelDownloadList();
            return;
        }
        const statusParts = [`Excel ${completed}/${total}`];
        if (pending > 0) statusParts.push(`pending ${pending}`);
        if (running > 0) statusParts.push(`running ${running}`);
        if (failed > 0) statusParts.push(`failed ${failed}`);
        const color = failed > 0 ? "#ffcdd2" : (pending > 0 || running > 0) ? "#fff59d" : "#c8e6c9";
        setExcelJobStatus(statusParts.join(" | "), color);
        renderExcelDownloadList();
    }

    async function flushExcelReports(options = {}) {
        const wait = !(options && options.wait === false);
        const timeoutSec = Number.isFinite(Number(options && options.timeout_sec)) ? Number(options.timeout_sec) : undefined;
        const response = await fetch("/api/report/excel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: state.analysisData.output_dir || undefined,
                wait,
                timeout_sec: Number.isFinite(timeoutSec) ? timeoutSec : undefined,
            }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.error || `excel report flush failed (${response.status})`);
        }
        return payload;
    }

    async function handleFlushExcelReportsClick() {
        if (!state.analysisData.output_dir) return;
        if (flushExcelBtn) {
            flushExcelBtn.disabled = true;
            flushExcelBtn.textContent = "Flushing Excel...";
        }
        setExcelDownloadsExpanded(false);
        setExcelJobStatus("Excel flush is running. Please wait...", "#fff59d");
        try {
            const payload = await flushExcelReports({ wait: true, timeout_sec: 120 });
            state.analysisData = {
                ...state.analysisData,
                report_jobs: payload.report_jobs || {},
                report_paths: payload.report_paths || state.analysisData.report_paths || {},
                output_dir: payload.output_dir || state.analysisData.output_dir || "",
            };
            if (Array.isArray((payload.report_paths || {}).excel) && payload.report_paths.excel.length) {
                setExcelDownloadsExpanded(true);
            }
            updateExcelJobUiFromAnalysis();
        } catch (err) {
            const msg = String((err && err.message) || err || "Excel flush failed");
            setExcelJobStatus(`Excel flush failed: ${msg}`, "#ffcdd2");
            alert(`Excel flush failed: ${msg}`);
        } finally {
            updateExcelJobUiFromAnalysis();
        }
    }

    return {
        excelFilesFromAnalysis,
        excelJobsFromAnalysis,
        flushExcelReports,
        handleFlushExcelReportsClick,
        isExcelSupportAvailable,
        makeExcelDownloadUrl,
        renderExcelDownloadList,
        setExcelDownloadsExpanded,
        setExcelJobStatus,
        triggerExcelDownload,
        updateExcelJobUiFromAnalysis,
    };
}
