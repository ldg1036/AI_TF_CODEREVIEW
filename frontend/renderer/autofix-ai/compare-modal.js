export function buildDiffModalMeta({ violation, aiMatch, proposal, helpers }) {
    const entries = [];
    const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(proposal, helpers.violationDisplayFile(violation)));
    const parentSource = String((violation && violation.priority_origin) || "P1").toUpperCase();
    const p3Source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
    const generatorType = String((proposal && proposal.generator_type) || "").trim().toUpperCase();
    const hasProposal = !!(proposal && String(proposal.unified_diff || "").trim());
    const allowApply = !!(proposal && proposal.can_apply);
    const proposalReady = !!(proposal && (proposal.proposal_ready || proposal.prepared));
    if (fileName) entries.push(`File ${fileName}`);
    entries.push(`Source ${parentSource}`);
    if (String((violation && violation.rule_id) || "").trim()) entries.push(`Rule ${String(violation.rule_id || "").trim()}`);
    if (helpers.positiveLineOrZero((violation && violation.line) || 0) > 0) entries.push(`Line ${helpers.positiveLineOrZero(violation.line)}`);
    entries.push(p3Source === "mock" ? "P3 Mock" : "P3 Live");
    if (generatorType) entries.push(`Proposal ${generatorType}`);
    if (!proposalReady) {
        entries.push("Patch not prepared");
    } else if (allowApply) {
        entries.push("Ready to apply");
    } else if (hasProposal) {
        entries.push("Patch prepared");
    } else {
        entries.push("Patch missing");
    }
    return entries;
}

export function buildCompareSummaryLines({ violation, aiMatch, proposal, helpers }) {
    const lines = [];
    const sourceLabel = helpers.sourceFilterKey((violation && violation.priority_origin) || "P1") === "p2" ? "P2 source" : "P1 source";
    const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(violation)) || "selected file";
    const p3Source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase() === "mock" ? "Mock P3" : "Live P3";
    lines.push(`${sourceLabel} compared with ${p3Source}.`);
    lines.push(`Target ${fileName} ??rule ${String((violation && violation.rule_id) || "-")} ??line ${helpers.positiveLineOrZero((violation && violation.line) || 0) || "-"}`);
    lines.push(`Issue ${helpers.compactUiText(String((violation && violation.message) || "").trim(), 180) || "-"}`);
    if (!proposal || !(proposal.proposal_ready || proposal.prepared)) {
        lines.push("Patch not prepared.");
    } else if (proposal.can_apply) {
        lines.push("Ready to apply.");
    } else {
        lines.push(`Blocked: ${String(proposal.blocked_reason_text || proposal.blocked_reason || "apply_blocked")}`);
    }
    return lines;
}

export function buildDiffModalStatusEntries({ context, aiMatch, proposal }) {
    const entries = [];
    const safeContext = context && typeof context === "object" ? context : {};
    const hasPatch = !!String((proposal && proposal.unified_diff) || "").trim();
    const prepared = !!(proposal && (proposal.proposal_ready || proposal.prepared));
    const allowApply = !!(proposal && proposal.can_apply);
    const blockedReasonText = String((proposal && proposal.blocked_reason_text) || (proposal && proposal.blocked_reason) || "").trim();
    if (!prepared) {
        entries.push({
            key: "patch_not_prepared",
            label: "patch not prepared",
            title: "Prepare the selected candidate before applying it.",
            tone: "muted",
        });
    } else if (allowApply) {
        entries.push({
            key: "ready_to_apply",
            label: "ready to apply",
            title: "The selected candidate is prepared and allowed for apply.",
            tone: "ok",
        });
    } else if (blockedReasonText) {
        entries.push({
            key: "apply_blocked",
            label: "apply blocked",
            title: blockedReasonText,
            tone: "warn",
        });
    }
    if (safeContext.lineUnresolved) {
        entries.push({
            key: "line_unresolved",
            label: "line unresolved",
            title: "The source anchor line could not be resolved precisely.",
            tone: "warn",
        });
    }
    if (!hasPatch || safeContext.patchMissing) {
        entries.push({
            key: "patch_not_generated",
            label: "patch missing",
            title: "No source patch diff is available yet.",
            tone: "muted",
        });
    }
    if (safeContext.prepareFailed) {
        entries.push({
            key: "prepare_failed",
            label: "prepare failed",
            title: String(safeContext.errorMessage || "Patch prepare failed."),
            tone: "danger",
        });
    }
    const source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
    if (safeContext.mockOrLowConfidence || source === "mock") {
        entries.push({
            key: "mock_or_low_confidence",
            label: "mock review",
            title: "This comparison is based on a mock or low-confidence review item.",
            tone: "muted",
        });
    }
    return entries;
}
