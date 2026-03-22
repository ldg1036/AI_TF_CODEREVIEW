export function getAutofixApplyGate(proposal) {
    const activeProposal = (proposal && typeof proposal === "object") ? proposal : null;
    if (!activeProposal) {
        return { canApply: false, blockedReason: "proposal_missing" };
    }
    const explicitCanApply = activeProposal.can_apply;
    const explicitBlockedReason = String(activeProposal.blocked_reason || "").trim();
    if (typeof explicitCanApply === "boolean") {
        return {
            canApply: explicitCanApply,
            blockedReason: explicitCanApply ? "" : (explicitBlockedReason || "apply_blocked"),
        };
    }
    const preview = (activeProposal.instruction_preview && typeof activeProposal.instruction_preview === "object")
        ? activeProposal.instruction_preview
        : {};
    const quality = (activeProposal.quality_preview && typeof activeProposal.quality_preview === "object")
        ? activeProposal.quality_preview
        : {};
    const blockingErrors = Array.isArray(quality.blocking_errors) ? quality.blocking_errors.filter(Boolean) : [];
    const validationErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
    if (!preview.valid) return { canApply: false, blockedReason: "instruction_validation_failed" };
    if (!quality.syntax_check_passed) return { canApply: false, blockedReason: "syntax_check_failed" };
    if (blockingErrors.length) return { canApply: false, blockedReason: String(blockingErrors[0]) };
    if (validationErrors.length) return { canApply: false, blockedReason: String(validationErrors[0]) };
    if (quality.identifier_reuse_confirmed === false) {
        return { canApply: false, blockedReason: "identifier_reuse_not_confirmed" };
    }
    return { canApply: true, blockedReason: "" };
}
