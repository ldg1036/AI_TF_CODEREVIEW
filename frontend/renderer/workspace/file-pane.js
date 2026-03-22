import {
    buildWorkspaceFileListEmptyMessage,
    filterWorkspaceFilesByQuery,
    getWorkspaceFileName,
} from "../workspace-search-helpers.js";

export function createWorkspaceFilePaneController({
    dom,
    state,
    helpers,
    applyWorkspaceCodePaneHeight,
    renderWorkspaceCommandBar,
    renderWorkspaceFilterSummary,
}) {
    function getSelectedFiles() {
        const selectedSet = state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : new Set();
        return (Array.isArray(state.workspaceAvailableFiles) ? state.workspaceAvailableFiles : [])
            .map((fileLike) => getWorkspaceFileName(fileLike))
            .filter((fileName) => selectedSet.has(fileName));
    }

    function getSelectedInputSources() {
        return state.sessionInputSources.map((item) => ({
            type: String(item.type || ""),
            value: String(item.value || ""),
        }));
    }

    function syncWorkspaceFileSelection(files = []) {
        const safeFiles = Array.isArray(files) ? files : [];
        const previousFiles = Array.isArray(state.workspaceAvailableFiles) ? state.workspaceAvailableFiles : [];
        const previousSelection = state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : new Set();
        const allFileNames = safeFiles
            .map((fileLike) => getWorkspaceFileName(fileLike))
            .filter(Boolean);
        const availableSet = new Set(allFileNames);
        const preservedSelection = new Set(
            Array.from(previousSelection)
                .filter((fileName) => availableSet.has(fileName)),
        );
        const shouldPreserveExplicitEmpty = previousFiles.length > 0 && previousSelection.size === 0;
        if (!preservedSelection.size && !shouldPreserveExplicitEmpty) {
            allFileNames.forEach((fileName) => preservedSelection.add(fileName));
        }
        state.workspaceAvailableFiles = safeFiles;
        state.workspaceSelectedFiles = preservedSelection;
    }

    function getVisibleWorkspaceFiles() {
        return filterWorkspaceFilesByQuery(state.workspaceAvailableFiles, state.workspaceFileQuery);
    }

    function renderFileList(files, options = {}) {
        applyWorkspaceCodePaneHeight();
        if (!dom.fileList) return;
        dom.fileList.replaceChildren();
        const safeFiles = Array.isArray(files) ? files : [];
        syncWorkspaceFileSelection(safeFiles);
        const visibleFiles = getVisibleWorkspaceFiles();
        const emptyMessage = buildWorkspaceFileListEmptyMessage({
            totalFileCount: safeFiles.length,
            fileQuery: state.workspaceFileQuery,
            fallbackMessage: String((options && options.emptyMessage) || "").trim(),
        });

        const selectAllWrap = document.createElement("div");
        selectAllWrap.className = "sidebar-select-all";
        const chkAll = document.createElement("input");
        chkAll.type = "checkbox";
        chkAll.id = "chk-all";
        chkAll.checked = visibleFiles.length > 0 && visibleFiles.every((fileLike) => state.workspaceSelectedFiles.has(getWorkspaceFileName(fileLike)));
        chkAll.indeterminate = visibleFiles.length > 0 && !chkAll.checked && visibleFiles.some((fileLike) => state.workspaceSelectedFiles.has(getWorkspaceFileName(fileLike)));
        const chkAllLabel = document.createElement("strong");
        chkAllLabel.textContent = "현재 표시 파일 전체 선택";
        selectAllWrap.append(chkAll, " ", chkAllLabel);
        dom.fileList.appendChild(selectAllWrap);

        visibleFiles.forEach((file) => {
            const fileName = getWorkspaceFileName(file);
            const row = document.createElement("div");
            row.className = "file-item";
            row.style.cursor = "pointer";
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = state.workspaceSelectedFiles.has(fileName);
            cb.setAttribute("data-file", fileName);
            cb.addEventListener("click", (event) => event.stopPropagation());
            cb.addEventListener("change", () => {
                const nextSelection = new Set(state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : []);
                if (cb.checked) nextSelection.add(fileName);
                else nextSelection.delete(fileName);
                state.workspaceSelectedFiles = nextSelection;
                renderWorkspaceCommandBar();
            });
            const label = document.createElement("span");
            label.className = "file-item-label";
            label.textContent = fileName;
            row.append(cb, label);
            row.addEventListener("click", () => {
                void helpers.loadCodeViewer(fileName).catch(() => {});
            });
            dom.fileList.appendChild(row);
        });

        if (!visibleFiles.length) {
            const empty = document.createElement("div");
            empty.className = "file-item file-item-empty";
            empty.textContent = emptyMessage;
            dom.fileList.appendChild(empty);
        }

        chkAll.addEventListener("change", () => {
            const checked = chkAll.checked;
            const nextSelection = new Set(state.workspaceSelectedFiles instanceof Set ? state.workspaceSelectedFiles : []);
            visibleFiles.forEach((fileLike) => {
                const fileName = getWorkspaceFileName(fileLike);
                if (!fileName) return;
                if (checked) nextSelection.add(fileName);
                else nextSelection.delete(fileName);
            });
            state.workspaceSelectedFiles = nextSelection;
            dom.fileList.querySelectorAll("input[type='checkbox'][data-file]").forEach((cb) => {
                cb.checked = checked;
            });
            renderWorkspaceCommandBar();
        });

        if (typeof helpers.updateRendererDiagnostics === "function") {
            helpers.updateRendererDiagnostics({
                file_list_status: safeFiles.length ? "ready" : "empty",
                file_list_dom_count: visibleFiles.length,
                file_list_empty_message: emptyMessage,
                file_list_query: String(state.workspaceFileQuery || ""),
            });
        }
        renderWorkspaceCommandBar();
    }

    async function loadFiles() {
        applyWorkspaceCodePaneHeight();
        const response = await fetch("/api/files");
        if (!response.ok) {
            state.workspaceAvailableFiles = [];
            state.workspaceSelectedFiles = new Set();
            renderFileList([], { emptyMessage: `파일 목록을 불러오지 못했습니다. (${response.status})` });
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    file_list_status: "http_error",
                    file_list_http_status: response.status,
                });
            }
            throw new Error(`파일 목록을 불러오지 못했습니다. (${response.status})`);
        }
        const payload = await response.json();
        if (!payload || !Array.isArray(payload.files)) {
            state.workspaceAvailableFiles = [];
            state.workspaceSelectedFiles = new Set();
            renderFileList([], { emptyMessage: "파일 목록 응답 형식이 올바르지 않습니다." });
            if (typeof helpers.updateRendererDiagnostics === "function") {
                helpers.updateRendererDiagnostics({
                    file_list_status: "invalid_payload",
                    file_list_http_status: response.status,
                    file_list_payload_keys: payload && typeof payload === "object" ? Object.keys(payload) : [],
                });
            }
            return;
        }
        renderFileList(payload.files || []);
        helpers.renderExternalInputSources();
    }

    function setWorkspaceFileQuery(query = "") {
        state.workspaceFileQuery = String(query || "");
        renderFileList(state.workspaceAvailableFiles || []);
        renderWorkspaceFilterSummary();
    }

    return {
        getSelectedFiles,
        getSelectedInputSources,
        loadFiles,
        renderFileList,
        setWorkspaceFileQuery,
    };
}
