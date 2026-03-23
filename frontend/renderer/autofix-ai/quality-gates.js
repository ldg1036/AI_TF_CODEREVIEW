const BLOCKED_REASON_LABELS = {
    proposal_missing: "준비된 원문 수정안이 없습니다.",
    prepared_proposal_missing: "선택한 후보의 준비된 수정안이 사라졌습니다.",
    source_changed_since_prepare: "수정안 준비 이후 원문이 바뀌었습니다. 다시 준비해 주세요.",
    cache_expired: "준비된 수정안이 만료되었습니다. 다시 준비해 주세요.",
    apply_blocked: "백엔드에서 이 수정안의 적용을 차단했습니다.",
    instruction_validation_failed: "구조화된 지시 검증에 실패했습니다.",
    syntax_check_failed: "미리보기 구문 검증에 실패했습니다.",
    validation_errors_present: "미리보기 검증에서 오류가 발견되었습니다.",
    identifier_reuse_not_confirmed: "원문 식별자를 충분히 재사용하는지 확인되지 않았습니다.",
    target_issue_not_reduced: "미리보기 재분석에서 대상 이슈가 줄지 않았습니다.",
    new_critical_findings: "미리보기 재분석에서 새로운 치명 이슈가 생겼습니다.",
    new_warning_findings: "미리보기 재분석에서 새로운 경고 이슈가 생겼습니다.",
    target_rule_family_not_reduced: "미리보기 재분석에서 대상 규칙군 영향이 줄지 않았습니다.",
    placeholder_artifacts_detected: "예시 또는 플레이스홀더 흔적이 아직 남아 있습니다.",
    contains_example_arrow: "예시 화살표 표기가 아직 남아 있습니다.",
    contains_placeholder_obj_auto_sel: "플레이스홀더 객체 식별자가 아직 남아 있습니다.",
    contains_placeholder_system_obj: "플레이스홀더 시스템 객체 식별자가 아직 남아 있습니다.",
    contains_placeholder_bsel: "플레이스홀더 선택자 식별자가 아직 남아 있습니다.",
};

export function describeAutofixBlockedReason(code) {
    const normalized = String(code || "").trim();
    if (!normalized) return "";
    return BLOCKED_REASON_LABELS[normalized] || normalized;
}

export function getAutofixApplyGate(proposal) {
    const activeProposal = (proposal && typeof proposal === "object") ? proposal : null;
    if (!activeProposal) {
        return {
            canApply: false,
            prepared: false,
            proposalReady: false,
            preparedProposalId: "",
            blockedReason: "proposal_missing",
            blockedReasonCodes: ["proposal_missing"],
            blockedReasonText: describeAutofixBlockedReason("proposal_missing"),
            blockedReasonDetail: describeAutofixBlockedReason("proposal_missing"),
        };
    }
    const quality = (activeProposal.quality_preview && typeof activeProposal.quality_preview === "object")
        ? activeProposal.quality_preview
        : {};
    const explicitCanApply = activeProposal.can_apply;
    const explicitBlockedReason = String(activeProposal.blocked_reason || "").trim();
    const explicitBlockedReasonText = String(activeProposal.blocked_reason_text || "").trim();
    const preparedProposalId = String(activeProposal.prepared_proposal_id || quality.prepared_proposal_id || activeProposal.proposal_id || "").trim();
    const proposalReady = !!(activeProposal.proposal_ready ?? quality.proposal_ready ?? preparedProposalId);
    const prepared = proposalReady;
    const explicitBlockedReasonCodes = Array.isArray(quality.blocked_reason_codes)
        ? quality.blocked_reason_codes.map((item) => String(item || "").trim()).filter(Boolean)
        : [];
    if (typeof explicitCanApply === "boolean") {
        const blockedReason = explicitCanApply ? "" : (explicitBlockedReason || explicitBlockedReasonCodes[0] || "apply_blocked");
        const blockedReasonText = explicitCanApply ? "" : (explicitBlockedReasonText || String(quality.blocked_reason_text || "").trim() || describeAutofixBlockedReason(blockedReason));
        return {
            canApply: explicitCanApply,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason,
            blockedReasonCodes: explicitCanApply ? [] : (explicitBlockedReasonCodes.length ? explicitBlockedReasonCodes : [blockedReason]),
            blockedReasonText,
            blockedReasonDetail: blockedReasonText,
        };
    }

    const preview = (activeProposal.instruction_preview && typeof activeProposal.instruction_preview === "object")
        ? activeProposal.instruction_preview
        : {};
    const blockingErrors = Array.isArray(quality.blocking_errors) ? quality.blocking_errors.filter(Boolean) : [];
    const validationErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    if (!preview.valid) {
        return {
            canApply: false,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason: "instruction_validation_failed",
            blockedReasonCodes: ["instruction_validation_failed"],
            blockedReasonText: describeAutofixBlockedReason("instruction_validation_failed"),
            blockedReasonDetail: describeAutofixBlockedReason("instruction_validation_failed"),
        };
    }
    if (!quality.syntax_check_passed) {
        return {
            canApply: false,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason: "syntax_check_failed",
            blockedReasonCodes: ["syntax_check_failed"],
            blockedReasonText: describeAutofixBlockedReason("syntax_check_failed"),
            blockedReasonDetail: describeAutofixBlockedReason("syntax_check_failed"),
        };
    }
    if (blockingErrors.length) {
        const blockedReason = String(blockingErrors[0]);
        return {
            canApply: false,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason,
            blockedReasonCodes: [blockedReason],
            blockedReasonText: String(quality.blocked_reason_text || "").trim() || describeAutofixBlockedReason(blockedReason),
            blockedReasonDetail: String(quality.blocked_reason_text || "").trim() || describeAutofixBlockedReason(blockedReason),
        };
    }
    if (validationErrors.length) {
        const blockedReason = String(validationErrors[0]);
        return {
            canApply: false,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason,
            blockedReasonCodes: [blockedReason],
            blockedReasonText: String(quality.blocked_reason_text || "").trim() || describeAutofixBlockedReason(blockedReason),
            blockedReasonDetail: String(quality.blocked_reason_text || "").trim() || describeAutofixBlockedReason(blockedReason),
        };
    }
    if (quality.identifier_reuse_confirmed === false) {
        return {
            canApply: false,
            prepared,
            proposalReady,
            preparedProposalId,
            blockedReason: "identifier_reuse_not_confirmed",
            blockedReasonCodes: ["identifier_reuse_not_confirmed"],
            blockedReasonText: describeAutofixBlockedReason("identifier_reuse_not_confirmed"),
            blockedReasonDetail: describeAutofixBlockedReason("identifier_reuse_not_confirmed"),
        };
    }
    return {
        canApply: true,
        prepared,
        proposalReady,
        preparedProposalId,
        blockedReason: "",
        blockedReasonCodes: [],
        blockedReasonText: "",
        blockedReasonDetail: "",
    };
}
