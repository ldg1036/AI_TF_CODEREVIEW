import {
    basenamePath,
    positiveLineOrZero,
    violationCanonicalFileId,
    violationDisplayFile,
    violationResolvedFile,
} from "../utils.js";
import { buildReviewedP1SyncPlan } from "../reviewed-linking.js";
import {
    applyP1TriageToRow,
    excludeSuppressedP1Rows,
} from "../p1-triage.js";
import { deriveAnalysisInsights } from "./recommendations.js";

export function rebuildWorkspaceRowIndex({ state, caches, helpers, runWorkspaceSelection }) {
    const nextRows = [];
    const violations = (state.analysisData && state.analysisData.violations) || {};
    const p1Groups = Array.isArray(violations.P1) ? violations.P1 : [];
    const p2List = Array.isArray(violations.P2) ? violations.P2 : [];
    const p1Rows = [];

    const pushP1Row = (baseViolation, eventName, syncState, originLabel, matchedItems = [], overrideMessage = "", syncReason = "") => {
        const lines = matchedItems.map((item) => positiveLineOrZero(item.violation && item.violation.line)).filter((line) => line > 0);
        const baseLines = Array.isArray(baseViolation._duplicate_lines) ? baseViolation._duplicate_lines : [];
        const uniqueLines = Array.from(new Set(lines.concat(baseLines).map((line) => positiveLineOrZero(line)).filter((line) => line > 0))).sort((a, b) => a - b);
        const primaryLine = positiveLineOrZero(baseViolation._primary_line || baseViolation.line) || uniqueLines[0] || 0;
        const canonicalRuleId = String(baseViolation.rule_id || "").trim();
        const groupedRules = canonicalRuleId ? [canonicalRuleId] : [];
        matchedItems
            .map((item) => String(item.violation && item.violation.rule_id || "").trim())
            .filter(Boolean)
            .forEach((ruleId) => {
                if (!groupedRules.includes(ruleId)) groupedRules.push(ruleId);
            });
        const baseGroupedRules = Array.isArray(baseViolation._group_rule_ids) ? baseViolation._group_rule_ids : [];
        baseGroupedRules
            .map((value) => String(value || "").trim())
            .filter(Boolean)
            .forEach((ruleId) => {
                if (!groupedRules.includes(ruleId)) groupedRules.push(ruleId);
            });
        const groupedMessages = Array.from(new Set(matchedItems.map((item) => String(item.violation && item.violation.message || "").trim()).filter(Boolean)));
        const baseGroupedMessages = Array.isArray(baseViolation._group_messages) ? baseViolation._group_messages : [];
        groupedMessages.push(...baseGroupedMessages.map((value) => String(value || "").trim()).filter(Boolean));
        if (!groupedMessages.length && overrideMessage) groupedMessages.push(overrideMessage);
        if (!groupedMessages.length && baseViolation.message) groupedMessages.push(String(baseViolation.message));
        const groupedIssues = Array.from(new Set(matchedItems.map((item) => String(item.violation && item.violation.issue_id || "").trim()).filter(Boolean)));
        const baseGroupedIssues = Array.isArray(baseViolation._group_issue_ids) ? baseViolation._group_issue_ids : [];
        groupedIssues.push(...baseGroupedIssues.map((value) => String(value || "").trim()).filter(Boolean));
        if (!groupedIssues.length && baseViolation.issue_id) groupedIssues.push(String(baseViolation.issue_id));
        const duplicateCountFromBase = Number.parseInt(baseViolation._duplicate_count, 10);
        const duplicateCount = Number.isFinite(duplicateCountFromBase) && duplicateCountFromBase > 0 ? duplicateCountFromBase : Math.max(1, matchedItems.length || 1);
        const canonicalSeverity = String(baseViolation.severity || "Info");

        const enriched = {
            ...baseViolation,
            priority_origin: "P1",
            line: primaryLine || baseViolation.line || 0,
            rule_id: canonicalRuleId || baseViolation.rule_id || "",
            severity: canonicalSeverity,
            _duplicate_count: duplicateCount,
            _duplicate_lines: uniqueLines,
            _primary_line: primaryLine,
            _grouping_mode: String(baseViolation._grouping_mode || "reviewed_block"),
            _group_rule_ids: Array.from(new Set(groupedRules)),
            _group_messages: Array.from(new Set(groupedMessages)),
            _group_issue_ids: Array.from(new Set(groupedIssues)),
            _sync_state: syncState,
            _sync_origin: originLabel,
            _sync_reason: syncReason || "",
        };
        const jumpReadyViolation = helpers.applyPrecomputedJumpTarget(enriched, "reviewed");
        const rowMessage = String(baseViolation.message || overrideMessage || "");
        const canonicalFileId = violationCanonicalFileId(jumpReadyViolation, baseViolation.file || baseViolation.object || "");
        const rowRuleId = String(jumpReadyViolation.rule_id || canonicalRuleId || groupedRules[0] || "").trim();
        const rowLine = primaryLine || baseViolation.line || 0;
        p1Rows.push(applyP1TriageToRow({
            rowId: `p1:${canonicalFileId || "global"}:${rowRuleId || "UNKNOWN"}:${rowLine || 0}:${jumpReadyViolation.issue_id || rowMessage}`,
            source: "P1",
            object: violationDisplayFile(baseViolation, "Global") || "Global",
            severity: canonicalSeverity,
            message: rowMessage,
            file: violationResolvedFile(baseViolation),
            line: rowLine,
            issueId: jumpReadyViolation.issue_id || "",
            canonicalFileId,
            duplicateCount,
            ruleId: rowRuleId,
            rule_id: rowRuleId,
            ruleIds: Array.from(new Set(groupedRules)),
            onClick: async (selectionToken) => {
                await runWorkspaceSelection(jumpReadyViolation, eventName || "Global", selectionToken);
            },
        }, state.p1TriageByKey));
    };

    const {
        rowPlans,
        leftoverCount: violationOnlyCount,
        syncedCount,
        reviewOnlyCount,
        mappingDiagnostics,
    } = buildReviewedP1SyncPlan({
        p1Groups,
        reviewedTodoCacheByFile: caches.reviewedTodoCacheByFile,
        pickHigherSeverity: helpers.pickHigherSeverity,
    });

    rowPlans.forEach((plan) => {
        pushP1Row(
            plan.baseViolation,
            plan.eventName,
            plan.syncState,
            plan.originLabel,
            plan.matchedItems,
            plan.overrideMessage,
            plan.syncReason,
        );
    });

    if (p1Rows.length > 0) {
        console.debug("[P1 sync]", {
            synced_count: syncedCount,
            review_only_count: reviewOnlyCount,
            violation_only_count: violationOnlyCount,
            rows: p1Rows.length,
        });
        console.debug("[P1 mapping diagnostics]", mappingDiagnostics);
    }
    nextRows.push(...p1Rows);

    p2List.forEach((v) => {
        const objectName = String(v.object || "Global");
        const fileFromPayload = violationDisplayFile(v);
        const fileFromObject = /\.ctl$/i.test(objectName) ? basenamePath(objectName) : "";
        const fileHint = fileFromPayload || fileFromObject;
        const displayObject = fileHint || objectName || "Global";
        const p2Violation = {
            ...v,
            object: displayObject,
            file: String(v.file_path || v.file || fileHint || ""),
            file_path: String(v.file_path || v.file || fileHint || ""),
            priority_origin: v.priority_origin || "P2",
            issue_id: String(v.issue_id || `P2::${fileHint || displayObject}:${String(v.rule_id || "")}:${positiveLineOrZero(v.line)}`),
        };
        const jumpReadyP2Violation = helpers.applyPrecomputedJumpTarget(p2Violation, "source");
        const p2Localized = helpers.buildP2LocalizedMessage(p2Violation);
        nextRows.push({
            rowId: `p2:${jumpReadyP2Violation.issue_id || `${jumpReadyP2Violation.object || "global"}:${jumpReadyP2Violation.line || 0}:${p2Localized.shortText}`}`,
            source: jumpReadyP2Violation.priority_origin || "P2",
            object: jumpReadyP2Violation.object || "Global",
            severity: jumpReadyP2Violation.severity || jumpReadyP2Violation.type || "Info",
            message: p2Localized.shortText,
            file: String(jumpReadyP2Violation.file_path || jumpReadyP2Violation.file || ""),
            line: positiveLineOrZero(jumpReadyP2Violation.line),
            issueId: jumpReadyP2Violation.issue_id || "",
            canonicalFileId: violationCanonicalFileId(jumpReadyP2Violation, fileHint || displayObject),
            duplicateCount: 1,
            ruleIds: [String(jumpReadyP2Violation.rule_id || "").trim()].filter(Boolean),
            onClick: async (selectionToken) => {
                await runWorkspaceSelection(jumpReadyP2Violation, "Global", selectionToken);
            },
        });
    });

    state.workspaceRowIndex = nextRows;
    state.analysisInsights = deriveAnalysisInsights(excludeSuppressedP1Rows(nextRows), helpers);
}
