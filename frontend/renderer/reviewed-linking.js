import {
    basenamePath,
    canonicalFileId,
    fileIdentityKey,
    inferRuleIdFromReviewedBlock,
    messageSearchToken,
    normalizeP1RuleId,
    normalizeReviewedMessageKey,
    p1RulePrefixGroup,
    positiveLineOrZero,
    sameFileIdentity,
    violationCanonicalFileId,
    violationResolvedFile,
} from "./utils.js";

export function extractReviewCodeBlocks(reviewText) {
    const raw = String(reviewText || "");
    const blocks = [];
    const regex = /```(?:[\w#+.-]+)?\s*([\s\S]*?)```/gi;
    let match;
    while ((match = regex.exec(raw)) !== null) {
        const block = String((match && match[1]) || "").trim();
        if (block) blocks.push(block);
    }
    return blocks;
}

export function reviewHasGroupedExample(ruleId, reviewText) {
    const rule = String(ruleId || "").trim().toUpperCase();
    const blocks = extractReviewCodeBlocks(reviewText).map((item) => item.toLowerCase());
    if (!rule || !blocks.length) return false;
    if (rule === "PERF-SETMULTIVALUE-ADOPT-01") return blocks.some((block) => block.includes("setmultivalue("));
    if (rule === "PERF-GETMULTIVALUE-ADOPT-01") return blocks.some((block) => block.includes("getmultivalue("));
    if (rule === "PERF-DPSET-BATCH-01") {
        return blocks.some((block) => /dpset\s*\(([\s\S]*?)\);/i.test(block) && ((block.match(/,/g) || []).length >= 3));
    }
    if (rule === "PERF-DPGET-BATCH-01") {
        return blocks.some((block) => /dpget\s*\(([\s\S]*?)\);/i.test(block) && ((block.match(/,/g) || []).length >= 3));
    }
    return false;
}

function buildFlattenedP1Items(p1Groups) {
    const flattened = [];
    (Array.isArray(p1Groups) ? p1Groups : []).forEach((group) => {
        (Array.isArray(group && group.violations) ? group.violations : []).forEach((entry, index) => {
            const violation = { ...entry, object: group.object };
            violation.file = violation.file || group.object;
            violation.file_path = violation.file_path || violation.file || group.object;
            violation.priority_origin = violation.priority_origin || "P1";
            const flatKey = String(
                violation.issue_id
                || `${violationCanonicalFileId(violation, group.object)}:${positiveLineOrZero(violation.line)}:${String(violation.rule_id || "")}:${index}`,
            );
            flattened.push({
                flatKey,
                violation,
                eventName: String(group.event || "Global"),
                rowObject: group.object,
                fileKey: violationCanonicalFileId(violation, group.object),
            });
        });
    });
    return flattened;
}

function buildReviewedIndexes(flattenedP1) {
    const byIssueId = new Map();
    const bySecondary = new Map();
    flattenedP1.forEach((item) => {
        const issueId = String(item.violation.issue_id || "").trim();
        if (issueId) {
            if (!byIssueId.has(issueId)) byIssueId.set(issueId, []);
            byIssueId.get(issueId).push(item);
        }
        const secondaryKey = [
            item.fileKey,
            positiveLineOrZero(item.violation.line),
            normalizeP1RuleId(item.violation.rule_id),
            normalizeReviewedMessageKey(item.violation.message),
        ].join("||");
        if (!bySecondary.has(secondaryKey)) bySecondary.set(secondaryKey, []);
        bySecondary.get(secondaryKey).push(item);
    });
    return { byIssueId, bySecondary };
}

function isGroupedRuleConflict(effectiveRuleId, itemRule) {
    return (
        (effectiveRuleId === "PERF-DPGET-BATCH-01" && itemRule === "PERF-GETMULTIVALUE-ADOPT-01")
        || (effectiveRuleId === "PERF-GETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPGET-BATCH-01")
        || (effectiveRuleId === "PERF-DPSET-BATCH-01" && itemRule === "PERF-SETMULTIVALUE-ADOPT-01")
        || (effectiveRuleId === "PERF-SETMULTIVALUE-ADOPT-01" && itemRule === "PERF-DPSET-BATCH-01")
    );
}

