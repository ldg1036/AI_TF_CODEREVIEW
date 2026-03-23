export function buildAiCardKey(violation, eventName, aiMatch) {
    const fileName = String((violation && (violation.file || violation.object)) || "");
    const objectName = String((violation && violation.object) || (aiMatch && aiMatch.object) || "");
    const evt = String(eventName || (aiMatch && aiMatch.event) || "Global");
    const review = String((aiMatch && aiMatch.review) || "");
    return [fileName, objectName, evt, review].join("||");
}

export function getActiveAutofixProposal(bundle) {
    if (!bundle || !Array.isArray(bundle.proposals) || !bundle.proposals.length) return null;
    const activeId = String(bundle.active_proposal_id || bundle.selected_proposal_id || "");
    const found = bundle.proposals.find((item) => String((item && item.proposal_id) || "") === activeId);
    return found || bundle.proposals[0] || null;
}
