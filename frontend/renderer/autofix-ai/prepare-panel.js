export function formatAutofixValidationSummary(resultPayload) {
    const validation = (resultPayload && resultPayload.validation) || {};
    const quality = (resultPayload && resultPayload.quality_metrics) || {};
    if ((!validation || typeof validation !== "object") && (!quality || typeof quality !== "object")) return "";
    const readValue = (key, fallback = "") => {
        if (validation && typeof validation === "object" && Object.prototype.hasOwnProperty.call(validation, key)) {
            return validation[key];
        }
        if (quality && typeof quality === "object" && Object.prototype.hasOwnProperty.call(quality, key)) {
            return quality[key];
        }
        return fallback;
    };
    const boolText = (value) => (value ? "yes" : "no");
    const toFloat = (value, fallback = 0) => {
        const parsed = Number.parseFloat(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    };
    const toInt = (value, fallback = 0) => {
        const parsed = Number.parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : fallback;
    };
    const observeMode = String(readValue("benchmark_observe_mode", "strict_hash") || "strict_hash");
    const hashBypassed = !!readValue("hash_gate_bypassed", false);
    const tuningApplied = !!readValue("benchmark_tuning_applied", false);
    const tokenMinConfidence = toFloat(readValue("token_min_confidence_used", 0.8), 0.8);
    const tokenMinGap = toFloat(readValue("token_min_gap_used", 0.15), 0.15);
    const tokenMaxLineDrift = toInt(readValue("token_max_line_drift_used", 0), 0);
    const instructionMode = String(readValue("instruction_mode", "off") || "off");
    const instructionOperation = String(readValue("instruction_operation", "") || "-");
    const instructionApplySuccess = !!readValue("instruction_apply_success", false);
    const lines = [
        `hash_match: ${boolText(!!readValue("hash_match", false))}`,
        `anchors_match: ${boolText(!!readValue("anchors_match", false))}`,
        `syntax_check_passed: ${boolText(!!readValue("syntax_check_passed", false))}`,
        `heuristic_regression_count: ${toInt(readValue("heuristic_regression_count", 0), 0)}`,
        `ctrlpp_regression_count: ${toInt(readValue("ctrlpp_regression_count", 0), 0)}`,
        `locator_mode: ${String(readValue("locator_mode", "")) || "-"}`,
        `apply_engine_mode: ${String(readValue("apply_engine_mode", "")) || "-"}`,
        `apply_engine_fallback_reason: ${String(readValue("apply_engine_fallback_reason", "")) || "-"}`,
        `benchmark_observe_mode: ${observeMode}`,
        `hash_gate_bypassed: ${boolText(hashBypassed)}`,
        `benchmark_tuning_applied: ${boolText(tuningApplied)}`,
        `token_min_confidence_used: ${tokenMinConfidence}`,
        `token_min_gap_used: ${tokenMinGap}`,
        `token_max_line_drift_used: ${tokenMaxLineDrift}`,
        `instruction_mode: ${instructionMode}`,
        `instruction_operation: ${instructionOperation}`,
        `instruction_apply_success: ${boolText(instructionApplySuccess)}`,
    ];
    const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    const mergedErrorSet = new Set([...validationErrors, ...qualityErrors].map((item) => String(item || "").trim()).filter(Boolean));
    const errors = Array.from(mergedErrorSet);
    const instructionErrors = Array.isArray(readValue("instruction_validation_errors", []))
        ? readValue("instruction_validation_errors", []).filter(Boolean).map((item) => String(item))
        : [];
    if (instructionErrors.length) {
        lines.push(`instruction_validation_errors: ${instructionErrors.slice(0, 3).join(" | ")}`);
    }
    if (errors.length) {
        lines.push("");
        lines.push("errors:");
        errors.slice(0, 10).forEach((err) => lines.push(`- ${String(err)}`));
    }
    return lines.join("\n");
}

export function buildAiReviewSummary(reviewText) {
    const raw = String(reviewText || "");
    if (!raw.trim()) return "AI review unavailable";
    const noCodeBlock = raw.replace(/```[\s\S]*?```/g, " ").replace(/`([^`]+)`/g, "$1");
    const cleaned = noCodeBlock
        .split(/\r?\n/)
        .map((line) => line.replace(/^\s*summary\s*[:\-]?\s*/i, "").trim())
        .filter((line) => line.length > 0)
        .join(" ");
    const sentence = cleaned.split(/(?<=[.!?])\s+/)[0] || cleaned;
    const compact = sentence.replace(/\s+/g, " ").trim();
    if (!compact) return "AI review unavailable";
    if (compact.length <= 200) return compact;
    return `${compact.slice(0, 197)}...`;
}

export function buildQualityPreviewSummaryLines(qualityPreview) {
    const preview = (qualityPreview && typeof qualityPreview === "object") ? qualityPreview : {};
    if (!Object.keys(preview).length) return [];
    const boolText = (value) => (value ? "yes" : "no");
    const lines = [];
    const validationParts = [];
    if (Object.prototype.hasOwnProperty.call(preview, "hash_match")) {
        validationParts.push(`hash ${boolText(!!preview.hash_match)}`);
    }
    if (Object.prototype.hasOwnProperty.call(preview, "anchors_match")) {
        validationParts.push(`anchors ${boolText(!!preview.anchors_match)}`);
    }
    if (Object.prototype.hasOwnProperty.call(preview, "syntax_check_passed")) {
        validationParts.push(`syntax ${boolText(!!preview.syntax_check_passed)}`);
    }
    if (validationParts.length) {
        lines.push(`Validation preview: ${validationParts.join(" | ")}`);
    }
    const regressionParts = [];
    if (Object.prototype.hasOwnProperty.call(preview, "heuristic_regression_count")) {
        regressionParts.push(`heuristic ${Number.parseInt(preview.heuristic_regression_count, 10) || 0}`);
    }
    if (Object.prototype.hasOwnProperty.call(preview, "ctrlpp_regression_count")) {
        regressionParts.push(`ctrlpp ${Number.parseInt(preview.ctrlpp_regression_count, 10) || 0}`);
    }
    if (Object.prototype.hasOwnProperty.call(preview, "semantic_violation_count")) {
        regressionParts.push(`semantic ${Number.parseInt(preview.semantic_violation_count, 10) || 0}`);
    }
    if (regressionParts.length) {
        lines.push(`Regression preview: ${regressionParts.join(" | ")}`);
    }
    const modeParts = [];
    const locatorMode = String(preview.locator_mode || "").trim();
    const applyEngineMode = String(preview.apply_engine_mode || "").trim();
    const instructionMode = String(preview.instruction_mode || "").trim();
    if (locatorMode) modeParts.push(`locator ${locatorMode}`);
    if (applyEngineMode) modeParts.push(`apply ${applyEngineMode}`);
    if (instructionMode) modeParts.push(`instruction ${instructionMode}`);
    if (modeParts.length) {
        lines.push(`Execution mode: ${modeParts.join(" | ")}`);
    }
    const errors = Array.isArray(preview.validation_errors)
        ? preview.validation_errors.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
    if (errors.length) {
        lines.push(`Validation errors: ${errors.slice(0, 2).join(" | ")}`);
    } else if (preview.rejected_reason) {
        lines.push(`Rejected reason: ${String(preview.rejected_reason || "").trim()}`);
    }
    return lines.slice(0, 4);
}

export function buildAiSummaryLines(
    violationOrOptions,
    aiMatchArg,
    proposalArg,
    helpersArg,
    reviewHasGroupedExampleArg,
) {
    const options = (
        violationOrOptions
        && typeof violationOrOptions === "object"
        && Object.prototype.hasOwnProperty.call(violationOrOptions, "helpers")
    )
        ? violationOrOptions
        : {
            violation: violationOrOptions,
            aiMatch: aiMatchArg,
            proposal: proposalArg,
            helpers: helpersArg,
            reviewHasGroupedExample: reviewHasGroupedExampleArg,
        };
    const {
        violation,
        aiMatch,
        proposal,
        helpers,
        reviewHasGroupedExample,
    } = options;
    const activeProposal = (proposal && typeof proposal === "object") ? proposal : null;
    const lines = [];
    const effectiveRuleId = String((violation && violation.rule_id) || (aiMatch && aiMatch.parent_rule_id) || "").trim();
    const reviewText = String((activeProposal && activeProposal.summary) || (aiMatch && aiMatch.review) || "");
    const isMultiAggregationRule = !!(helpers && typeof helpers.isMultiAggregationRule === "function")
        && helpers.isMultiAggregationRule(effectiveRuleId);
    if (isMultiAggregationRule) {
        lines.push(`Grouped-rule hint: ${typeof reviewHasGroupedExample === "function" && reviewHasGroupedExample(effectiveRuleId, reviewText) ? "grouped example found in review" : "no grouped example found in review"}`);
    }
    const reviewSummary = buildAiReviewSummary(reviewText);
    if (reviewSummary) {
        lines.push(`Review summary: ${reviewSummary}`);
    }
    const generatorType = String((activeProposal && activeProposal.generator_type) || "").trim().toUpperCase();
    const generatorReason = helpers && typeof helpers.compactUiText === "function"
        ? helpers.compactUiText((activeProposal && activeProposal.generator_reason) || "", 130)
        : String((activeProposal && activeProposal.generator_reason) || "").trim();
    if (generatorType || generatorReason) {
        const generatorText = [generatorType && `Generator ${generatorType}`, generatorReason].filter(Boolean).join(" | ");
        if (generatorText) lines.push(generatorText);
    } else {
        const fileName = helpers && typeof helpers.violationDisplayFile === "function"
            ? helpers.violationDisplayFile(violation)
            : "";
        if (fileName) lines.push(`Source file ${fileName}`);
        lines.push("No generator metadata was attached, so the source file and summary are being used as the fallback context.");
    }
    buildQualityPreviewSummaryLines(activeProposal && activeProposal.quality_preview).forEach((line) => {
        if (line) lines.push(line);
    });
    return lines.slice(0, 4);
}
