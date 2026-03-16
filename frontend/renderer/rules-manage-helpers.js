export function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
}

export function createEmptyRuleDraft(rows = []) {
    const safeRows = Array.isArray(rows) ? rows : [];
    const nextOrder = safeRows.reduce((maxValue, row) => Math.max(maxValue, Number((row && row.order) || 0) || 0), 0) + 10;
    return {
        id: "",
        order: nextOrder,
        enabled: true,
        file_types: ["Client", "Server"],
        rule_id: "",
        item: "",
        detector: {
            kind: "regex",
            pattern: "",
            flags: ["MULTILINE"],
        },
        finding: {
            severity: "Warning",
            message: "",
        },
        meta: {},
    };
}

export function parseRuleEditorJsonFields(detectorText, metaText) {
    let detector;
    let meta;
    try {
        detector = JSON.parse(String(detectorText || "").trim() || "{}");
    } catch (_) {
        throw new Error("Detector JSON must be valid JSON.");
    }
    try {
        meta = JSON.parse(String(metaText || "").trim() || "{}");
    } catch (_) {
        throw new Error("Meta JSON must be valid JSON.");
    }
    if (!detector || typeof detector !== "object" || Array.isArray(detector)) {
        throw new Error("Detector JSON must be an object.");
    }
    if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
        throw new Error("Meta JSON must be an object.");
    }
    return { detector, meta };
}

export function validateDetectorJsonText(detectorText) {
    try {
        const { detector } = parseRuleEditorJsonFields(detectorText, "{}");
        const kind = String((detector && detector.kind) || "").trim() || "regex";
        return {
            ok: true,
            message: `Detector JSON looks valid (${kind}).`,
            detector,
        };
    } catch (error) {
        return {
            ok: false,
            message: String((error && error.message) || error || "Detector JSON is invalid."),
            detector: null,
        };
    }
}

export function extractRulesFromImportPayload(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.rules)) return payload.rules;
    return [];
}

export function buildRulesImportPreviewSummary(preview) {
    const safePreview = preview && typeof preview === "object" ? preview : {};
    const errors = Array.isArray(safePreview.errors) ? safePreview.errors : [];
    const duplicates = Array.isArray(safePreview.duplicates) ? safePreview.duplicates : [];
    return {
        requestedCount: Number(safePreview.requested_count || 0) || 0,
        validCount: Number(safePreview.valid_count || 0) || 0,
        created: Number(safePreview.created || 0) || 0,
        updated: Number(safePreview.updated || 0) || 0,
        unchanged: Number(safePreview.unchanged || 0) || 0,
        duplicatesCount: duplicates.length,
        errorsCount: errors.length,
        effectiveRuleCount: Number(safePreview.effective_rule_count || 0) || 0,
        canApply: !!safePreview.can_apply && duplicates.length === 0 && errors.length === 0,
    };
}
