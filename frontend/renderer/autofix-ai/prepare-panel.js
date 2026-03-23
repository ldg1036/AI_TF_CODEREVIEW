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
    const boolText = (value) => (value ? "예" : "아니오");
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
        `해시 일치: ${boolText(!!readValue("hash_match", false))}`,
        `앵커 일치: ${boolText(!!readValue("anchors_match", false))}`,
        `구문 검증 통과: ${boolText(!!readValue("syntax_check_passed", false))}`,
        `휴리스틱 회귀 수: ${toInt(readValue("heuristic_regression_count", 0), 0)}`,
        `Ctrlpp 회귀 수: ${toInt(readValue("ctrlpp_regression_count", 0), 0)}`,
        `탐지 모드: ${String(readValue("locator_mode", "")) || "-"}`,
        `적용 엔진 모드: ${String(readValue("apply_engine_mode", "")) || "-"}`,
        `적용 엔진 fallback 사유: ${String(readValue("apply_engine_fallback_reason", "")) || "-"}`,
        `벤치 관찰 모드: ${observeMode}`,
        `해시 게이트 우회: ${boolText(hashBypassed)}`,
        `벤치 튜닝 적용: ${boolText(tuningApplied)}`,
        `토큰 최소 신뢰도: ${tokenMinConfidence}`,
        `토큰 최소 간격: ${tokenMinGap}`,
        `토큰 최대 라인 드리프트: ${tokenMaxLineDrift}`,
        `지시 모드: ${instructionMode}`,
        `지시 작업: ${instructionOperation}`,
        `지시 적용 성공: ${boolText(instructionApplySuccess)}`,
    ];
    const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
    const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    const mergedErrorSet = new Set([...validationErrors, ...qualityErrors].map((item) => String(item || "").trim()).filter(Boolean));
    const errors = Array.from(mergedErrorSet);
    const instructionErrors = Array.isArray(readValue("instruction_validation_errors", []))
        ? readValue("instruction_validation_errors", []).filter(Boolean).map((item) => String(item))
        : [];
    if (instructionErrors.length) {
        lines.push(`지시 검증 오류: ${instructionErrors.slice(0, 3).join(" | ")}`);
    }
    if (errors.length) {
        lines.push("");
        lines.push("오류:");
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
    const boolText = (value) => (value ? "예" : "아니오");
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
        lines.push(`검증 미리보기: ${validationParts.join(" | ")}`);
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
        lines.push(`회귀 미리보기: ${regressionParts.join(" | ")}`);
    }
    if (Object.prototype.hasOwnProperty.call(preview, "allow_apply")) {
        lines.push(`적용 게이트: ${preview.allow_apply ? "허용" : "차단"}`);
    }
    if (preview.semantic_verdict) {
        lines.push(`Semantic verdict: ${String(preview.semantic_verdict)}`);
    }
    const modeParts = [];
    const locatorMode = String(preview.locator_mode || "").trim();
    const applyEngineMode = String(preview.apply_engine_mode || "").trim();
    const instructionMode = String(preview.instruction_mode || "").trim();
    if (locatorMode) modeParts.push(`locator ${locatorMode}`);
    if (applyEngineMode) modeParts.push(`apply ${applyEngineMode}`);
    if (instructionMode) modeParts.push(`instruction ${instructionMode}`);
    if (modeParts.length) {
        lines.push(`실행 모드: ${modeParts.join(" | ")}`);
    }
    const errors = Array.isArray(preview.validation_errors)
        ? preview.validation_errors.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
    const blockedCodes = Array.isArray(preview.blocked_reason_codes)
        ? preview.blocked_reason_codes.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
    if (blockedCodes.length) {
        lines.push(`차단 코드: ${blockedCodes.slice(0, 2).join(" | ")}`);
    }
    if (errors.length) {
        lines.push(`검증 오류: ${errors.slice(0, 2).join(" | ")}`);
    } else if (preview.rejected_reason) {
        lines.push(`거부 사유: ${String(preview.rejected_reason || "").trim()}`);
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
        lines.push(`묶음 규칙 힌트: ${typeof reviewHasGroupedExample === "function" && reviewHasGroupedExample(effectiveRuleId, reviewText) ? "검토 본문에 묶음 예시가 있습니다" : "검토 본문에 묶음 예시가 아직 없습니다"}`);
    }
    const reviewSummary = buildAiReviewSummary(reviewText);
    if (reviewSummary) {
        lines.push(`검토 요약: ${reviewSummary}`);
    }
    const generatorType = String((activeProposal && activeProposal.generator_type) || "").trim().toUpperCase();
    const generatorReason = helpers && typeof helpers.compactUiText === "function"
        ? helpers.compactUiText((activeProposal && activeProposal.generator_reason) || "", 130)
        : String((activeProposal && activeProposal.generator_reason) || "").trim();
    if (generatorType || generatorReason) {
        const generatorText = [generatorType && `생성기 ${generatorType}`, generatorReason].filter(Boolean).join(" | ");
        if (generatorText) lines.push(generatorText);
    } else {
        const fileName = helpers && typeof helpers.violationDisplayFile === "function"
            ? helpers.violationDisplayFile(violation)
            : "";
        if (fileName) lines.push(`원본 파일 ${fileName}`);
        lines.push("생성기 메타데이터가 없어 원본 파일과 요약을 기본 문맥으로 사용합니다.");
    }
    buildQualityPreviewSummaryLines(activeProposal && activeProposal.quality_preview).forEach((line) => {
        if (line) lines.push(line);
    });
    return lines.slice(0, 4);
}
