import { severityFilterKey, sourceFilterKey } from "./app-state.js";
import { basenamePath } from "./utils.js";

export function normalizeWorkspaceSearchQuery(value = "") {
    return String(value || "").trim().toLowerCase();
}

export function normalizeWorkspaceQuickPreset(value = "all") {
    const normalized = String(value || "all").trim().toLowerCase();
    if (normalized === "p1_only") return "p1_only";
    if (normalized === "attention_only") return "attention_only";
    return "all";
}

export function getWorkspaceFileName(fileLike = {}) {
    return String(
        (fileLike && (fileLike.name || fileLike.label || fileLike.path || fileLike.value))
        || fileLike
        || "",
    ).trim();
}

export function filterWorkspaceFilesByQuery(files = [], query = "") {
    const safeFiles = Array.isArray(files) ? files : [];
    const normalizedQuery = normalizeWorkspaceSearchQuery(query);
    if (!normalizedQuery) return safeFiles;
    return safeFiles.filter((fileLike) => getWorkspaceFileName(fileLike).toLowerCase().includes(normalizedQuery));
}

function buildWorkspaceRowSearchText(row = {}) {
    const ruleIds = Array.isArray(row && row.ruleIds) ? row.ruleIds : [];
    return [
        row && row.source,
        row && row.severity,
        row && row.object,
        basenamePath(row && row.file),
        row && row.file,
        row && row.message,
        row && row.ruleId,
        row && row.rule_id,
        row && row.messageSearchToken,
        ruleIds.join(" "),
    ]
        .map((value) => String(value || "").trim())
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
}

export function rowMatchesWorkspaceResultQuery(row = {}, query = "") {
    const normalizedQuery = normalizeWorkspaceSearchQuery(query);
    if (!normalizedQuery) return true;
    return buildWorkspaceRowSearchText(row).includes(normalizedQuery);
}

export function rowMatchesWorkspaceQuickPreset(row = {}, preset = "all") {
    const normalizedPreset = normalizeWorkspaceQuickPreset(preset);
    if (normalizedPreset === "p1_only") {
        return sourceFilterKey(row && row.source) === "p1";
    }
    if (normalizedPreset === "attention_only") {
        const severityKey = severityFilterKey(row && row.severity);
        return severityKey === "critical" || severityKey === "warning";
    }
    return true;
}

export function buildWorkspaceSearchStateLabel({
    fileQuery = "",
    resultQuery = "",
    quickPreset = "all",
} = {}) {
    const labels = [];
    const normalizedPreset = normalizeWorkspaceQuickPreset(quickPreset);
    const normalizedFileQuery = normalizeWorkspaceSearchQuery(fileQuery);
    const normalizedResultQuery = normalizeWorkspaceSearchQuery(resultQuery);

    if (normalizedPreset === "p1_only") labels.push("빠른 보기: P1만");
    else if (normalizedPreset === "attention_only") labels.push("빠른 보기: 치명/경고");

    if (normalizedFileQuery) labels.push(`파일 검색: "${fileQuery}"`);
    if (normalizedResultQuery) labels.push(`결과 검색: "${resultQuery}"`);

    return labels.join(" | ");
}

export function buildWorkspaceFileListEmptyMessage({
    totalFileCount = 0,
    fileQuery = "",
    fallbackMessage = "",
} = {}) {
    const normalizedQuery = normalizeWorkspaceSearchQuery(fileQuery);
    if (fallbackMessage) return String(fallbackMessage);
    if (totalFileCount <= 0) {
        return "선택 가능한 파일이 아직 없습니다.";
    }
    if (normalizedQuery) {
        return `파일 검색과 일치하는 항목이 없습니다. "${fileQuery}" 검색을 조정해 보세요.`;
    }
    return "선택 가능한 파일이 없습니다.";
}