function sortMatchedItemsByCanonicalFit(items, effectiveRuleId, lineNo, blockMessage) {
    const normalizedTargetRuleId = normalizeP1RuleId(effectiveRuleId);
    const normalizedMessage = normalizeReviewedMessageKey(blockMessage);
    const targetLine = positiveLineOrZero(lineNo);
    const scoreItem = (item) => {
        const violation = (item && item.violation && typeof item.violation === "object") ? item.violation : {};
        const ruleId = normalizeP1RuleId(violation.rule_id);
        const line = positiveLineOrZero(violation.line);
        const message = normalizeReviewedMessageKey(violation.message);
        let score = 0;
        if (normalizedTargetRuleId && normalizedTargetRuleId !== "UNKNOWN" && ruleId === normalizedTargetRuleId) score += 8;
        if (targetLine > 0 && line > 0) {
            const delta = Math.abs(line - targetLine);
            if (delta === 0) score += 6;
            else if (delta <= 2) score += 4;
            else if (delta <= 5) score += 2;
            else if (delta <= 10) score += 1;
        }
        if (normalizedMessage && message && normalizedMessage === message) score += 3;
        if (String(violation.issue_id || "").trim()) score += 1;
        return score;
    };
    return [...(Array.isArray(items) ? items : [])].sort((left, right) => {
        const scoreDiff = scoreItem(right) - scoreItem(left);
        if (scoreDiff !== 0) return scoreDiff;
        return positiveLineOrZero((left && left.violation && left.violation.line) || 0)
            - positiveLineOrZero((right && right.violation && right.violation.line) || 0);
    });
}

function buildReviewedCandidateFileKeys(reviewedFile, metaFile, blockCanonicalFileId = "") {
    return Array.from(
        new Set(
            [blockCanonicalFileId, metaFile, reviewedFile, basenamePath(metaFile), basenamePath(reviewedFile)]
                .map((value) => canonicalFileId(value))
                .filter(Boolean),
        ),
    );
}

function matchesCandidateFileKeys(itemFileKey, candidateFileKeys) {
    if (!Array.isArray(candidateFileKeys) || !candidateFileKeys.length) return true;
    return candidateFileKeys.some((candidateFileKey) => sameFileIdentity(itemFileKey, candidateFileKey));
}

