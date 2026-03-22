import {
    basenamePath,
    normalizeInsightToken,
    scoreSeverityWeight,
    scoreSourceWeight,
} from "../utils.js";

export function buildRecommendationReason(item, helpers) {
    const reasons = [];
    const duplicateCount = Math.max(0, Number.parseInt(item && item.duplicateCount, 10) || 0);
    const hotspotIssueCount = Math.max(0, Number.parseInt(item && item.hotspotIssueCount, 10) || 0);
    const ruleBreadth = Math.max(0, Number.parseInt(item && item.ruleBreadth, 10) || 0);
    const dominantRuleCount = Math.max(0, Number.parseInt(item && item.dominantRuleCount, 10) || 0);
    const severityKey = helpers.severityFilterKey(item && item.severity);
    const sourceKey = helpers.sourceFilterKey(item && item.source);
    if (severityKey === "critical") reasons.push("치명 등급이라 우선 검토가 필요합니다.");
    else if (severityKey === "warning") reasons.push("경고 등급이라 빠른 확인이 필요합니다.");
    if (duplicateCount >= 4) reasons.push(`중복 영향 ${duplicateCount}건이 묶여 있습니다.`);
    if (hotspotIssueCount >= 3) reasons.push(`${String(item && item.hotspotObject || item && item.target || "Global")} 구간에 ${hotspotIssueCount}건이 집중되어 있습니다.`);
    if (dominantRuleCount >= 2) reasons.push(`${String(item && item.dominantRuleFamily || "RULE")} 규칙이 ${dominantRuleCount}회 반복됩니다.`);
    if (ruleBreadth >= 3) reasons.push(`연관 규칙군이 ${ruleBreadth}개라 교차 점검이 필요합니다.`);
    if (sourceKey === "p1") reasons.push("정적 규칙 우선 검토 대상입니다.");
    else if (sourceKey === "p2") reasons.push("Ctrlpp 정적 분석 결과를 함께 확인해야 합니다.");
    else if (sourceKey === "p3") reasons.push("AI 후속 검토가 권장됩니다.");
    return reasons.slice(0, 3).join(" | ") || "집중도와 심각도가 높아 우선 검토 대상으로 적합합니다.";
}

export function deriveAnalysisInsights(rows, helpers) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const dedupe = { rawIssueCount: 0, displayedRowCount: safeRows.length, collapsedDuplicateCount: 0 };
    const grouped = new Map();
    safeRows.forEach((row, index) => {
        const duplicateCount = Math.max(1, Number.parseInt(row && row.duplicateCount, 10) || 1);
        dedupe.rawIssueCount += duplicateCount;
        dedupe.collapsedDuplicateCount += Math.max(0, duplicateCount - 1);
        const source = String((row && row.source) || "P1");
        const target = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
        const key = `${source}||${target}`;
        if (!grouped.has(key)) {
            grouped.set(key, {
                source,
                target,
                severity: row && row.severity || "Info",
                rowCount: 0,
                duplicateCount: 0,
                messages: [],
                firstIndex: index,
                representativeRow: row || null,
                objectCounts: new Map(),
                objectLabels: new Map(),
                ruleFamilyCounts: new Map(),
                uniqueRuleIds: new Set(),
                severityTotal: 0,
                sourceTotal: 0,
                duplicateBonusTotal: 0,
            });
        }
        const current = grouped.get(key);
        current.rowCount += 1;
        current.duplicateCount += duplicateCount;
        current.severity = helpers.pickHigherSeverity(current.severity, row && row.severity || "Info");
        current.severityTotal += scoreSeverityWeight(row && row.severity);
        current.sourceTotal += scoreSourceWeight(source);
        current.duplicateBonusTotal += Math.min(6, duplicateCount - 1);
        if (!current.representativeRow || scoreSeverityWeight(row && row.severity) >= scoreSeverityWeight(current.representativeRow && current.representativeRow.severity)) {
            current.representativeRow = row || current.representativeRow;
        }
        const message = String((row && row.message) || "").trim();
        if (message && current.messages.length < 3) current.messages.push(message);
        const hotspotObject = basenamePath((row && row.object) || "") || String((row && row.object) || target || "Global");
        const objectKey = normalizeInsightToken(hotspotObject);
        current.objectCounts.set(objectKey, (current.objectCounts.get(objectKey) || 0) + duplicateCount);
        if (!current.objectLabels.has(objectKey)) current.objectLabels.set(objectKey, hotspotObject);
        (Array.isArray(row && row.ruleIds) ? row.ruleIds : []).forEach((ruleId) => {
            const normalizedRuleId = String(ruleId || "").trim();
            if (!normalizedRuleId) return;
            current.uniqueRuleIds.add(normalizedRuleId);
            const family = normalizeInsightToken(normalizedRuleId.split("-")[0] || normalizedRuleId, "unknown");
            current.ruleFamilyCounts.set(family, (current.ruleFamilyCounts.get(family) || 0) + 1);
        });
    });
    const recommendations = Array.from(grouped.values())
        .map((item) => {
            let hotspotObject = item.target;
            let hotspotIssueCount = 0;
            item.objectCounts.forEach((count, objectKey) => {
                if (count > hotspotIssueCount) {
                    hotspotIssueCount = count;
                    hotspotObject = item.objectLabels.get(objectKey) || objectKey;
                }
            });
            let dominantRuleFamily = "unknown";
            let dominantRuleCount = 0;
            item.ruleFamilyCounts.forEach((count, family) => {
                if (count > dominantRuleCount) {
                    dominantRuleCount = count;
                    dominantRuleFamily = family;
                }
            });
            const score = item.severityTotal + item.sourceTotal + item.duplicateBonusTotal + Math.min(6, Math.max(0, hotspotIssueCount - 1)) + Math.min(4, item.uniqueRuleIds.size) + Math.min(5, Math.max(0, dominantRuleCount - 1));
            return {
                ...item,
                score,
                hotspotObject,
                hotspotIssueCount,
                ruleBreadth: item.uniqueRuleIds.size,
                dominantRuleFamily: dominantRuleFamily.toUpperCase(),
                dominantRuleCount,
            };
        })
        .sort((a, b) => (b.score - a.score) || (b.duplicateCount - a.duplicateCount) || (b.rowCount - a.rowCount) || (a.firstIndex - b.firstIndex))
        .slice(0, 5)
        .map((item) => ({ ...item, leadMessage: item.messages[0] || "", reason: buildRecommendationReason(item, helpers) }));
    return { dedupe, recommendations };
}

export function buildRecommendationInsightIndex(insights) {
    const index = new Map();
    (Array.isArray(insights && insights.recommendations) ? insights.recommendations : []).forEach((item) => {
        const rowId = String(item && item.representativeRow && item.representativeRow.rowId || "").trim();
        if (rowId) index.set(rowId, item);
    });
    return index;
}

export function getRowHotspotKey(row) {
    const hotspot = basenamePath((row && (row.file || row.object)) || "") || String((row && row.object) || "Global");
    return normalizeInsightToken(hotspot, "global");
}

export function getRowRuleFamilies(row) {
    const ruleIds = Array.isArray(row && row.ruleIds) ? row.ruleIds : [];
    return Array.from(new Set(
        ruleIds
            .map((ruleId) => normalizeInsightToken(String(ruleId || "").split("-")[0] || ruleId, "unknown"))
            .filter(Boolean),
    ));
}
