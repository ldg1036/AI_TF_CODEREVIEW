import {
    buildRulesImportPreviewSummary,
    createEmptyRuleDraft,
    parseRuleEditorJsonFields,
    validateDetectorJsonText,
} from "./rules-manage-helpers.js";

describe("rules manage helpers", () => {
    test("createEmptyRuleDraft increments order from current rows", () => {
        const draft = createEmptyRuleDraft([{ order: 10 }, { order: 35 }]);
        expect(draft.order).toBe(45);
        expect(draft.file_types).toEqual(["Client", "Server"]);
    });

    test("parseRuleEditorJsonFields validates JSON objects", () => {
        const parsed = parseRuleEditorJsonFields('{"kind":"regex","pattern":"DebugN"}', '{"owner":"qa"}');
        expect(parsed.detector.kind).toBe("regex");
        expect(parsed.meta.owner).toBe("qa");
        expect(() => parseRuleEditorJsonFields("[]", "{}")).toThrow("Detector JSON must be an object.");
    });

    test("validateDetectorJsonText returns status messages", () => {
        expect(validateDetectorJsonText('{"kind":"regex","pattern":"DebugN"}').ok).toBe(true);
        expect(validateDetectorJsonText('{"kind":').ok).toBe(false);
    });

    test("buildRulesImportPreviewSummary normalizes preview payload", () => {
        const summary = buildRulesImportPreviewSummary({
            requested_count: 3,
            valid_count: 2,
            created: 1,
            updated: 1,
            unchanged: 0,
            duplicates: [],
            errors: [],
            effective_rule_count: 4,
            can_apply: true,
        });
        expect(summary.canApply).toBe(true);
        expect(summary.effectiveRuleCount).toBe(4);
    });
});