export function buildReviewedP1SyncPlan({ p1Groups, reviewedTodoCacheByFile, pickHigherSeverity }) {
    const flattenedP1 = buildFlattenedP1Items(p1Groups);
    const { byIssueId, bySecondary } = buildReviewedIndexes(flattenedP1);
    const mappingDiagnostics = {
        violation_total: flattenedP1.length,
        violation_unknown_rule_count: 0,
        violation_cfg_rule_count: 0,
        violation_cfg_alias_mapped_count: 0,
        violation_cfg_alias_unmapped_ids: [],
        reviewed_block_total: 0,
        reviewed_unknown_rule_count: 0,
        reviewed_unknown_with_no_line_count: 0,
        reviewed_inferred_rule_count: 0,
        reviewed_inferred_match_success_count: 0,
        reviewed_inferred_match_ambiguous_count: 0,
        reviewed_unknown_after_infer_count: 0,
        review_only_grouped_row_count: 0,
        review_only_grouped_collapsed_count: 0,
        synced_message_mismatch_count: 0,
        synced_rule_message_conflict_samples: [],
    };

    flattenedP1.forEach((item) => {
        const rawRuleId = String(item && item.violation && item.violation.rule_id || "").trim();
        const normalizedRuleId = normalizeP1RuleId(rawRuleId);
        if (!rawRuleId || normalizedRuleId === "UNKNOWN") mappingDiagnostics.violation_unknown_rule_count += 1;
        if (/^cfg-/i.test(rawRuleId)) {
            mappingDiagnostics.violation_cfg_rule_count += 1;
            if (normalizedRuleId !== rawRuleId.toUpperCase()) {
                mappingDiagnostics.violation_cfg_alias_mapped_count += 1;
            } else {
                mappingDiagnostics.violation_cfg_alias_unmapped_ids.push(rawRuleId);
            }
        }
    });
    mappingDiagnostics.violation_cfg_alias_unmapped_ids = Array.from(new Set(mappingDiagnostics.violation_cfg_alias_unmapped_ids)).sort();

    const rowPlans = [];
    const usedFlatKeys = new Set();
    let syncedCount = 0;
    let reviewOnlyCount = 0;

    const cacheEntries = reviewedTodoCacheByFile instanceof Map ? reviewedTodoCacheByFile.entries() : [];
    for (const [reviewedFile, blocks] of cacheEntries) {
        const fileBlocks = Array.isArray(blocks) ? blocks : [];
        mappingDiagnostics.reviewed_block_total += fileBlocks.length;
        fileBlocks.forEach((block, idx) => {
            const meta = (block && block.meta && typeof block.meta === "object") ? block.meta : {};
            const issueId = String(meta.issue_id || "").trim();
            const ruleId = String(meta.rule_id || "").trim();
            const lineNo = positiveLineOrZero(meta.line || 0);
            const normalizedRuleId = normalizeP1RuleId(ruleId);
            const inferred = inferRuleIdFromReviewedBlock(block);
            const inferredRuleId = normalizeP1RuleId(inferred.inferredRuleId);
            if (inferredRuleId !== "UNKNOWN" && inferred.source !== "meta") {
                mappingDiagnostics.reviewed_inferred_rule_count += 1;
            }
            if (!ruleId || normalizedRuleId === "UNKNOWN") {
                mappingDiagnostics.reviewed_unknown_rule_count += 1;
                if (lineNo <= 0) mappingDiagnostics.reviewed_unknown_with_no_line_count += 1;
            }

            const effectiveRuleId = normalizedRuleId !== "UNKNOWN" ? normalizedRuleId : inferredRuleId;
            const blockMessage = String(block.message || "").trim();
            const candidateFileKeys = buildReviewedCandidateFileKeys(reviewedFile, meta.file || reviewedFile, block.canonical_file_id || meta.canonical_file_id);
            const secondaryKeys = candidateFileKeys.map((fileKey) => [
                fileKey,
                lineNo,
                effectiveRuleId,
                normalizeReviewedMessageKey(blockMessage),
            ].join("||"));

            let matched = [];
            let matchedReason = "";
            if (issueId && byIssueId.has(issueId)) {
                matched = (byIssueId.get(issueId) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                if (matched.length) matchedReason = "meta_exact";
            }
            if (!matched.length && (lineNo > 0 || ruleId || blockMessage)) {
                for (const secondaryKey of secondaryKeys) {
                    if (!bySecondary.has(secondaryKey)) continue;
                    matched = (bySecondary.get(secondaryKey) || []).filter((item) => !usedFlatKeys.has(item.flatKey));
                    if (matched.length) {
                        matchedReason = "secondary_exact";
                        break;
                    }
                }
            }
            if (!matched.length && effectiveRuleId !== "UNKNOWN" && candidateFileKeys.length) {
                const ruleOnlyCandidates = flattenedP1.filter((item) => {
                    if (usedFlatKeys.has(item.flatKey)) return false;
                    if (!matchesCandidateFileKeys(item.fileKey, candidateFileKeys)) return false;
                    return normalizeP1RuleId(item.violation.rule_id) === effectiveRuleId;
                });
                if (ruleOnlyCandidates.length === 1) {
                    matched = ruleOnlyCandidates;
                    matchedReason = "inferred_rule_only";
                    mappingDiagnostics.reviewed_inferred_match_success_count += 1;
                }
            }
            if (!matched.length && effectiveRuleId !== "UNKNOWN") {
                const targetLine = lineNo > 0 ? lineNo : positiveLineOrZero(block.todo_line);
                const inferredPrefix = p1RulePrefixGroup(effectiveRuleId);
                const proximityCandidates = flattenedP1.filter((item) => {
                    if (usedFlatKeys.has(item.flatKey)) return false;
                    if (!matchesCandidateFileKeys(item.fileKey, candidateFileKeys)) return false;
                    const itemRule = normalizeP1RuleId(item.violation.rule_id);
                    if (itemRule === "UNKNOWN") return false;
                    if (isGroupedRuleConflict(effectiveRuleId, itemRule)) return false;
                    const itemPrefix = p1RulePrefixGroup(itemRule);
                    if (!(itemRule === effectiveRuleId || itemPrefix === inferredPrefix)) return false;
                    const itemLine = positiveLineOrZero(item.violation.line);
                    if (targetLine <= 0 || itemLine <= 0) return false;
                    return Math.abs(itemLine - targetLine) <= 25;
                });
                if (proximityCandidates.length === 1) {
                    matched = proximityCandidates;
                    matchedReason = "inferred_proximity";
                    mappingDiagnostics.reviewed_inferred_match_success_count += 1;
                } else if (proximityCandidates.length > 1) {
                    mappingDiagnostics.reviewed_inferred_match_ambiguous_count += 1;
                }
            }

            if (matched.length) {
                const sortedMatched = sortMatchedItemsByCanonicalFit(matched, effectiveRuleId, lineNo, blockMessage);
                sortedMatched.forEach((item) => usedFlatKeys.add(item.flatKey));
                sortedMatched.forEach((item) => {
                    const violation = item && item.violation && typeof item.violation === "object" ? item.violation : {};
                    if (
                        normalizeReviewedMessageKey(blockMessage)
                        && normalizeReviewedMessageKey(violation.message || "")
                        && normalizeReviewedMessageKey(blockMessage) !== normalizeReviewedMessageKey(violation.message || "")
                    ) {
                        mappingDiagnostics.synced_message_mismatch_count += 1;
                        if (mappingDiagnostics.synced_rule_message_conflict_samples.length < 10) {
                            mappingDiagnostics.synced_rule_message_conflict_samples.push({
                                file: basenamePath(violation.file || reviewedFile),
                                line: positiveLineOrZero(violation.line),
                                rule_id: normalizeP1RuleId(violation.rule_id),
                                violation_message: String(violation.message || ""),
                                reviewed_message: String(blockMessage || ""),
                            });
                        }
                    }
                    rowPlans.push({
                        baseViolation: {
                            ...violation,
                            file: violation.file || reviewedFile,
                            file_path: violation.file_path || violation.file || reviewedFile,
                            object: violation.object || item.rowObject || reviewedFile,
                            message: violation.message || blockMessage,
                            line: positiveLineOrZero(violation.line) || lineNo || positiveLineOrZero(block.todo_line),
                            rule_id: String(violation.rule_id || effectiveRuleId || ruleId || "").trim(),
                            issue_id: String(violation.issue_id || issueId || "").trim(),
                            severity: String(violation.severity || block.severity || "Info").trim() || "Info",
                            _reviewed_todo_line: positiveLineOrZero(block.todo_line),
                            _reviewed_block_indexes: [idx + 1],
                            _reviewed_original_message: blockMessage || "",
                            _matched_group_size: sortedMatched.length,
                            _reviewed_sync_canonical_file_id: item.fileKey,
                        },
                        eventName: item.eventName || "Global",
                        syncState: "synced",
                        originLabel: "mixed",
                        matchedItems: [item],
                        overrideMessage: "",
                        syncReason: matchedReason,
                    });
                    syncedCount += 1;
                });
                return;
            }

            reviewOnlyCount += 1;
            if ((effectiveRuleId || "UNKNOWN") === "UNKNOWN") {
                mappingDiagnostics.reviewed_unknown_after_infer_count += 1;
            }
        });
    }

    const leftoverItems = flattenedP1.filter((item) => !usedFlatKeys.has(item.flatKey));
    leftoverItems.forEach((item) => {
        rowPlans.push({
            baseViolation: {
                ...item.violation,
                file: item.violation.file || item.fileKey,
                file_path: item.violation.file_path || item.violation.file || item.fileKey,
                object: item.violation.object || item.rowObject || item.fileKey,
                line: positiveLineOrZero(item.violation.line),
                rule_id: String(item.violation.rule_id || "").trim(),
                severity: String(item.violation.severity || "Info"),
                _reviewed_sync_canonical_file_id: item.fileKey,
            },
            eventName: item.eventName || "Global",
            syncState: "violation-only",
            originLabel: "p1",
            matchedItems: [item],
            overrideMessage: "",
            syncReason: "violation_only",
        });
    });

    return {
        rowPlans,
        leftoverCount: leftoverItems.length,
        syncedCount,
        reviewOnlyCount,
        mappingDiagnostics,
    };
}

function aiStatusMatchesViolation(statusItem, violation, eventName) {
    if (!statusItem || typeof statusItem !== "object") return false;
    const parentIssueId = String(statusItem.parent_issue_id || "").trim();
    const violationIssueId = String((violation && violation.issue_id) || "").trim();
    if (parentIssueId && violationIssueId && parentIssueId === violationIssueId) return true;
    const parentSource = String(statusItem.parent_source || "").trim().toUpperCase();
    const violationSource = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    if (parentSource && violationSource && parentSource !== violationSource) return false;
    const parentFile = violationCanonicalFileId(statusItem, violationResolvedFile(statusItem));
    const violationFile = violationCanonicalFileId(violation, violationResolvedFile(violation));
    if (parentFile && violationFile && !sameFileIdentity(parentFile, violationFile)) return false;
    const parentRule = String(statusItem.parent_rule_id || "").trim();
    const violationRule = String((violation && violation.rule_id) || "").trim();
    const parentLine = positiveLineOrZero(statusItem.parent_line || 0);
    const violationLine = positiveLineOrZero((violation && violation.line) || 0);
    if (parentRule && violationRule && parentRule === violationRule && parentLine > 0 && violationLine > 0) {
        return Math.abs(parentLine - violationLine) <= 25;
    }
    const parentMessage = messageSearchToken(statusItem.message || "");
    const violationMessage = messageSearchToken((violation && violation.message) || "");
    if (parentRule && violationRule && parentRule === violationRule && parentMessage && violationMessage) {
        return parentMessage === violationMessage;
    }
    if (parentMessage && violationMessage) {
        return parentMessage === violationMessage && String(statusItem.event || "Global") === String(eventName || "Global");
    }
    return false;
}

function isReviewOnlyLikeViolation(violation) {
    const source = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const issueId = String((violation && violation.issue_id) || "").trim().toUpperCase();
    const lineNo = positiveLineOrZero((violation && violation.line) || 0);
    return source === "P1" && (lineNo <= 0 || issueId.startsWith("REVIEW-ONLY-"));
}

function findAiLinkedItemForViolation(items, violation, eventName) {
    const collection = Array.isArray(items) ? items : [];
    const exact = collection.find((item) => aiStatusMatchesViolation(item, violation, eventName)) || null;
    if (exact) return exact;
    if (!isReviewOnlyLikeViolation(violation)) return null;

    const selectedFile = violationCanonicalFileId(violation, violationResolvedFile(violation));
    const selectedSource = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const selectedRule = String((violation && violation.rule_id) || "").trim();
    const selectedEvent = String(eventName || "Global");
    const selectedLine = positiveLineOrZero((violation && violation.line) || 0);
    if (!selectedRule) return null;

    const candidates = collection.filter((item) => {
        if (!item || typeof item !== "object") return false;
        const parentFile = violationCanonicalFileId(item, violationResolvedFile(item));
        if (selectedFile && parentFile && !sameFileIdentity(selectedFile, parentFile)) return false;
        const parentSource = String(item.parent_source || "").trim().toUpperCase();
        if (selectedSource && parentSource && selectedSource !== parentSource) return false;
        const parentRule = String(item.parent_rule_id || "").trim();
        if (!parentRule || parentRule !== selectedRule) return false;
        const parentEvent = String(item.event || "Global");
        if (selectedEvent && parentEvent && selectedEvent !== parentEvent) return false;
        return true;
    });
    if (!candidates.length) return null;
    if (candidates.length === 1) return candidates[0];

    return candidates
        .map((item, idx) => ({ item, idx }))
        .sort((left, right) => {
            const leftLine = positiveLineOrZero(left.item.parent_line || 0);
            const rightLine = positiveLineOrZero(right.item.parent_line || 0);
            const leftHasLine = leftLine > 0 ? 1 : 0;
            const rightHasLine = rightLine > 0 ? 1 : 0;
            if (leftHasLine !== rightHasLine) return rightHasLine - leftHasLine;
            const leftDistance = selectedLine > 0 && leftLine > 0 ? Math.abs(leftLine - selectedLine) : 999999;
            const rightDistance = selectedLine > 0 && rightLine > 0 ? Math.abs(rightLine - selectedLine) : 999999;
            if (leftDistance !== rightDistance) return leftDistance - rightDistance;
            return right.idx - left.idx;
        })[0].item;
}

export function findAiMatchForViolation({ analysisData, violation, eventName }) {
    return findAiLinkedItemForViolation((analysisData && analysisData.violations && analysisData.violations.P3) || [], violation, eventName);
}

export function findAiStatusForViolation({ analysisData, violation, eventName }) {
    return findAiLinkedItemForViolation((analysisData && analysisData.ai_review_statuses) || [], violation, eventName);
}

function aiStatusDisplayLabel(status) {
    const key = String(status || "").trim().toLowerCase();
    if (key === "generated") return "Generated";
    if (key === "failed") return "Generation failed";
    if (key === "skipped") return "Skipped";
    return key || "Unknown";
}

function aiReasonDisplayMeta(reason) {
    const key = String(reason || "").trim();
    if (key === "generated") {
        return {
            title: "AI review was generated for this finding.",
            detail: "A matching P3 review is available for the selected issue.",
            label: "Generated",
        };
    }
    if (key === "mock_generated") {
        return {
            title: "A mock AI review was generated.",
            detail: "Live AI was not used, but a mock review is available for preview.",
            label: "Mock generated",
        };
    }
    if (key === "timeout") {
        return {
            title: "AI review generation timed out.",
            detail: "Live AI did not respond in time, so no P3 review was attached.",
            label: "Timed out",
        };
    }
    if (key === "response_parse_failed") {
        return {
            title: "AI review response could not be parsed.",
            detail: "The AI returned a response, but it was not in a usable format.",
            label: "Parse failed",
        };
    }
    if (key === "fail_soft_skip") {
        return {
            title: "AI review was skipped in fail-soft mode.",
            detail: "Live AI was unavailable, so the app continued without attaching a P3 review.",
            label: "Fail-soft skip",
        };
    }
    if (key === "empty_response") {
        return {
            title: "AI returned an empty response.",
            detail: "No review content was returned for this finding.",
            label: "Empty response",
        };
    }
    if (key === "severity_filtered") {
        return {
            title: "P3 generation was skipped by severity filter.",
            detail: "This issue did not meet the threshold for generating a P3 review.",
            label: "Severity filtered",
        };
    }
    if (key === "priority_limited") {
        return {
            title: "P3 generation was skipped by priority limits.",
            detail: "Another nearby parent review took precedence over this issue.",
            label: "Priority limited",
        };
    }
    return {
        title: "No AI review metadata is available.",
        detail: "A matching P3 status could not be found for this issue.",
        label: key || "Unknown",
    };
}

function collectNearbyP3Candidates({ analysisData, violation, eventName }) {
    const source = String((violation && violation.priority_origin) || "").trim().toUpperCase();
    const selectedRule = String((violation && violation.rule_id) || "").trim();
    const selectedLine = positiveLineOrZero((violation && violation.line) || 0);
    const selectedFile = violationCanonicalFileId(violation, violationResolvedFile(violation));
    const selectedEvent = String(eventName || "Global");
    const candidates = Array.isArray(analysisData && analysisData.violations && analysisData.violations.P3)
        ? analysisData.violations.P3
        : [];
    return candidates.filter((item) => {
        if (!item || typeof item !== "object") return false;
        const parentFile = violationCanonicalFileId(item, violationResolvedFile(item));
        if (selectedFile && parentFile && !sameFileIdentity(selectedFile, parentFile)) return false;
        const parentSource = String(item.parent_source || "").trim().toUpperCase();
        if (source && parentSource && source !== parentSource) return false;
        const parentEvent = String(item.event || "Global");
        if (selectedEvent && parentEvent && selectedEvent !== parentEvent) return false;
        return true;
    }).sort((left, right) => {
        const leftRule = String(left.parent_rule_id || "").trim();
        const rightRule = String(right.parent_rule_id || "").trim();
        const leftLine = positiveLineOrZero(left.parent_line || 0);
        const rightLine = positiveLineOrZero(right.parent_line || 0);
        const leftRuleMatch = leftRule && selectedRule && leftRule === selectedRule ? 0 : 1;
        const rightRuleMatch = rightRule && selectedRule && rightRule === selectedRule ? 0 : 1;
        const leftDistance = selectedLine > 0 && leftLine > 0 ? Math.abs(leftLine - selectedLine) : 999999;
        const rightDistance = selectedLine > 0 && rightLine > 0 ? Math.abs(rightLine - selectedLine) : 999999;
        return leftRuleMatch - rightRuleMatch || leftDistance - rightDistance;
    });
}

export function buildAiUnavailableDiagnostic({ analysisData, violation, eventName, sourceFilterKey }) {
    const aiStatus = findAiStatusForViolation({ analysisData, violation, eventName });
    const nearbyCandidates = collectNearbyP3Candidates({ analysisData, violation, eventName });
    const nearby = nearbyCandidates[0] || null;
    const sourceKey = typeof sourceFilterKey === "function"
        ? sourceFilterKey(violation && violation.priority_origin)
        : String((violation && violation.priority_origin) || "").trim().toLowerCase();
    const status = String((aiStatus && aiStatus.status) || "").trim();
    const reason = String((aiStatus && aiStatus.reason) || "").trim();
    const reasonMeta = aiReasonDisplayMeta(reason);
    let classification = "not_found";
    let classificationLabel = "Not found";
    let matchLabel = "No related P3 item";
    let matchHint = "";

    if (aiStatus) {
        classification = status || "not_found";
        classificationLabel = aiStatusDisplayLabel(status);
        if (status === "generated" && nearby) {
            classification = "not_matched";
            classificationLabel = "Matched elsewhere";
            matchLabel = "P3 was generated but did not exact-match this parent";
            matchHint = `nearest parent_rule_id=${String(nearby.parent_rule_id || "-")}, selected rule_id=${String((violation && violation.rule_id) || "-")}`;
        } else if (status === "generated") {
            matchLabel = "Status is generated but no exact P3 match was found";
        } else {
            matchLabel = "P3 status matched";
        }
    } else if (nearby) {
        classification = "not_matched";
        classificationLabel = "Matched elsewhere";
        matchLabel = "Nearby P3 found for another parent";
        matchHint = `nearest parent_rule_id=${String(nearby.parent_rule_id || "-")}, selected rule_id=${String((violation && violation.rule_id) || "-")}`;
    } else {
        classification = "not_found";
        classificationLabel = "Not found";
        matchLabel = sourceKey === "p2" ? "No related P3 status for this P2 issue" : "No related P3/status match";
    }

    return {
        classification,
        classification_label: classificationLabel,
        status,
        status_label: aiStatusDisplayLabel(status),
        reason,
        reason_label: reasonMeta.label,
        title: reasonMeta.title,
        detail: reasonMeta.detail,
        selected_source: String((violation && violation.priority_origin) || "P1"),
        selected_issue_id: String((violation && violation.issue_id) || "-"),
        selected_rule_id: String((violation && violation.rule_id) || "-"),
        selected_line: positiveLineOrZero((violation && violation.line) || 0) || "-",
        parent_issue_id: String(((aiStatus || nearby || {}).parent_issue_id) || "-"),
        parent_rule_id: String(((aiStatus || nearby || {}).parent_rule_id) || "-"),
        parent_line: positiveLineOrZero(((aiStatus || nearby || {}).parent_line) || 0) || "-",
        selected_cap: positiveLineOrZero(((aiStatus || {}).selected_cap) || 0) || 0,
        selected_rank: positiveLineOrZero(((aiStatus || {}).selected_rank) || 0) || 0,
        match_label: matchLabel,
        match_hint: matchHint,
    };
}

export function describeAiUnavailable({ analysisData, violation, eventName, liveAiEnabled, sourceFilterKey }) {
    const diagnostic = buildAiUnavailableDiagnostic({ analysisData, violation, eventName, sourceFilterKey });
    if (!liveAiEnabled) {
        return {
            title: "AI review is currently disabled.",
            detail: "Enable Live AI to request a P3 review for this finding.",
            diagnostic,
        };
    }
    return {
        title: diagnostic.title,
        detail: diagnostic.detail,
        diagnostic,
    };
}
