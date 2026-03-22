export function buildDiffModalMeta({ violation, aiMatch, proposal, helpers }) {
    const entries = [];
    const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(proposal, helpers.violationDisplayFile(violation)));
    const parentSource = String((violation && violation.priority_origin) || "P1").toUpperCase();
    const p3Source = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
    const generatorType = String((proposal && proposal.generator_type) || "").trim().toUpperCase();
    const hasProposal = !!(proposal && String(proposal.unified_diff || "").trim());
    if (fileName) entries.push(`File ${fileName}`);
    entries.push(`Source ${parentSource}`);
    if (String((violation && violation.rule_id) || "").trim()) entries.push(`Rule ${String(violation.rule_id || "").trim()}`);
    if (helpers.positiveLineOrZero((violation && violation.line) || 0) > 0) entries.push(`Line ${helpers.positiveLineOrZero(violation.line)}`);
    entries.push(p3Source === "mock" ? "P3 Mock" : "P3 Live");
    if (generatorType) entries.push(`Proposal ${generatorType}`);
    entries.push(hasProposal ? "Patch ready" : "Patch missing");
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
    lines.push(proposal && String(proposal.unified_diff || "").trim()
        ? "A source patch diff is available."
        : "The source patch diff is not ready yet.");
    return lines;
}

export function buildDiffModalStatusEntries({ context, aiMatch, proposal }) {
    const entries = [];
    const safeContext = context && typeof context === "object" ? context : {};
    const hasPatch = !!String((proposal && proposal.unified_diff) || "").trim();
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
