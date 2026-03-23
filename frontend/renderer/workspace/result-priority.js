import { severityFilterKey } from "../app-state.js";
import { buildAiCardKey, getActiveAutofixProposal } from "../autofix-ai/bundle-utils.js";
import { getAutofixApplyGate } from "../autofix-ai/quality-gates.js";
import { findAiMatchForViolation } from "../reviewed-linking.js";
import { basenamePath, positiveLineOrZero } from "../utils.js";

const analysisAiIndexCache = new WeakMap();

const GROUP_META = {
    ready: {
        title: "바로 수정 가능한 항목",
        subtitle: "AI 제안이 이미 있거나 바로 비교와 준비가 가능한 항목입니다.",
    },
    review: {
        title: "검토가 필요한 항목",
        subtitle: "우선 원인과 근거를 보고 수동 검토 또는 AI 분석 여부를 결정하는 항목입니다.",
    },
    blocked: {
        title: "차단된 항목",
        subtitle: "준비된 패치가 있지만 안전성 검증 때문에 적용이 막힌 항목입니다.",
    },
};

function defaultAiMeta() {
    return {
        group: "review",
        label: "AI 검토 필요",
        detail: "",
        tone: "review",
        hasAiSuggestion: false,
        canApply: false,
        prepared: false,
    };
}

function classifyAcceptedAi(aiMatch) {
    const statusKey = String((aiMatch && aiMatch.status) || "").trim().toLowerCase();
    if (statusKey !== "accepted") return null;
    return {
        group: "review",
        label: "적용 완료",
        detail: "이미 적용된 AI 제안입니다.",
        tone: "complete",
        hasAiSuggestion: true,
        canApply: false,
        prepared: false,
    };
}

function classifyPreparedProposal(proposal) {
    if (!proposal) return null;
    const gate = getAutofixApplyGate(proposal);
    if (gate.canApply) {
        return {
            group: "ready",
            label: "바로 적용 가능",
            detail: "준비된 source patch를 바로 적용할 수 있습니다.",
            tone: "ready",
            hasAiSuggestion: true,
            canApply: true,
            prepared: gate.prepared,
        };
    }
    return {
        group: "blocked",
        label: "적용 차단",
        detail: gate.blockedReasonDetail || gate.blockedReasonText || gate.blockedReason || "",
        tone: "blocked",
        hasAiSuggestion: true,
        canApply: false,
        prepared: gate.prepared,
    };
}

function getAnalysisAiIndex(analysisData) {
    if (!analysisData || typeof analysisData !== "object") {
        return { byParentIssueId: new Map() };
    }
    if (analysisAiIndexCache.has(analysisData)) {
        return analysisAiIndexCache.get(analysisData);
    }
    const p3Items = Array.isArray(analysisData && analysisData.violations && analysisData.violations.P3)
        ? analysisData.violations.P3
        : [];
    const byParentIssueId = new Map();
    p3Items.forEach((item) => {
        const parentIssueId = String((item && item.parent_issue_id) || "").trim();
        if (parentIssueId && !byParentIssueId.has(parentIssueId)) {
            byParentIssueId.set(parentIssueId, item);
        }
    });
    const index = { byParentIssueId };
    analysisAiIndexCache.set(analysisData, index);
    return index;
}

function isReviewOnlyLikeViolation(violation) {
    const source = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const issueId = String((violation && violation.issue_id) || "").trim().toUpperCase();
    const lineNo = positiveLineOrZero((violation && violation.line) || 0);
    return source === "P1" && (lineNo <= 0 || issueId.startsWith("REVIEW-ONLY-"));
}

export function deriveWorkspaceRowPriorityMeta({ row, analysisData, autofixProposalCache }) {
    const safeRow = row && typeof row === "object" ? row : {};
    const violation = safeRow.violation && typeof safeRow.violation === "object" ? safeRow.violation : null;
    const eventName = String(safeRow.eventName || "Global");
    if (!violation) {
        return defaultAiMeta();
    }

    const violationIssueId = String((violation && violation.issue_id) || "").trim();
    const aiIndex = getAnalysisAiIndex(analysisData);
    const indexedMatch = violationIssueId ? (aiIndex.byParentIssueId.get(violationIssueId) || null) : null;
    const aiMatch = indexedMatch
        || (isReviewOnlyLikeViolation(violation)
            ? findAiMatchForViolation({ analysisData, violation, eventName })
            : null);
    const acceptedMeta = classifyAcceptedAi(aiMatch);
    if (acceptedMeta) return acceptedMeta;

    if (aiMatch) {
        const aiKey = buildAiCardKey(violation, eventName, aiMatch);
        const bundle = autofixProposalCache instanceof Map ? autofixProposalCache.get(aiKey) : null;
        const proposal = getActiveAutofixProposal(bundle);
        const preparedMeta = classifyPreparedProposal(proposal);
        if (preparedMeta) return preparedMeta;
        return {
            group: "ready",
            label: "AI 제안 있음",
            detail: "비교 또는 패치 준비를 시작할 수 있습니다.",
            tone: "ready",
            hasAiSuggestion: true,
            canApply: false,
            prepared: false,
        };
    }

    return defaultAiMeta();
}

function buildLocationLabel(row) {
    const lineNo = positiveLineOrZero(row && row.line);
    const fileLabel = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
    return lineNo > 0 ? `${fileLabel} · line ${lineNo}` : fileLabel;
}

export function buildWorkspacePriorityModel({ rows, analysisData, autofixProposalCache }) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const grouped = { ready: [], review: [], blocked: [] };
    const summary = {
        total: safeRows.length,
        critical: 0,
        warning: 0,
        ready: 0,
        blocked: 0,
        review: 0,
    };

    safeRows.forEach((row) => {
        const severity = severityFilterKey(row && row.severity);
        if (severity === "critical") summary.critical += 1;
        if (severity === "warning") summary.warning += 1;
        const aiMeta = deriveWorkspaceRowPriorityMeta({ row, analysisData, autofixProposalCache });
        summary[aiMeta.group] += 1;
        grouped[aiMeta.group].push({
            ...row,
            aiStatus: aiMeta.label,
            aiStatusDetail: aiMeta.detail,
            aiStatusTone: aiMeta.tone,
            locationLabel: buildLocationLabel(row),
        });
    });

    const groupedRows = [];
    ["ready", "review", "blocked"].forEach((groupKey) => {
        const items = grouped[groupKey];
        if (!items.length) return;
        groupedRows.push({
            rowType: "group",
            groupKey,
            title: GROUP_META[groupKey].title,
            subtitle: GROUP_META[groupKey].subtitle,
            count: items.length,
        });
        groupedRows.push(...items);
    });

    return {
        summary,
        groupedRows,
    };
}
