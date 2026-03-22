import {
    describeAiUnavailable,
    findAiMatchForViolation,
    reviewHasGroupedExample,
} from "./reviewed-linking.js";
import { getAutofixApplyGate } from "./autofix-ai/quality-gates.js";
import {
    buildAiReviewSummary,
    buildAiSummaryLines,
    buildQualityPreviewSummaryLines,
    formatAutofixValidationSummary,
} from "./autofix-ai/prepare-panel.js";
import {
    buildCompareSummaryLines,
    buildDiffModalMeta,
    buildDiffModalStatusEntries,
} from "./autofix-ai/compare-modal.js";
import { createAutofixUiStateController } from "./autofix-ai/ui-state.js";

export function createAutofixAiController({ dom, state, helpers }) {
    const createEmptyDiffModalContext = () => ({
        beforeRows: null,
        afterRows: null,
        errorMessage: "",
        lineUnresolved: false,
        patchMissing: false,
        prepareFailed: false,
        mockOrLowConfidence: false,
        anchorLine: 0,
    });
    let activeDiffModalKey = "";
    let activeDiffModalBundle = null;
    let activeDiffModalViolation = null;
    let activeDiffModalSelectHandler = null;
    let activeDiffModalEventName = "Global";
    let activeDiffModalView = "split";
    let activeDiffModalContext = createEmptyDiffModalContext();

    const currentAnalysisData = () => state.analysisData || {};
    const findLinkedAiMatch = (violation, eventName) => findAiMatchForViolation({
        analysisData: currentAnalysisData(),
        violation,
        eventName,
    });
    const describeUnavailableAi = (violation, eventName) => describeAiUnavailable({
        analysisData: currentAnalysisData(),
        violation,
        eventName,
        liveAiEnabled: !!(helpers.getAiRequestOptions && helpers.getAiRequestOptions().enableLiveAi),
        sourceFilterKey: helpers.sourceFilterKey,
    });
    const {
        hideAiEmptyState,
        renderAiEmptyState,
        setAiActionHint,
        setAiStatusInline,
        syncAiMoreMenuUi,
    } = createAutofixUiStateController({ dom, state, helpers });

    async function readJsonLikeResponse(response) {
        let payload = {};
        let responseText = "";
        const contentType = String(response.headers.get("content-type") || "").toLowerCase();
        try {
            if (contentType.includes("application/json")) {
                payload = await response.json();
            } else {
                responseText = await response.text();
                try {
                    payload = JSON.parse(responseText);
                } catch (_) {
                    payload = {};
                }
            }
        } catch (_) {
            payload = {};
        }
        return { payload, responseText };
    }

    function applyActiveDiffModalContext(context) {
        const safeContext = context && typeof context === "object" ? context : {};
        activeDiffModalContext = {
            beforeRows: Array.isArray(safeContext.beforeRows) ? safeContext.beforeRows : null,
            afterRows: Array.isArray(safeContext.afterRows) ? safeContext.afterRows : null,
            errorMessage: String(safeContext.errorMessage || ""),
            lineUnresolved: !!safeContext.lineUnresolved,
            patchMissing: !!safeContext.patchMissing,
            prepareFailed: !!safeContext.prepareFailed,
            mockOrLowConfidence: !!safeContext.mockOrLowConfidence,
            anchorLine: helpers.positiveLineOrZero(safeContext.anchorLine || 0),
        };
    }

    function clearAiComparePreview() {
        if (!dom.aiComparePreview) return;
        dom.aiComparePreview.replaceChildren();
        dom.aiComparePreview.style.display = "none";
    }

    function renderAiComparePreview(violation, aiMatch) {
        if (!dom.aiComparePreview || !violation || !aiMatch) return;
        const sourceLabel = helpers.sourceFilterKey((violation && violation.priority_origin) || "P1") === "p2" ? "P2 source" : "P1 source";
        const p3Mode = String((aiMatch && aiMatch.source) || "").trim().toLowerCase() === "mock" ? "Mock P3" : "Live P3";
        const previewHeader = document.createElement("div");
        previewHeader.className = "ai-compare-preview-meta";
        previewHeader.textContent = `${sourceLabel} line ${helpers.positiveLineOrZero((violation && violation.line) || 0) || "-"} <> ${p3Mode}`;
        const issueRows = helpers.buildIssueContextRows(violation, 3);
        const reviewRows = helpers.buildReviewContextRows(aiMatch);
        dom.aiComparePreview.replaceChildren(
            previewHeader,
            helpers.createComparePreviewColumn("Source context", issueRows, "is-source"),
            helpers.createComparePreviewColumn("P3 review", reviewRows, "is-review"),
        );
        dom.aiComparePreview.style.display = "grid";
    }

    function hasAutofixValidationErrors(resultPayload) {
        const validation = (resultPayload && resultPayload.validation) || {};
        const quality = (resultPayload && resultPayload.quality_metrics) || {};
        const validationErrors = Array.isArray(validation.errors) ? validation.errors.filter(Boolean) : [];
        const qualityErrors = Array.isArray(quality.validation_errors) ? quality.validation_errors.filter(Boolean) : [];
        return (validationErrors.length + qualityErrors.length) > 0;
    }

    function renderAiSummaryList(lines) {
        if (!dom.aiSummaryList) return;
        const safeLines = Array.isArray(lines) ? lines.map((line) => String(line || "").trim()).filter(Boolean) : [];
        dom.aiSummaryList.replaceChildren(...safeLines.map((line) => {
            const item = document.createElement("li");
            item.textContent = line;
            return item;
        }));
    }

    function makeAiCardKey(violation, eventName, aiMatch) {
        const fileName = helpers.violationResolvedFile(violation, state.currentViewerFile);
        const objectName = String((violation && violation.object) || (aiMatch && aiMatch.object) || "");
        const evt = String(eventName || (aiMatch && aiMatch.event) || "Global");
        const review = String((aiMatch && aiMatch.review) || "");
        return [fileName, objectName, evt, review].join("||");
    }

    function setAiReviewText(reviewText) {
        const full = String(reviewText || "").trim();
        if (dom.aiText) {
            dom.aiText.textContent = buildAiReviewSummary(full);
        }
        renderAiSummaryList([]);
        if (dom.aiTextFull) {
            dom.aiTextFull.textContent = full;
            dom.aiTextFull.style.display = state.aiReviewExpanded && full ? "block" : "none";
        }
        if (dom.aiReviewToggleBtn) {
            dom.aiReviewToggleBtn.style.display = full ? "inline-block" : "none";
            dom.aiReviewToggleBtn.textContent = state.aiReviewExpanded ? "Hide full review" : "Show full review";
        }
    }

    function setAutofixDiffPanel(diffText) {
        const text = String(diffText || "");
        if (dom.aiDiffText) {
            dom.aiDiffText.textContent = text;
        }
        if (dom.aiDiffPanel) {
            dom.aiDiffPanel.style.display = "none";
        }
        if (dom.diffModalText) {
            dom.diffModalText.textContent = text || "// Source patch diff is not ready yet.";
        }
    }

    function normalizeAutofixBundle(payload) {
        const data = (payload && typeof payload === "object") ? payload : {};
        const rawProposals = Array.isArray(data.proposals) && data.proposals.length ? data.proposals : [data];
        const proposals = rawProposals.filter((item) => item && typeof item === "object" && item.proposal_id);
        const fallbackProposal = proposals[0] || {};
        let selected = String(data.selected_proposal_id || "");
        if (!selected || !proposals.some((item) => String(item.proposal_id) === selected)) {
            const ranked = [...proposals].sort((left, right) => {
                const leftScore = Number.parseInt((((left || {}).compare_score || {}).total || 0), 10) || 0;
                const rightScore = Number.parseInt((((right || {}).compare_score || {}).total || 0), 10) || 0;
                if (rightScore !== leftScore) return rightScore - leftScore;
                const leftLiveLlm = String((left || {}).generator_type || "").toLowerCase() === "llm"
                    && String((left || {}).source || "").toLowerCase() === "live-ai";
                const rightLiveLlm = String((right || {}).generator_type || "").toLowerCase() === "llm"
                    && String((right || {}).source || "").toLowerCase() === "live-ai";
                if (leftLiveLlm !== rightLiveLlm) return rightLiveLlm ? 1 : -1;
                return 0;
            });
            selected = String(((ranked[0] || fallbackProposal).proposal_id) || "");
        }
        return {
            proposals,
            selected_proposal_id: selected,
            active_proposal_id: selected,
            compare_meta: (data.compare_meta && typeof data.compare_meta === "object") ? data.compare_meta : null,
        };
    }

    function getActiveAutofixProposal(bundle) {
        if (!bundle || !Array.isArray(bundle.proposals) || !bundle.proposals.length) return null;
        const activeId = String(bundle.active_proposal_id || bundle.selected_proposal_id || "");
        const found = bundle.proposals.find((item) => String(item.proposal_id) === activeId);
        return found || bundle.proposals[0];
    }

    function renderAutofixComparePanel(bundle, onSelect) {
        if (!dom.aiComparePanel || !dom.aiCompareButtons || !dom.aiCompareMeta) return;
        const proposals = (bundle && Array.isArray(bundle.proposals)) ? bundle.proposals : [];
        if (proposals.length <= 1) {
            dom.aiCompareButtons.innerHTML = "";
            dom.aiCompareMeta.textContent = "";
            dom.aiComparePanel.style.display = "none";
            return;
        }
        dom.aiCompareButtons.innerHTML = "";
        const activeId = String((bundle && bundle.active_proposal_id) || (bundle && bundle.selected_proposal_id) || "");
        proposals.forEach((proposal) => {
            const pid = String((proposal && proposal.proposal_id) || "");
            if (!pid) return;
            const gen = String((proposal && proposal.generator_type) || "unknown").toUpperCase();
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "ai-compare-button";
            const preview = (proposal && typeof proposal.instruction_preview === "object") ? proposal.instruction_preview : {};
            const instructionValid = !!preview.valid;
            const compareScore = (proposal && typeof proposal.compare_score === "object") ? proposal.compare_score : {};
            const totalScore = Number.parseInt(compareScore.total, 10);
            const scoreText = Number.isFinite(totalScore) ? ` (${totalScore})` : "";
            btn.textContent = instructionValid ? `${gen}${scoreText}` : `${gen}!${scoreText}`;
            btn.title = instructionValid
                ? "structured instruction: valid"
                : `structured instruction: invalid (${String((preview.errors || []).join(", ") || "unknown")})`;
            btn.classList.toggle("ai-compare-button-active", pid === activeId);
            btn.onclick = () => {
                if (typeof onSelect === "function") onSelect(pid);
            };
            dom.aiCompareButtons.appendChild(btn);
        });
        const generatedCount = proposals.length;
        const compareMeta = (bundle && bundle.compare_meta && typeof bundle.compare_meta === "object") ? bundle.compare_meta : {};
        const selectionPolicy = String(compareMeta.selection_policy || "").trim();
        const active = proposals.find((item) => String((item && item.proposal_id) || "") === activeId) || proposals[0] || {};
        const activePreview = (active && typeof active.instruction_preview === "object") ? active.instruction_preview : {};
        const activeScore = (active && typeof active.compare_score === "object") ? active.compare_score : {};
        const generatorType = String((active && active.generator_type) || "unknown").toUpperCase();
        const validText = activePreview.valid ? "pass" : "check";
        const totalScore = Number.parseInt(activeScore.total || 0, 10) || 0;
        const selectedReason = helpers.compactUiText(active.selection_reason || compareMeta.selected_selection_reason || "", 84);
        const parts = [
            `Candidates ${generatedCount}`,
            `Selected ${generatorType}`,
            `Validation ${validText}`,
            `Score ${totalScore}`,
        ];
        if (selectionPolicy) parts.push(`Policy ${selectionPolicy}`);
        if (selectedReason) parts.push(selectedReason);
        dom.aiCompareMeta.textContent = parts.join(" | ");
        dom.aiComparePanel.style.display = "block";
    }

    async function prepareAutofixProposal(violation, eventName, aiMatch) {
        const fileName = String((violation && (violation.file_path || violation.file || violation.file_name || violation.filename)) || state.currentViewerFile || "");
        if (!fileName) throw new Error("target file is missing");
        const response = await fetch("/api/autofix/prepare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file: fileName,
                object: String((violation && violation.object) || (aiMatch && aiMatch.object) || ""),
                event: String(eventName || (aiMatch && aiMatch.event) || "Global"),
                review: String((aiMatch && aiMatch.review) || ""),
                issue_id: String((violation && violation.issue_id) || (aiMatch && aiMatch.parent_issue_id) || ""),
                session_id: (state.analysisData && state.analysisData.output_dir) || undefined,
                prepare_mode: "compare",
            }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const err = new Error(payload.error || `autofix prepare failed (${response.status})`);
            err.payload = payload;
            throw err;
        }
        return normalizeAutofixBundle(payload);
    }

    async function applyAutofixProposal(proposal, violation, eventName, aiMatch) {
        const fileName = String((violation && (violation.file_path || violation.file || violation.file_name || violation.filename)) || state.currentViewerFile || "");
        const response = await fetch("/api/autofix/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                proposal_id: String((proposal && proposal.proposal_id) || ""),
                session_id: (state.analysisData && state.analysisData.output_dir) || undefined,
                file: fileName || String((proposal && proposal.file) || ""),
                expected_base_hash: String((proposal && proposal.base_hash) || ""),
                apply_mode: "source_ctl",
                check_ctrlpp_regression: !!(typeof helpers.isCtrlppEnabled === "function" && helpers.isCtrlppEnabled()),
            }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const message = payload.error_code
                ? `${payload.error || "autofix apply failed"} [${payload.error_code}]`
                : (payload.error || `autofix apply failed (${response.status})`);
            const err = new Error(message);
            err.payload = payload;
            throw err;
        }
        return payload;
    }

    async function applyAiSuggestion(violation, eventName, aiMatch) {
        const fileName = helpers.violationResolvedFile(violation, state.currentViewerFile);
        if (!fileName) throw new Error("target file is missing");
        const response = await fetch("/api/ai-review/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                file: fileName,
                object: String((violation && violation.object) || (aiMatch && aiMatch.object) || ""),
                event: String(eventName || (aiMatch && aiMatch.event) || "Global"),
                review: String((aiMatch && aiMatch.review) || ""),
                output_dir: (state.analysisData && state.analysisData.output_dir) || undefined,
            }),
        });
        const { payload, responseText } = await readJsonLikeResponse(response);
        if (!response.ok) {
            throw new Error(payload.error || responseText || `AI review apply failed (${response.status})`);
        }
        return payload;
    }

    async function requestOnDemandAiReview(violation, eventName) {
        if (!violation || typeof violation !== "object") {
            throw new Error("no selected violation");
        }
        const aiOptions = typeof helpers.getAiRequestOptions === "function" ? helpers.getAiRequestOptions() : {};
        const payload = {
            violation: {
                source: String((violation && violation.priority_origin) || "P1"),
                issue_id: String((violation && violation.issue_id) || ""),
                rule_id: String((violation && violation.rule_id) || ""),
                file: String((violation && (violation.file || violation.file_name || "")) || ""),
                file_path: String((violation && (violation.file_path || violation.file || "")) || ""),
                line: helpers.positiveLineOrZero((violation && violation.line) || 0),
                object: String((violation && violation.object) || ""),
                event: String(eventName || violation.event || "Global"),
                severity: String((violation && (violation.severity || violation.type || "")) || ""),
                message: String((violation && violation.message) || ""),
            },
            enable_live_ai: !!aiOptions.enableLiveAi,
            ai_model_name: String(aiOptions.aiModelName || ""),
            ai_with_context: !!aiOptions.aiWithContext,
            session_id: (state.analysisData && state.analysisData.output_dir) || undefined,
        };
        const response = await fetch("/api/ai-review/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const respPayload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(respPayload.error || `additional AI review failed (${response.status})`);
        }
        const reviewItem = respPayload.review_item && typeof respPayload.review_item === "object" ? respPayload.review_item : null;
        const statusItem = respPayload.status_item && typeof respPayload.status_item === "object" ? respPayload.status_item : null;
        if (reviewItem && typeof helpers.upsertAiReview === "function") {
            helpers.upsertAiReview(reviewItem);
        }
        if (statusItem && typeof helpers.upsertAiReviewStatus === "function") {
            helpers.upsertAiReviewStatus(statusItem);
        }
        return respPayload;
    }

    function setDiffModalOpen(open) {
        if (!dom.diffModal) return;
        dom.diffModal.classList.toggle("hidden", !open);
        dom.diffModal.setAttribute("aria-hidden", open ? "false" : "true");
        document.body.classList.toggle("diff-modal-open", !!open);
    }

    function setDiffModalView(view) {
        const normalized = String(view || "split").trim().toLowerCase() === "unified" ? "unified" : "split";
        activeDiffModalView = normalized;
        if (dom.diffModalViewSplit) {
            const active = normalized === "split";
            dom.diffModalViewSplit.classList.toggle("active", active);
            dom.diffModalViewSplit.setAttribute("aria-selected", active ? "true" : "false");
        }
        if (dom.diffModalViewUnified) {
            const active = normalized === "unified";
            dom.diffModalViewUnified.classList.toggle("active", active);
            dom.diffModalViewUnified.setAttribute("aria-selected", active ? "true" : "false");
        }
        if (dom.diffModalSplit) {
            dom.diffModalSplit.classList.toggle("hidden", normalized !== "split");
        }
        if (dom.diffModalText) {
            dom.diffModalText.classList.toggle("hidden", normalized !== "unified");
        }
    }

    function closeDiffModal() {
        activeDiffModalKey = "";
        activeDiffModalBundle = null;
        activeDiffModalViolation = null;
        activeDiffModalSelectHandler = null;
        activeDiffModalEventName = "Global";
        activeDiffModalView = "split";
        activeDiffModalContext = createEmptyDiffModalContext();
        if (dom.diffModalCandidates) dom.diffModalCandidates.replaceChildren();
        if (dom.diffModalSummary) dom.diffModalSummary.replaceChildren();
        if (dom.diffModalMeta) dom.diffModalMeta.replaceChildren();
        if (dom.diffModalBefore) dom.diffModalBefore.replaceChildren();
        if (dom.diffModalAfter) dom.diffModalAfter.replaceChildren();
        if (dom.diffModalText) dom.diffModalText.textContent = "";
        if (dom.diffModalViewUnified) {
            dom.diffModalViewUnified.disabled = false;
            dom.diffModalViewUnified.style.opacity = "1";
            dom.diffModalViewUnified.title = "";
        }
        setDiffModalView("split");
        setDiffModalOpen(false);
    }

    function createDiffPaneLine(lineNo, text, kind) {
        const row = document.createElement("div");
        row.className = `diff-pane-line diff-pane-line-${kind || "context"}`;
        const number = document.createElement("span");
        number.className = "diff-pane-line-number";
        number.textContent = lineNo > 0 ? String(lineNo) : "";
        const content = document.createElement("span");
        content.className = "diff-pane-line-text";
        content.textContent = String(text || "");
        row.append(number, content);
        return row;
    }

    function renderDiffModalSplitView(beforeRows, afterRows) {
        if (!dom.diffModalBefore || !dom.diffModalAfter) return;
        const safeBeforeRows = Array.isArray(beforeRows) && beforeRows.length
            ? beforeRows
            : [{ lineNo: 0, text: "Could not build the before view.", kind: "placeholder" }];
        const safeAfterRows = Array.isArray(afterRows) && afterRows.length
            ? afterRows
            : [{ lineNo: 0, text: "Could not build the after view.", kind: "placeholder" }];
        const makeLine = (lineNo, text, kind) => {
            const row = document.createElement("div");
            row.className = `diff-pane-line diff-pane-line-${kind || "context"}`;
            const number = document.createElement("span");
            number.className = "diff-pane-line-number";
            number.textContent = lineNo > 0 ? String(lineNo) : "";
            const content = document.createElement("span");
            content.className = "diff-pane-line-text";
            content.textContent = String(text || "");
            row.append(number, content);
            return row;
        };
        dom.diffModalBefore.replaceChildren(...safeBeforeRows.map((item) => makeLine(item.lineNo, item.text, item.kind)));
        dom.diffModalAfter.replaceChildren(...safeAfterRows.map((item) => makeLine(item.lineNo, item.text, item.kind)));
    }

    async function buildDiffModalContext(violation, aiMatch, bundle, eventName) {
        const fileName = helpers.violationResolvedFile(violation, helpers.violationResolvedFile(aiMatch, state.currentViewerFile));
        let sourceLines = [];
        let sourceError = "";
        if (fileName) {
            try {
                const sourcePayload = await helpers.fetchFileContentPayload(fileName, { preferSource: true });
                sourceLines = String((sourcePayload && sourcePayload.content) || "").split("\n");
            } catch (err) {
                sourceError = String((err && err.message) || err || "source load failed");
            }
        }
        const targetLine = helpers.resolveDiffAnchorLine(sourceLines, violation, aiMatch, fileName);
        const beforeRows = helpers.buildIssueContextRowsWithLines(
            sourceLines,
            targetLine,
            violation,
            4,
            sourceError,
            { disableMessageEstimate: true },
        );

        let effectiveBundle = bundle || null;
        let afterRows = helpers.buildReviewContextRows(aiMatch);
        let errorMessage = "";
        const reviewCodeBlock = helpers.extractReviewCodeBlock(String((aiMatch && aiMatch.review) || ""));
        const hasCodeBlock = !!reviewCodeBlock;
        const placeholderCodeBlock = hasCodeBlock && helpers.isPlaceholderLikeReviewCode(reviewCodeBlock);
        let prepareAttempted = false;
        let prepareFailed = false;

        if (!hasCodeBlock || placeholderCodeBlock) {
            let activeProposal = getActiveAutofixProposal(effectiveBundle);
            if (!activeProposal || !String(activeProposal.unified_diff || "").trim()) {
                try {
                    prepareAttempted = true;
                    const prepared = await prepareAutofixProposal(violation, eventName, aiMatch);
                    effectiveBundle = prepared || effectiveBundle;
                    activeProposal = getActiveAutofixProposal(effectiveBundle);
                } catch (err) {
                    prepareFailed = true;
                    errorMessage = `Autofix prepare failed: ${String((err && err.message) || err || "autofix prepare failed")}`;
                }
            }
            const proposalAfterRows = helpers.buildAfterRowsFromProposal(getActiveAutofixProposal(effectiveBundle));
            if (proposalAfterRows.length) {
                afterRows = proposalAfterRows;
            } else if (!hasCodeBlock) {
                afterRows = [{
                    lineNo: 0,
                    text: errorMessage || "Source patch diff is not ready yet.",
                    kind: "placeholder",
                }];
            }
        }

        const activeProposal = getActiveAutofixProposal(effectiveBundle);
        const patchMissing = !String((activeProposal && activeProposal.unified_diff) || "").trim();
        const lineUnresolved = !beforeRows.length || beforeRows.some((row) => helpers.positiveLineOrZero(row && row.lineNo) <= 0);

        return {
            bundle: effectiveBundle,
            beforeRows,
            afterRows,
            errorMessage,
            lineUnresolved,
            patchMissing,
            prepareFailed: prepareFailed || (!!prepareAttempted && patchMissing),
            mockOrLowConfidence: String((aiMatch && aiMatch.source) || "").trim().toLowerCase() === "mock",
            anchorLine: helpers.positiveLineOrZero(targetLine),
        };
    }

    function renderDiffModal(bundle, violation, aiMatch, onSelectProposal = null) {
        if (!dom.diffModal || !dom.diffModalText || !dom.diffModalTitle || !dom.diffModalMeta || !dom.diffModalSummary || !dom.diffModalCandidates) return;
        const active = getActiveAutofixProposal(bundle);
        const fileName = helpers.violationDisplayFile(aiMatch, helpers.violationDisplayFile(active, helpers.violationDisplayFile(violation))) || "P3 compare";
        const effectiveRuleId = String((violation && violation.rule_id) || (aiMatch && aiMatch.parent_rule_id) || "").trim();
        const afterTitleNode = dom.diffModalSplit ? dom.diffModalSplit.querySelectorAll(".diff-modal-pane-title")[1] : null;
        dom.diffModalTitle.textContent = `${fileName} P1/P2 <> P3 compare`;
        dom.diffModalMeta.replaceChildren(...buildDiffModalMeta({ violation, aiMatch, proposal: active, helpers }).map((text) => {
            const chip = document.createElement("span");
            chip.className = "diff-modal-meta-chip";
            chip.textContent = text;
            return chip;
        }));
        const summaryLines = buildCompareSummaryLines({ violation, aiMatch, proposal: active, helpers });
        dom.diffModalSummary.replaceChildren(...summaryLines.map((line) => {
            const item = document.createElement("p");
            item.textContent = line;
            return item;
        }));
        appendDiffModalStatusAndActions(violation, aiMatch, active);
        const beforeRows = (activeDiffModalContext && Array.isArray(activeDiffModalContext.beforeRows) && activeDiffModalContext.beforeRows.length)
            ? activeDiffModalContext.beforeRows
            : helpers.buildIssueContextRows(violation, 4);
        const afterRows = (activeDiffModalContext && Array.isArray(activeDiffModalContext.afterRows) && activeDiffModalContext.afterRows.length)
            ? activeDiffModalContext.afterRows
            : helpers.buildReviewContextRows(aiMatch);
        if (afterTitleNode) {
        afterTitleNode.textContent = helpers.isMultiAggregationRule(effectiveRuleId) && reviewHasGroupedExample(effectiveRuleId, (aiMatch && aiMatch.review) || "")
                ? "P3 review (grouped)"
                : "P3 review";
        }
        renderDiffModalSplitView(beforeRows, afterRows);
        const unifiedDiff = String((active && active.unified_diff) || "").trim();
        dom.diffModalText.textContent = unifiedDiff || "// Source patch diff is not ready yet.\n// It will appear after prepare/apply completes.";
        if (dom.diffModalViewUnified) {
            dom.diffModalViewUnified.disabled = !unifiedDiff;
            dom.diffModalViewUnified.style.opacity = unifiedDiff ? "1" : "0.5";
            dom.diffModalViewUnified.title = unifiedDiff ? "" : "Source patch diff is not ready yet.";
        }
        if ((activeDiffModalView || "split") === "unified" && !unifiedDiff) {
            setDiffModalView("split");
        } else {
            setDiffModalView(activeDiffModalView || "split");
        }

        if (activeDiffModalContext && activeDiffModalContext.errorMessage) {
            const warn = document.createElement("p");
            warn.textContent = activeDiffModalContext.errorMessage;
            warn.style.color = "#b71c1c";
            dom.diffModalSummary.appendChild(warn);
        }

        const proposals = (bundle && Array.isArray(bundle.proposals)) ? bundle.proposals : [];
        const proposalsWithDiff = proposals.filter((proposal) => !!String((proposal && proposal.unified_diff) || "").trim());
        if (proposalsWithDiff.length > 1) {
            dom.diffModalCandidates.classList.remove("hidden");
            dom.diffModalCandidates.replaceChildren(...proposalsWithDiff.map((proposal) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "diff-modal-candidate";
                const generatorType = String((proposal && proposal.generator_type) || "unknown").toUpperCase();
                const score = Number.parseInt((proposal && proposal.compare_score && proposal.compare_score.total) || 0, 10) || 0;
                button.textContent = Number.isFinite(score) && score > 0 ? `${generatorType} (${score})` : generatorType;
                button.classList.toggle(
                    "diff-modal-candidate-active",
                    String((proposal && proposal.proposal_id) || "") === String((bundle && bundle.active_proposal_id) || (bundle && bundle.selected_proposal_id) || ""),
                );
                button.onclick = () => {
                    if (!bundle) return;
                    bundle.active_proposal_id = String((proposal && proposal.proposal_id) || "");
                    if (typeof onSelectProposal === "function") {
                        onSelectProposal(bundle.active_proposal_id, bundle);
                        return;
                    }
                    renderDiffModal(bundle, violation, aiMatch, onSelectProposal);
                };
                return button;
            }));
        } else {
            dom.diffModalCandidates.replaceChildren();
            dom.diffModalCandidates.classList.add("hidden");
        }
    }

    async function refreshOpenDiffModal(violation, aiMatch, eventName, fallbackBundle = null) {
        const context = await buildDiffModalContext(violation, aiMatch, fallbackBundle || activeDiffModalBundle, eventName);
        activeDiffModalBundle = context.bundle || fallbackBundle || activeDiffModalBundle;
        applyActiveDiffModalContext(context);
        renderDiffModal(activeDiffModalBundle, violation, aiMatch, activeDiffModalSelectHandler);
    }

    function appendDiffModalStatusAndActions(violation, aiMatch, proposal) {
        if (!dom.diffModalSummary) return;
        const statusEntries = buildDiffModalStatusEntries({ context: activeDiffModalContext, aiMatch, proposal });
        if (statusEntries.length) {
            const statusWrap = document.createElement("div");
            statusWrap.className = "diff-modal-status-list";
            statusEntries.forEach((entry) => {
                const chip = document.createElement("span");
                chip.className = `diff-modal-status-chip diff-modal-status-chip-${entry.tone || "muted"}`;
                chip.textContent = entry.label;
                chip.title = entry.title || entry.label;
                statusWrap.appendChild(chip);
            });
            dom.diffModalSummary.appendChild(statusWrap);
        }

        const actionWrap = document.createElement("div");
        actionWrap.className = "diff-modal-inline-actions";
        const eventName = String(activeDiffModalEventName || "Global");

        if (activeDiffModalContext && activeDiffModalContext.lineUnresolved) {
            const aiBtn = document.createElement("button");
            aiBtn.type = "button";
            aiBtn.className = "diff-modal-inline-button";
            aiBtn.textContent = "Run AI again";
            aiBtn.onclick = async () => {
                aiBtn.disabled = true;
                aiBtn.textContent = "Running AI...";
                try {
                    await requestOnDemandAiReview(violation, eventName);
        const refreshedMatch = findLinkedAiMatch(violation, eventName) || aiMatch;
                    await refreshOpenDiffModal(violation, refreshedMatch, eventName, activeDiffModalBundle);
                } catch (err) {
                    const msg = String((err && err.message) || err || "additional AI review failed");
                    activeDiffModalContext.errorMessage = `Additional AI review failed: ${msg}`;
                    renderDiffModal(activeDiffModalBundle, violation, aiMatch, activeDiffModalSelectHandler);
                }
            };
            actionWrap.appendChild(aiBtn);
        }

        if (!String((proposal && proposal.unified_diff) || "").trim()) {
            const patchBtn = document.createElement("button");
            patchBtn.type = "button";
            patchBtn.className = "diff-modal-inline-button";
            patchBtn.textContent = "Prepare patch";
            patchBtn.onclick = async () => {
                patchBtn.disabled = true;
                patchBtn.textContent = "Preparing...";
                try {
                    const prepared = await prepareAutofixProposal(violation, eventName, aiMatch);
                    activeDiffModalBundle = prepared || activeDiffModalBundle;
        const refreshedMatch = findLinkedAiMatch(violation, eventName) || aiMatch;
                    await refreshOpenDiffModal(violation, refreshedMatch, eventName, activeDiffModalBundle);
                } catch (err) {
                    const msg = String((err && err.message) || err || "patch prepare failed");
                    activeDiffModalContext.errorMessage = `Patch prepare failed: ${msg}`;
                    activeDiffModalContext.prepareFailed = true;
                    renderDiffModal(activeDiffModalBundle, violation, aiMatch, activeDiffModalSelectHandler);
                }
            };
            actionWrap.appendChild(patchBtn);
        }

        if (actionWrap.childElementCount > 0) {
            dom.diffModalSummary.appendChild(actionWrap);
        }
    }

    async function openDiffModal(bundle, violation, aiMatch, eventName = "Global", aiKey = "", onSelectProposal = null) {
        activeDiffModalKey = String(aiKey || "");
        activeDiffModalBundle = bundle || null;
        activeDiffModalViolation = violation || null;
        activeDiffModalSelectHandler = typeof onSelectProposal === "function" ? onSelectProposal : null;
        activeDiffModalEventName = String(eventName || "Global");
        if (!activeDiffModalView) {
            activeDiffModalView = "split";
        }
        activeDiffModalContext = createEmptyDiffModalContext();
        const context = await buildDiffModalContext(violation, aiMatch, bundle, activeDiffModalEventName);
        activeDiffModalBundle = context.bundle || bundle || null;
        applyActiveDiffModalContext(context);
        renderDiffModal(activeDiffModalBundle, violation, aiMatch, onSelectProposal);
        setDiffModalOpen(true);
    }

    function renderP1TriageSection(violation, eventName, options = {}) {
        if (
            !helpers.getP1TriageMeta
            || !helpers.suppressP1Violation
            || !helpers.unsuppressP1Violation
            || !helpers.refreshWorkspaceAfterTriage
        ) {
            return;
        }
        const triageMeta = helpers.getP1TriageMeta(violation);
        const section = document.createElement("section");
        section.className = "triage-section";
        section.setAttribute("data-triage-role", "section");

        const header = document.createElement("div");
        header.className = "triage-section-header";
        const titleWrap = document.createElement("div");
        const title = document.createElement("h4");
        title.className = "triage-section-title";
        title.textContent = "P1 숨김 관리";
        const subtitle = document.createElement("div");
        subtitle.className = "triage-section-subtitle";
        subtitle.textContent = "분석 결과는 유지한 채, 이미 검토한 P1 항목만 기본 보기에서 숨깁니다.";
        titleWrap.append(title, subtitle);

        const statusBadge = document.createElement("span");
        statusBadge.className = `triage-status-badge triage-status-badge-${triageMeta.suppressed ? "suppressed" : "open"}`;
        statusBadge.textContent = triageMeta.suppressed ? "숨김" : "표시 중";
        statusBadge.setAttribute("data-triage-role", "status");
        header.append(titleWrap, statusBadge);
        section.appendChild(header);

        const statusText = document.createElement("p");
        statusText.className = "triage-status-copy";
        statusText.textContent = triageMeta.suppressed
            ? "이 P1 항목은 숨김 처리되어 기본 작업공간 보기에서 제외됩니다."
            : "이 P1 항목은 현재 기본 작업공간 보기에서 표시되고 있습니다.";
        section.appendChild(statusText);

        const form = document.createElement("div");
        form.className = "triage-editor-grid";

        const reasonLabel = document.createElement("label");
        reasonLabel.className = "triage-field";
        const reasonTitle = document.createElement("span");
        reasonTitle.className = "triage-field-label";
        reasonTitle.textContent = "사유";
        const reasonInput = document.createElement("input");
        reasonInput.type = "text";
        reasonInput.className = "triage-input";
        reasonInput.placeholder = "숨김 처리 사유를 입력하세요 (선택)";
        reasonInput.value = triageMeta.reason || "";
        reasonInput.setAttribute("data-triage-role", "reason");
        reasonLabel.append(reasonTitle, reasonInput);

        const noteLabel = document.createElement("label");
        noteLabel.className = "triage-field";
        const noteTitle = document.createElement("span");
        noteTitle.className = "triage-field-label";
        noteTitle.textContent = "메모";
        const noteInput = document.createElement("textarea");
        noteInput.className = "triage-textarea";
        noteInput.rows = 4;
        noteInput.placeholder = "검토 메모를 남길 수 있습니다 (선택)";
        noteInput.value = triageMeta.note || "";
        noteInput.setAttribute("data-triage-role", "note");
        noteLabel.append(noteTitle, noteInput);

        form.append(reasonLabel, noteLabel);
        section.appendChild(form);

        const feedback = document.createElement("div");
        feedback.className = "triage-feedback";
        feedback.setAttribute("data-triage-role", "feedback");
        section.appendChild(feedback);

        const actions = document.createElement("div");
        actions.className = "triage-actions";
        const suppressBtn = document.createElement("button");
        suppressBtn.type = "button";
        suppressBtn.textContent = triageMeta.suppressed ? "숨김 정보 저장" : "숨김 처리";
        suppressBtn.setAttribute("data-triage-role", "suppress");
        actions.appendChild(suppressBtn);

        let unsuppressBtn = null;
        if (triageMeta.suppressed) {
            unsuppressBtn = document.createElement("button");
            unsuppressBtn.type = "button";
            unsuppressBtn.className = "triage-secondary-button";
            unsuppressBtn.textContent = "숨김 해제";
            unsuppressBtn.setAttribute("data-triage-role", "unsuppress");
            actions.appendChild(unsuppressBtn);
        }
        section.appendChild(actions);

        const setBusy = (busy, message = "", tone = "") => {
            suppressBtn.disabled = busy;
            if (unsuppressBtn) unsuppressBtn.disabled = busy;
            reasonInput.disabled = busy;
            noteInput.disabled = busy;
            feedback.textContent = message;
            feedback.className = tone ? `triage-feedback triage-feedback-${tone}` : "triage-feedback";
        };

        suppressBtn.onclick = async () => {
            setBusy(true, "숨김 상태를 저장하는 중...", "pending");
            try {
                await helpers.suppressP1Violation(violation, {
                    reason: reasonInput.value,
                    note: noteInput.value,
                });
                helpers.refreshWorkspaceAfterTriage();
                if (state.showSuppressedP1) {
                    showDetail(violation, eventName, options);
                }
            } catch (err) {
                setBusy(false, `숨김 처리에 실패했습니다: ${(err && err.message) || String(err)}`, "error");
            }
        };

        if (unsuppressBtn) {
            unsuppressBtn.onclick = async () => {
                setBusy(true, "숨김 상태를 해제하는 중...", "pending");
                try {
                    await helpers.unsuppressP1Violation(violation);
                    helpers.refreshWorkspaceAfterTriage();
                    showDetail(violation, eventName, options);
                } catch (err) {
                    setBusy(false, `숨김 해제에 실패했습니다: ${(err && err.message) || String(err)}`, "error");
                }
            };
        }

        dom.violationDetail.appendChild(section);
    }

    function showDetail(violation, eventName, options = {}) {
        dom.violationDetail.replaceChildren();
        helpers.renderInspectorSelectionMeta(violation, options);
        const detailSourceKey = helpers.sourceFilterKey(violation.priority_origin || "P1");
        const divider = document.createElement("div");
        divider.className = "detail-divider";
        dom.violationDetail.appendChild(divider);
        if (detailSourceKey === "p2") {
            helpers.renderDetailDescriptionBlocks(dom.violationDetail, helpers.buildP2DetailBlocks(violation));
        } else if (detailSourceKey === "p1") {
            helpers.renderDetailDescriptionBlocks(dom.violationDetail, helpers.buildP1DetailBlocks(violation));
            renderP1TriageSection(violation, eventName, options);
        } else {
            const desc = document.createElement("p");
            const descLabel = document.createElement("strong");
            descLabel.textContent = "Message:";
            desc.append(descLabel, ` ${violation.message || ""}`);
            dom.violationDetail.appendChild(desc);
        }
        if (typeof helpers.renderDetailEvidence === "function") {
            helpers.renderDetailEvidence(dom.violationDetail, violation);
        }

        const jumpMsg = helpers.jumpFailureMessage(options && options.jumpResult);
        if (jumpMsg) {
            helpers.appendDetailNote(dom.violationDetail, jumpMsg, "detail-note-warning");
        }

        const aiMatch = findLinkedAiMatch(violation, eventName);
        const aiStatus = String((aiMatch && aiMatch.status) || "Pending");
        const hasAiSuggestion = !!(aiMatch && aiStatus !== "Ignored");
        const sourceKey = helpers.sourceFilterKey(violation.priority_origin || "P1");
        const canShowAiPanel = sourceKey === "p1" || sourceKey === "p2";
        helpers.resetInspectorTabsForViolation({ hasAiSuggestion: hasAiSuggestion || canShowAiPanel, preferAi: state.activeInspectorTab === "ai" });

        if (hasAiSuggestion) {
            hideAiEmptyState();
            dom.aiCard.style.display = "block";
            state.aiReviewExpanded = false;
            setAiReviewText(aiMatch.review);
            const btnAiAccept = document.getElementById("btn-ai-accept");
            const btnAiDiff = document.getElementById("btn-ai-diff");
            const btnAiGenerate = document.getElementById("btn-ai-generate");
            const btnAiSourceApply = document.getElementById("btn-ai-source-apply");
            const btnAiIgnore = document.getElementById("btn-ai-ignore");
            const btnAiMoreLocal = document.getElementById("btn-ai-more");
            const aiKey = makeAiCardKey(violation, eventName, aiMatch);
            dom.aiCard.dataset.aiKey = aiKey;
            if (activeDiffModalKey && activeDiffModalKey !== aiKey) {
                closeDiffModal();
            }
            state.aiMoreMenuOpen = false;
            syncAiMoreMenuUi();

            const handleProposalSelect = (proposalId, explicitBundle = null) => {
                const latestBundle = explicitBundle || state.autofixProposalCache.get(aiKey) || null;
                if (!latestBundle || !Array.isArray(latestBundle.proposals)) return;
                latestBundle.active_proposal_id = String(proposalId || "");
                state.autofixProposalCache.set(aiKey, latestBundle);
                const active = getActiveAutofixProposal(latestBundle);
                const gen = String((active && active.generator_type) || "unknown").toUpperCase();
                const score = Number.parseInt((active && active.compare_score && active.compare_score.total) || 0, 10) || 0;
                syncAiPanel(latestBundle, `Selected proposal ${gen} | score ${score}`, "#1565c0");
            };

            const syncAiPanel = (bundle = null, statusMessage = null, statusColor = "") => {
                const activeProposal = getActiveAutofixProposal(bundle);
                const applyGate = getAutofixApplyGate(activeProposal);
                const accepted = String((aiMatch && aiMatch.status) || "Pending") === "Accepted";
                const aiSource = String((aiMatch && aiMatch.source) || "").trim().toLowerCase();
                const effectiveRuleId = String((violation && violation.rule_id) || (aiMatch && aiMatch.parent_rule_id) || "").trim();
        const hasGroupedExample = reviewHasGroupedExample(effectiveRuleId, (aiMatch && aiMatch.review) || "");
                const baseStatusMessage = aiSource === "mock" ? "Mock review suggestion | not real Live AI" : "Live P3 review suggestion";
                renderAiSummaryList(buildAiSummaryLines({
                    violation,
                    aiMatch,
                    proposal: activeProposal,
                    helpers,
                    reviewHasGroupedExample,
                }));
                renderAiComparePreview(violation, aiMatch);
                setAutofixDiffPanel(activeProposal ? activeProposal.unified_diff : "");
                helpers.setAutofixValidationPanel(
                    activeProposal ? formatAutofixValidationSummary(activeProposal) : "",
                    { ok: activeProposal ? (!hasAutofixValidationErrors(activeProposal) && applyGate.canApply) : true },
                );
                renderAutofixComparePanel(bundle, (proposalId) => handleProposalSelect(proposalId));
                if (activeDiffModalKey === aiKey) {
                    renderDiffModal(bundle, violation, aiMatch, (proposalId, selectedBundle) => handleProposalSelect(proposalId, selectedBundle));
                }
                if (btnAiAccept) {
                    btnAiAccept.disabled = accepted;
                    btnAiAccept.textContent = accepted ? "REVIEWED applied" : "Apply REVIEWED";
                    btnAiAccept.style.opacity = accepted ? "0.7" : "1";
                }
                if (btnAiDiff) {
                    btnAiDiff.disabled = false;
                    btnAiDiff.textContent = "P1/P2 <> P3 Compare";
                    btnAiDiff.style.opacity = "1";
                }
                if (btnAiGenerate) {
                    btnAiGenerate.disabled = false;
                    btnAiGenerate.textContent = "Generate AI Review";
                    btnAiGenerate.style.opacity = "1";
                }
                if (btnAiSourceApply) {
                    const applyEnabled = !accepted && !!activeProposal && applyGate.canApply;
                    btnAiSourceApply.disabled = !applyEnabled;
                    btnAiSourceApply.textContent = accepted ? "Source applied" : (applyGate.canApply ? "Apply source" : "Apply blocked");
                    btnAiSourceApply.style.opacity = applyEnabled ? "1" : "0.7";
                    const blockedHint = applyGate.canApply
                        ? ""
                        : `${applyGate.blockedReasonDetail || applyGate.blockedReason}${applyGate.blockedReasonCodes && applyGate.blockedReasonCodes.length ? ` [${applyGate.blockedReasonCodes.join(", ")}]` : ""}`;
                    btnAiSourceApply.title = applyGate.canApply ? "" : `Blocked: ${blockedHint}`;
                }
                if (btnAiIgnore) {
                    btnAiIgnore.disabled = accepted;
                    btnAiIgnore.style.display = "inline-flex";
                    btnAiIgnore.style.opacity = accepted ? "0.7" : "1";
                }
                if (btnAiMoreLocal) {
                    btnAiMoreLocal.disabled = false;
                    btnAiMoreLocal.style.opacity = "1";
                }
                if (statusMessage === null) {
                    setAiStatusInline(
                        accepted ? `${baseStatusMessage} | REVIEWED applied` : baseStatusMessage,
                        accepted ? "#2e7d32" : aiSource === "mock" ? "#8a5b00" : "#1565c0",
                    );
                } else {
                    setAiStatusInline(statusMessage, statusColor || "");
                }
                if (helpers.isMultiAggregationRule(effectiveRuleId) && !hasGroupedExample) {
                    setAiActionHint("This multi-aggregation rule does not yet show grouped evidence in the review text. Generate a fresh AI review before applying changes.", "warn");
                } else if (helpers.isMultiAggregationRule(effectiveRuleId) && hasGroupedExample) {
                    setAiActionHint("Grouped evidence is present in the review text. You can compare candidates and apply the suggestion with more confidence.", "ok");
                } else if (activeProposal && !applyGate.canApply) {
                    const blockedHint = `${applyGate.blockedReasonDetail || applyGate.blockedReason}${applyGate.blockedReasonCodes && applyGate.blockedReasonCodes.length ? ` [${applyGate.blockedReasonCodes.join(", ")}]` : ""}`;
                    setAiActionHint(`Source apply blocked: ${blockedHint}`, "warn");
                } else {
                    setAiActionHint("");
                }
            };

            const cachedAutofixBundle = state.autofixProposalCache.get(aiKey) || null;
            syncAiPanel(cachedAutofixBundle);

            if (btnAiMoreLocal) {
                btnAiMoreLocal.onclick = () => {
                    state.aiMoreMenuOpen = !state.aiMoreMenuOpen;
                    syncAiMoreMenuUi();
                };
            }

            if (btnAiDiff) {
                btnAiDiff.onclick = async () => {
                    const bundle = state.autofixProposalCache.get(aiKey) || null;
                    await openDiffModal(bundle, violation, aiMatch, eventName || "Global", aiKey, (proposalId, selectedBundle) => handleProposalSelect(proposalId, selectedBundle));
                };
            }

            if (btnAiGenerate) {
                btnAiGenerate.onclick = async () => {
                    btnAiGenerate.disabled = true;
                    btnAiGenerate.textContent = "Generating AI review...";
                    if (btnAiDiff) btnAiDiff.disabled = true;
                    if (btnAiSourceApply) btnAiSourceApply.disabled = true;
                    if (btnAiAccept) btnAiAccept.disabled = true;
                    if (btnAiIgnore) btnAiIgnore.disabled = true;
                    setAiStatusInline("Requesting an additional AI review. This may take a few seconds.", "#556070");
                    try {
                        const generated = await requestOnDemandAiReview(violation, eventName);
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        const statusItem = (generated && generated.status_item) || {};
                        if (generated && generated.review_item) {
                            setAiStatusInline("AI review generated.", "#2e7d32");
                        } else {
                            setAiStatusInline(String((generated && generated.message) || statusItem.detail || "The additional AI review completed, but no new review text was returned."), "#8a5b00");
                        }
                        showDetail(violation, eventName, options);
                    } catch (err) {
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        const msg = String((err && err.message) || err || "AI review generation failed");
                        setAiStatusInline(`AI review generation failed: ${msg}`, "#c62828");
                        syncAiPanel(state.autofixProposalCache.get(aiKey) || null, `AI review generation failed: ${msg}`, "#c62828");
                    }
                };
            }

            if (btnAiSourceApply) {
                btnAiSourceApply.onclick = async () => {
                    let bundle = state.autofixProposalCache.get(aiKey) || null;
                    let proposal = getActiveAutofixProposal(bundle);
                    btnAiSourceApply.disabled = true;
                    btnAiSourceApply.textContent = "Applying source...";
                    if (btnAiDiff) btnAiDiff.disabled = true;
                    if (btnAiAccept) btnAiAccept.disabled = true;
                    if (btnAiIgnore) btnAiIgnore.disabled = true;
                    setAiStatusInline("Preparing and applying the source proposal. This may take a few seconds.", "#556070");
                    try {
                        if (!proposal) {
                            bundle = await prepareAutofixProposal(violation, eventName, aiMatch);
                            if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                            state.autofixProposalCache.set(aiKey, bundle);
                            proposal = getActiveAutofixProposal(bundle);
                        }
                        if (!proposal) throw new Error("autofix proposal is missing");
                        const applyGate = getAutofixApplyGate(proposal);
                        if (!applyGate.canApply) {
                            const blockedHint = `${applyGate.blockedReasonDetail || applyGate.blockedReason}${applyGate.blockedReasonCodes && applyGate.blockedReasonCodes.length ? ` [${applyGate.blockedReasonCodes.join(", ")}]` : ""}`;
                            syncAiPanel(bundle, `Source apply blocked: ${blockedHint}`, "#8a5b00");
                            return;
                        }
                        const result = await applyAutofixProposal(proposal, violation, eventName, aiMatch);
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        const mergedProposal = { ...(proposal || {}), ...(result || {}) };
                        let mergedBundle = bundle;
                        if (mergedBundle && Array.isArray(mergedBundle.proposals)) {
                            mergedBundle.proposals = mergedBundle.proposals.map((item) =>
                                String(item.proposal_id) === String(mergedProposal.proposal_id) ? mergedProposal : item
                            );
                        } else {
                            mergedBundle = normalizeAutofixBundle(mergedProposal);
                        }
                        state.autofixProposalCache.set(aiKey, mergedBundle);
                        aiMatch.status = "Accepted";
                        syncAiPanel(mergedBundle, "Source proposal applied.", "#2e7d32");
                        const resultFile = helpers.violationResolvedFile(result, proposal && proposal.file);
                        if (resultFile && helpers.sameFileIdentity(state.currentViewerFile, resultFile)) {
                            try {
                                await helpers.loadCodeViewer(resultFile || state.currentViewerFile, { preferSource: true });
                            } catch (_) {
                                // fail-soft
                            }
                        }
                    } catch (err) {
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        const msg = String((err && err.message) || err || "autofix apply failed");
                        const payload = (err && err.payload) || {};
                        const validationSummary = formatAutofixValidationSummary(payload);
                        syncAiPanel(state.autofixProposalCache.get(aiKey) || bundle, `Source apply failed: ${msg}`, "#c62828");
                        helpers.setAutofixValidationPanel(validationSummary || msg, { ok: false });
                    }
                };
            }

            if (btnAiAccept) {
                btnAiAccept.onclick = async () => {
                    btnAiAccept.disabled = true;
                    btnAiAccept.textContent = "Applying REVIEWED...";
                    if (btnAiSourceApply) btnAiSourceApply.disabled = true;
                    if (btnAiDiff) btnAiDiff.disabled = true;
                    if (btnAiIgnore) btnAiIgnore.disabled = true;
                    setAiStatusInline("Applying the REVIEWED blocks. This may take a few seconds.", "#556070");
                    try {
                        const result = await applyAiSuggestion(violation, eventName, aiMatch);
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        aiMatch.status = "Accepted";
                        const appliedBlocks = helpers.positiveLineOrZero(result && result.applied_blocks);
                        syncAiPanel(
                            state.autofixProposalCache.get(aiKey) || null,
                            appliedBlocks > 0 ? `REVIEWED applied | blocks ${appliedBlocks}` : "REVIEWED applied",
                            "#2e7d32",
                        );
                        const resultFile = helpers.violationResolvedFile(result, helpers.violationResolvedFile(violation));
                        if (resultFile && helpers.sameFileIdentity(state.currentViewerFile, resultFile)) {
                            try {
                                await helpers.loadCodeViewer(resultFile || state.currentViewerFile);
                            } catch (_) {
                                // fail-soft
                            }
                        }
                    } catch (err) {
                        if ((dom.aiCard.dataset.aiKey || "") !== aiKey) return;
                        const msg = String((err && err.message) || err || "AI review apply failed");
                        syncAiPanel(state.autofixProposalCache.get(aiKey) || null, `REVIEWED apply failed: ${msg}`, "#c62828");
                    }
                };
            }
            if (btnAiIgnore) {
                btnAiIgnore.onclick = () => {
                    aiMatch.status = "Ignored";
                    dom.aiCard.style.display = "none";
                    dom.aiCard.dataset.aiKey = "";
                    state.aiMoreMenuOpen = false;
                    syncAiMoreMenuUi();
                    closeDiffModal();
                    helpers.setInspectorTab("detail", false);
                    setAiStatusInline("");
                    setAutofixDiffPanel("");
                    helpers.setAutofixValidationPanel("");
                };
            }
            return;
        }

        state.aiReviewExpanded = false;
        state.aiMoreMenuOpen = false;
        syncAiMoreMenuUi();
        closeDiffModal();
        setAiReviewText("");
        setAiStatusInline("");
        setAiActionHint("");
        clearAiComparePreview();
        setAutofixDiffPanel("");
        helpers.setAutofixValidationPanel("");
        if (canShowAiPanel) {
        const empty = describeUnavailableAi(violation, eventName);
            renderAiEmptyState(empty.title, empty.detail, empty.diagnostic || null);
            const btnAiGenerateEmpty = document.getElementById("btn-ai-generate-empty");
            if (btnAiGenerateEmpty) {
                btnAiGenerateEmpty.onclick = async () => {
                    btnAiGenerateEmpty.disabled = true;
                    btnAiGenerateEmpty.textContent = "Generating AI review...";
                    try {
                        const generated = await requestOnDemandAiReview(violation, eventName);
                        const statusItem = (generated && generated.status_item) || {};
                        if (generated && generated.review_item) {
                            setAiStatusInline("AI review generated.", "#2e7d32");
                        } else {
                            setAiStatusInline(String((generated && generated.message) || statusItem.detail || "The AI review request completed, but no review text was returned."), "#8a5b00");
                        }
                        showDetail(violation, eventName, options);
                    } catch (err) {
                        const msg = String((err && err.message) || err || "AI review generation failed");
                        setAiStatusInline(`AI review generation failed: ${msg}`, "#c62828");
                        btnAiGenerateEmpty.disabled = false;
                        btnAiGenerateEmpty.textContent = "Generate AI Review";
                    }
                };
            }
        } else {
            hideAiEmptyState();
            if (dom.aiCard) {
                dom.aiCard.style.display = "none";
                dom.aiCard.dataset.aiKey = "";
            }
        }
    }

    return {
        applyAiSuggestion,
        applyAutofixProposal,
        buildAiReviewSummary,
        buildAiSummaryLines,
        clearAiComparePreview,
        closeDiffModal,
        formatAutofixValidationSummary,
        getAutofixApplyGate,
        getActiveAutofixProposal,
        hasAutofixValidationErrors,
        hideAiEmptyState,
        makeAiCardKey,
        normalizeAutofixBundle,
        openDiffModal,
        prepareAutofixProposal,
        renderAiComparePreview,
        renderAiEmptyState,
        renderAiSummaryList,
        renderAutofixComparePanel,
        requestOnDemandAiReview,
        setAutofixDiffPanel,
        setAiActionHint,
        setDiffModalView,
        setAiReviewText,
        setAiStatusInline,
        showDetail,
        syncAiMoreMenuUi,
    };
}
