import { getAutofixApplyGate } from "./quality-gates.js";

export function buildDiffModalMeta({ violation, aiMatch, proposal, helpers }) {
    const entries = [];
    const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(proposal, helpers.violationDisplayFile(violation)));
    const parentSource = String((violation && violation.priority_origin) || "P1").toUpperCase();
    const p3Source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
    const generatorType = String((proposal && proposal.generator_type) || "").trim().toUpperCase();
    const hasProposal = !!(proposal && String(proposal.unified_diff || "").trim());
    const gate = getAutofixApplyGate(proposal);
    if (fileName) entries.push(`파일 ${fileName}`);
    entries.push(`원본 ${parentSource}`);
    if (String((violation && violation.rule_id) || "").trim()) entries.push(`규칙 ${String(violation.rule_id || "").trim()}`);
    if (helpers.positiveLineOrZero((violation && violation.line) || 0) > 0) entries.push(`라인 ${helpers.positiveLineOrZero(violation.line)}`);
    entries.push(p3Source === "mock" ? "P3 모의" : "P3 실시간");
    if (generatorType) entries.push(`후보 ${generatorType}`);
    if (!gate.proposalReady) {
        entries.push("수정안 준비 안 됨");
    } else if (gate.canApply) {
        entries.push("적용 가능");
    } else if (hasProposal) {
        entries.push(`적용 차단: ${gate.blockedReasonText || gate.blockedReason || "apply_blocked"}`);
    } else {
        entries.push("수정안 없음");
    }
    return entries;
}

export function buildCompareSummaryLines({ violation, aiMatch, proposal, helpers }) {
    const lines = [];
    const sourceLabel = helpers.sourceFilterKey((violation && violation.priority_origin) || "P1") === "p2" ? "P2 원문" : "P1 원문";
    const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(violation)) || "선택 파일";
    const p3Source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase() === "mock" ? "모의 P3" : "실시간 P3";
    const gate = getAutofixApplyGate(proposal);
    lines.push(`${sourceLabel}과 ${p3Source}를 비교합니다.`);
    lines.push(`대상 ${fileName} · 규칙 ${String((violation && violation.rule_id) || "-")} · 라인 ${helpers.positiveLineOrZero((violation && violation.line) || 0) || "-"}`);
    lines.push(`이슈 ${helpers.compactUiText(String((violation && violation.message) || "").trim(), 180) || "-"}`);
    if (!gate.proposalReady) {
        lines.push("아직 수정안이 준비되지 않았습니다.");
    } else if (gate.canApply) {
        lines.push("적용 가능합니다.");
    } else {
        lines.push(`적용 차단: ${String(gate.blockedReasonText || gate.blockedReason || "apply_blocked")}`);
    }
    return lines;
}

export function buildDiffModalStatusEntries({ context, aiMatch, proposal }) {
    const entries = [];
    const safeContext = context && typeof context === "object" ? context : {};
    const hasPatch = !!String((proposal && proposal.unified_diff) || "").trim();
    const gate = getAutofixApplyGate(proposal);
    if (!gate.proposalReady) {
        entries.push({
            key: "patch_not_prepared",
            label: "수정안 준비 안 됨",
            title: "적용하려면 먼저 선택한 후보의 수정안을 준비해야 합니다.",
            tone: "muted",
        });
    } else if (gate.canApply) {
        entries.push({
            key: "ready_to_apply",
            label: "적용 가능",
            title: "선택한 후보의 수정안이 준비되었고 적용이 허용됩니다.",
            tone: "ok",
        });
    } else if (gate.blockedReasonText || gate.blockedReason) {
        entries.push({
            key: "apply_blocked",
            label: "적용 차단",
            title: gate.blockedReasonText || gate.blockedReason,
            tone: "warn",
        });
    }
    if (safeContext.lineUnresolved) {
        entries.push({
            key: "line_unresolved",
            label: "라인 확인 필요",
            title: "원문 기준 라인을 정확하게 찾지 못했습니다.",
            tone: "warn",
        });
    }
    if (!hasPatch || safeContext.patchMissing) {
        entries.push({
            key: "patch_not_generated",
            label: "수정안 없음",
            title: "원문 수정 diff가 아직 준비되지 않았습니다.",
            tone: "muted",
        });
    }
    if (safeContext.prepareFailed) {
        entries.push({
            key: "prepare_failed",
            label: "준비 실패",
            title: String(safeContext.errorMessage || "수정안 준비에 실패했습니다."),
            tone: "danger",
        });
    }
    const source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
    if (safeContext.mockOrLowConfidence || source === "mock") {
        entries.push({
            key: "mock_or_low_confidence",
            label: "모의 검토",
            title: "이 비교는 모의 또는 낮은 신뢰도의 검토 결과를 기반으로 합니다.",
            tone: "muted",
        });
    }
    return entries;
}
