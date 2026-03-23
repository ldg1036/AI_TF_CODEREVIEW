import { createAutofixAiController } from "./autofix-ai.js";
import { describeAutofixBlockedReason } from "./autofix-ai/quality-gates.js";

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
            expect.stringContaining("검토 요약:"),
            expect.stringContaining("생성기 LLM"),
            expect.stringContaining("검증 미리보기:"),
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
        expect(lines.some((line) => line.includes("검증 미리보기:"))).toBe(false);
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

    test("getAutofixApplyGate blocks unsafe proposals", () => {
        const controller = createController();
        const gate = controller.getAutofixApplyGate({
            proposal_id: "llm-unsafe",
            instruction_preview: { valid: true },
            quality_preview: {
                syntax_check_passed: true,
                validation_errors: [],
                blocking_errors: ["contains_placeholder_system_obj"],
                identifier_reuse_confirmed: false,
            },
        });
        expect(gate.canApply).toBe(false);
        expect(gate.blockedReason).toBe("contains_placeholder_system_obj");
        expect(gate.blockedReasonCodes).toEqual(["contains_placeholder_system_obj"]);
        expect(gate.blockedReasonDetail).toBe(describeAutofixBlockedReason("contains_placeholder_system_obj"));
    });

    test("getAutofixApplyGate allows clean proposals", () => {
        const controller = createController();
        const gate = controller.getAutofixApplyGate({
            proposal_id: "llm-clean",
            instruction_preview: { valid: true },
            quality_preview: {
                syntax_check_passed: true,
                validation_errors: [],
                blocking_errors: [],
                identifier_reuse_confirmed: true,
            },
        });
        expect(gate.canApply).toBe(true);
        expect(gate.blockedReason).toBe("");
    });

    test("getAutofixApplyGate prefers backend allow_apply verdict when present", () => {
        const controller = createController();
        const gate = controller.getAutofixApplyGate({
            proposal_id: "llm-blocked",
            prepared_proposal_id: "llm-blocked",
            proposal_ready: true,
            can_apply: false,
            blocked_reason: "target_issue_not_reduced",
            blocked_reason_text: "Preview reanalysis did not reduce the target issue.",
            quality_preview: {
                allow_apply: false,
                blocked_reason_codes: ["target_issue_not_reduced"],
            },
        });
        expect(gate.canApply).toBe(false);
        expect(gate.prepared).toBe(true);
        expect(gate.preparedProposalId).toBe("llm-blocked");
        expect(gate.blockedReason).toBe("target_issue_not_reduced");
        expect(gate.blockedReasonText).toBe("Preview reanalysis did not reduce the target issue.");
        expect(gate.blockedReasonDetail).toBe("Preview reanalysis did not reduce the target issue.");
    });

    test("getAutofixApplyGate exposes drift reasons from backend codes", () => {
        const controller = createController();
        const gate = controller.getAutofixApplyGate({
            proposal_id: "llm-expired",
            prepared_proposal_id: "llm-expired",
            proposal_ready: true,
            can_apply: false,
            blocked_reason: "source_changed_since_prepare",
            quality_preview: {
                allow_apply: false,
                blocked_reason_codes: ["source_changed_since_prepare"],
            },
        });
        expect(gate.canApply).toBe(false);
        expect(gate.blockedReason).toBe("source_changed_since_prepare");
        expect(gate.blockedReasonDetail).toBe(describeAutofixBlockedReason("source_changed_since_prepare"));
    });

    test("describeGeneratedAiPayload marks mock reviews as preview-only", () => {
        const controller = createController();
        const state = controller.describeGeneratedAiPayload({
            status: "generated",
            status_reason: "mock_generated",
            review_source: "mock",
            review_text_present: true,
            review_item: {
                source: "mock",
                review: "Mock review text",
            },
        });
        expect(state.isMock).toBe(true);
        expect(state.usable).toBe(false);
        expect(state.message).toContain("모의 검토만 생성되었습니다");
    });

    test("describeGeneratedAiPayload reports live review success only when review text is present", () => {
        const controller = createController();
        const state = controller.describeGeneratedAiPayload({
            status: "generated",
            status_reason: "generated",
            review_source: "live",
            review_text_present: true,
            review_item: {
                source: "live",
                review: "Use grouped setter",
            },
        });
        expect(state.isMock).toBe(false);
        expect(state.usable).toBe(true);
        expect(state.message).toBe("Live AI 개선 제안이 생성되었습니다.");
    });
});
