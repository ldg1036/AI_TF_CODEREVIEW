const BLOCKED_REASON_LABELS = {
    proposal_missing: "No prepared source proposal is available.",
    prepared_proposal_missing: "The prepared patch is missing for the selected candidate.",
    source_changed_since_prepare: "The source changed after prepare. Prepare the patch again.",
    cache_expired: "The prepared patch expired. Prepare the patch again.",
    apply_blocked: "The backend marked this proposal as blocked.",
    instruction_validation_failed: "Structured instruction validation failed.",
    syntax_check_failed: "Preview syntax validation failed.",
    validation_errors_present: "Preview validation returned errors.",
    identifier_reuse_not_confirmed: "The proposal does not clearly reuse identifiers from the source snippet.",
    target_issue_not_reduced: "Preview reanalysis did not reduce the target issue.",
    new_critical_findings: "Preview reanalysis introduced new critical findings.",
    new_warning_findings: "Preview reanalysis introduced new warning findings.",
    target_rule_family_not_reduced: "Preview reanalysis did not reduce the target rule family footprint.",
    placeholder_artifacts_detected: "Example or placeholder markers are still present in the candidate patch.",
    contains_example_arrow: "Example arrow markers are still present in the candidate patch.",
    contains_placeholder_obj_auto_sel: "Placeholder object identifiers are still present in the candidate patch.",
    contains_placeholder_system_obj: "Placeholder system object identifiers are still present in the candidate patch.",
    contains_placeholder_bsel: "Placeholder selector identifiers are still present in the candidate patch.",
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
