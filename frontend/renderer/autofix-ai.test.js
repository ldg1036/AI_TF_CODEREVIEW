import { createAutofixAiController } from "./autofix-ai.js";

describe("autofix ai controller", () => {
    function createController() {
        return createAutofixAiController({
            dom: {},
            state: {},
            helpers: {
                compactUiText: (value) => String(value || ""),
                isMultiAggregationRule: () => false,
                violationDisplayFile: (violation) => String((violation && violation.file) || ""),
            },
        });
    }

    test("buildAiSummaryLines renders quality preview without throwing", () => {
        const controller = createController();
        const lines = controller.buildAiSummaryLines(
            { rule_id: "EXC-DP-01", file: "sample.ctl" },
            { review: "Use guarded access around dpGet." },
            {
                generator_type: "llm",
                generator_reason: "cached review",
                quality_preview: {
                    hash_match: true,
                    anchors_match: true,
                    syntax_check_passed: true,
                    heuristic_regression_count: 0,
                    ctrlpp_regression_count: 0,
                    locator_mode: "anchor",
                    validation_errors: [],
                },
            },
        );
        expect(lines).toEqual(expect.arrayContaining([
            expect.stringContaining("Review summary:"),
            expect.stringContaining("Generator LLM"),
            expect.stringContaining("Validation preview:"),
        ]));
    });

    test("buildAiSummaryLines fails soft when quality preview is missing", () => {
        const controller = createController();
        const lines = controller.buildAiSummaryLines(
            { rule_id: "EXC-DP-01", file: "sample.ctl" },
            { review: "Use guarded access around dpGet." },
            {
                generator_type: "rule",
                generator_reason: "rule template",
                quality_preview: null,
            },
        );
        expect(lines.length).toBeGreaterThan(0);
        expect(lines.some((line) => line.includes("Validation preview:"))).toBe(false);
    });

    test("normalizeAutofixBundle falls back to highest scored live llm proposal", () => {
        const controller = createController();
        const bundle = controller.normalizeAutofixBundle({
            proposals: [
                {
                    proposal_id: "rule-1",
                    generator_type: "rule",
                    source: "rule-template",
                    compare_score: { total: 120 },
                },
                {
                    proposal_id: "llm-1",
                    generator_type: "llm",
                    source: "live-ai",
                    compare_score: { total: 127 },
                },
            ],
        });
        expect(bundle.selected_proposal_id).toBe("llm-1");
        expect(bundle.active_proposal_id).toBe("llm-1");
    });
});
