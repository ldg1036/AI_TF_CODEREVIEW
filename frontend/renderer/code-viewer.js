import {
    basenamePath,
    buildFunctionScopes,
    canonicalFileId,
    findScopeForLine,
    fileDescriptorFor,
    inferRuleIdFromReviewedBlock,
    messageSearchToken,
    normalizeP1RuleId,
    normalizeReviewedMessageKey,
    parseReviewedTodoBlocks,
    positiveLineOrZero,
    violationCanonicalFileId,
} from "./utils.js";

export function createCodeViewerController({ dom, state, caches, virtualState, helpers }) {
    const FULL_RENDER_LINE_THRESHOLD = 320;
    function currentViewerLineCount() {
        if (!state.currentViewerContent) return 0;
        return String(state.currentViewerContent).split("\n").length;
    }

    function setCodeViewerText(text) {
        if (!dom.codeViewer) return;
        dom.codeViewer.textContent = text || "";
        state.currentViewerLines = [];
        state.currentHighlightedLine = null;
        state.currentHighlightedLineNear = false;
        virtualState.codeViewerVirtualState.headerEl = null;
        virtualState.codeViewerVirtualState.linesWrap = null;
        virtualState.codeViewerVirtualState.topSpacer = null;
        virtualState.codeViewerVirtualState.visibleHost = null;
        virtualState.codeViewerVirtualState.bottomSpacer = null;
        virtualState.codeViewerVirtualState.renderedStart = -1;
        virtualState.codeViewerVirtualState.renderedEnd = -1;
    }

    function attachCodeViewerVirtualScrollHandler() {
        if (!dom.codeViewer || virtualState.codeViewerVirtualState.scrollHandlerAttached) return;
        dom.codeViewer.addEventListener("scroll", () => {
            queueCodeViewerWindowRender();
        });
        dom.codeViewer.addEventListener("wheel", (event) => {
            event.stopPropagation();
        }, { passive: true });
        virtualState.codeViewerVirtualState.scrollHandlerAttached = true;
    }

    function createCodeLineRow(lineNo, lineText) {
        const lineRow = document.createElement("div");
        lineRow.className = "code-line";
        lineRow.dataset.line = String(lineNo);

        const gutter = document.createElement("span");
        gutter.className = "code-line-no";
        gutter.textContent = String(lineNo);

        const text = document.createElement("span");
        text.className = "code-line-text";
        if (lineText && lineText.length) {
            text.textContent = lineText;
        } else {
            text.textContent = "·";
            text.classList.add("code-line-text-empty");
            text.setAttribute("aria-label", "empty line");
        }

        lineRow.appendChild(gutter);
        lineRow.appendChild(text);
        return lineRow;
    }

    function getCodeViewerLineAreaOffset() {
        if (!dom.codeViewer || !virtualState.codeViewerVirtualState.linesWrap) return 0;
        return Math.max(0, virtualState.codeViewerVirtualState.linesWrap.offsetTop || 0);
    }

    function queueCodeViewerWindowRender(force = false) {
        if (!dom.codeViewer || !virtualState.codeViewerVirtualState.visibleHost) return;
        if (force) {
            virtualState.codeViewerVirtualState.renderedStart = -1;
            virtualState.codeViewerVirtualState.renderedEnd = -1;
        }
        if (virtualState.codeViewerWindowRenderQueued) return;
        virtualState.codeViewerWindowRenderQueued = true;
        window.requestAnimationFrame(() => {
            virtualState.codeViewerWindowRenderQueued = false;
            renderCodeViewerWindow();
        });
    }

    function renderCodeViewerWindow() {
        if (!dom.codeViewer) return;
        const lines = state.currentViewerLines || [];
        const totalLines = lines.length;
        const {
            topSpacer, visibleHost, bottomSpacer,
        } = virtualState.codeViewerVirtualState;
        if (!topSpacer || !visibleHost || !bottomSpacer) return;

        if (totalLines <= 0) {
            topSpacer.style.height = "0px";
            bottomSpacer.style.height = "0px";
            visibleHost.replaceChildren();
            virtualState.codeViewerVirtualState.renderedStart = 0;
            virtualState.codeViewerVirtualState.renderedEnd = 0;
            return;
        }

        const headerOffset = Number.isFinite(getCodeViewerLineAreaOffset()) ? getCodeViewerLineAreaOffset() : 0;
        let lineHeight = Math.max(16, getViewerLineHeight());
        if (!Number.isFinite(lineHeight) || lineHeight <= 0) {
            lineHeight = 20;
        }
        virtualState.codeViewerVirtualState.lineHeight = lineHeight;
        const rawViewportHeight = Number.parseInt(dom.codeViewer.clientHeight, 10) || 1;
        const viewportHeight = Math.max(1, rawViewportHeight - headerOffset);
        const scrollTop = Math.max(0, (dom.codeViewer.scrollTop || 0) - headerOffset);
        const overscan = 14;
        const visibleCount = Math.max(1, Math.ceil(viewportHeight / lineHeight));
        const bufferedCount = visibleCount + overscan * 2;
        const shouldVirtualize = totalLines > FULL_RENDER_LINE_THRESHOLD && totalLines > bufferedCount;
        let start = 0;
        let end = totalLines;
        if (shouldVirtualize) {
            start = Math.floor(scrollTop / lineHeight) - overscan;
            if (!Number.isFinite(start) || start < 0) start = 0;
            end = Math.min(totalLines, start + bufferedCount);
            if (!Number.isFinite(end) || end <= start) {
                start = 0;
                end = Math.min(totalLines, bufferedCount);
            }
            if (end >= totalLines) {
                end = totalLines;
                start = Math.max(0, totalLines - bufferedCount);
            }
            if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start) {
                start = 0;
                end = totalLines;
            }
        }

        if (
            start === virtualState.codeViewerVirtualState.renderedStart
            && end === virtualState.codeViewerVirtualState.renderedEnd
        ) {
            return;
        }

        virtualState.codeViewerVirtualState.renderedStart = start;
        virtualState.codeViewerVirtualState.renderedEnd = end;

        topSpacer.style.height = shouldVirtualize ? `${start * lineHeight}px` : "0px";
        bottomSpacer.style.height = shouldVirtualize ? `${Math.max(0, totalLines - end) * lineHeight}px` : "0px";

        const frag = document.createDocumentFragment();
        for (let idx = start; idx < end; idx += 1) {
            const lineNo = idx + 1;
            const row = createCodeLineRow(lineNo, lines[idx]);
            if (state.currentHighlightedLine === lineNo) {
                row.classList.add(state.currentHighlightedLineNear ? "line-highlight-near" : "line-highlight");
            }
            frag.appendChild(row);
        }
        visibleHost.replaceChildren(frag);

        const renderedRow = visibleHost.querySelector(".code-line");
        if (renderedRow) {
            const measured = renderedRow.getBoundingClientRect().height;
            if (Number.isFinite(measured) && measured > 0 && Math.abs(measured - lineHeight) > 1) {
                virtualState.codeViewerVirtualState.lineHeight = measured;
                virtualState.codeViewerVirtualState.renderedStart = -1;
                virtualState.codeViewerVirtualState.renderedEnd = -1;
                queueCodeViewerWindowRender(true);
            }
        }
    }

    function renderCodeViewerContent(header, content) {
        if (!dom.codeViewer) return;
        attachCodeViewerVirtualScrollHandler();
        dom.codeViewer.replaceChildren();
        state.currentViewerLines = String(content || "").split("\n");

        let headerEl = null;
        if (header) {
            headerEl = document.createElement("div");
            headerEl.className = "code-viewer-header";
            const eyebrowEl = document.createElement("div");
            eyebrowEl.className = "code-viewer-header-eyebrow";
            eyebrowEl.textContent = "Code Context";
            const titleEl = document.createElement("div");
            titleEl.className = "code-viewer-header-title";
            const subtitleEl = document.createElement("div");
            subtitleEl.className = "code-viewer-header-subtitle";
            const metaEl = document.createElement("div");
            metaEl.className = "code-viewer-header-meta";
            const legacyEl = document.createElement("div");
            legacyEl.className = "code-viewer-header-legacy";
            legacyEl.textContent = header;
            headerEl.append(eyebrowEl, titleEl, subtitleEl, metaEl, legacyEl);
            dom.codeViewer.appendChild(headerEl);
        }

        const linesWrap = document.createElement("div");
        linesWrap.className = "code-lines";

        const topSpacer = document.createElement("div");
        topSpacer.className = "code-line-spacer";
        const visibleHost = document.createElement("div");
        visibleHost.className = "code-lines-window";
        const bottomSpacer = document.createElement("div");
        bottomSpacer.className = "code-line-spacer";

        linesWrap.appendChild(topSpacer);
        linesWrap.appendChild(visibleHost);
        linesWrap.appendChild(bottomSpacer);
        dom.codeViewer.appendChild(linesWrap);

        virtualState.codeViewerVirtualState.headerEl = headerEl;
        virtualState.codeViewerVirtualState.linesWrap = linesWrap;
        virtualState.codeViewerVirtualState.topSpacer = topSpacer;
        virtualState.codeViewerVirtualState.visibleHost = visibleHost;
        virtualState.codeViewerVirtualState.bottomSpacer = bottomSpacer;
        virtualState.codeViewerVirtualState.renderedStart = -1;
        virtualState.codeViewerVirtualState.renderedEnd = -1;

        state.currentHighlightedLine = null;
        state.currentHighlightedLineNear = false;
        dom.codeViewer.scrollTop = 0;
        updateCodeViewerHeaderMeta();
        queueCodeViewerWindowRender(true);
    }

    function cacheFunctionScopesForFile(fileName, content) {
        const key = canonicalFileId(fileName);
        if (!key) return;
        const scopes = buildFunctionScopes(String(content || "").split("\n"));
        caches.functionScopeCacheByFile.set(key, scopes);
    }

    function getFunctionScopeFor(fileName, lineNo) {
        const key = canonicalFileId(fileName);
        if (!key) return null;
        return findScopeForLine(caches.functionScopeCacheByFile.get(key) || [], lineNo);
    }

    function resolveFunctionScopeForViolation(fileName, lineNo) {
        const scope = getFunctionScopeFor(fileName, lineNo);
        if (!scope) return { name: "Global", start: 0, end: 0 };
        return scope;
    }

    function resolveReviewedJumpLineFromCache(fileName, violation) {
        const reviewedFile = violationCanonicalFileId(violation, fileName || (violation && (violation.file || violation.object)) || "");
        if (!reviewedFile) return 0;
        const blocks = caches.reviewedTodoCacheByFile.get(reviewedFile) || [];
        if (!Array.isArray(blocks) || !blocks.length) return 0;

        const explicitTodoLine = positiveLineOrZero(violation && (violation._reviewed_todo_line || violation.reviewed_todo_line));
        if (explicitTodoLine > 0) return explicitTodoLine;

        const blockIndexes = Array.isArray(violation && violation._reviewed_block_indexes)
            ? violation._reviewed_block_indexes
                .map((value) => Number.parseInt(value, 10))
                .filter((value) => Number.isFinite(value) && value > 0)
            : [];
        for (const blockIndex of blockIndexes) {
            const block = blocks[blockIndex - 1];
            const todoLine = positiveLineOrZero(block && block.todo_line);
            if (todoLine > 0) return todoLine;
        }

        const issueId = String((violation && violation.issue_id) || "").trim();
        if (issueId) {
            const byIssue = blocks.find((block) => String((((block || {}).meta || {}).issue_id) || "").trim() === issueId);
            const todoLine = positiveLineOrZero(byIssue && byIssue.todo_line);
            if (todoLine > 0) return todoLine;
        }

        const targetRuleId = normalizeP1RuleId((violation && violation.rule_id) || "");
        const targetMessage = normalizeReviewedMessageKey(
            String((violation && (violation._reviewed_original_message || violation.message)) || "").trim(),
        );
        if (targetRuleId !== "UNKNOWN" || targetMessage) {
            const matched = blocks.find((block) => {
                const inferredRuleId = normalizeP1RuleId(inferRuleIdFromReviewedBlock(block).inferredRuleId);
                const normalizedMessage = normalizeReviewedMessageKey((block && block.message) || "");
                const ruleMatch = targetRuleId !== "UNKNOWN" && inferredRuleId === targetRuleId;
                const messageMatch = targetMessage
                    && normalizedMessage
                    && (normalizedMessage.includes(targetMessage) || targetMessage.includes(normalizedMessage));
                return ruleMatch || messageMatch;
            });
            const todoLine = positiveLineOrZero(matched && matched.todo_line);
            if (todoLine > 0) return todoLine;
        }

        return 0;
    }

    function applyPrecomputedJumpTarget(violation, preferredSource = "") {
        const safe = (violation && typeof violation === "object") ? violation : {};
        const next = { ...safe };
        const source = String(preferredSource || next._jump_target_source || "").trim().toLowerCase();
        const explicitLine = positiveLineOrZero(next._jump_target_line || next.line);
        if (source === "reviewed" || (!source && String(next.priority_origin || "").toUpperCase() === "P1")) {
            const reviewedLine = resolveReviewedJumpLineFromCache(next.file || next.object, next);
            if (reviewedLine > 0) {
                next._jump_target_source = "reviewed";
                next._jump_target_line = reviewedLine;
                next._reviewed_todo_line = positiveLineOrZero(next._reviewed_todo_line || reviewedLine);
                return next;
            }
        }
        if (source === "source" || String(next.priority_origin || "").toUpperCase() === "P2") {
            if (explicitLine > 0) {
                next._jump_target_source = "source";
                next._jump_target_line = explicitLine;
            }
            return next;
        }
        if (explicitLine > 0) {
            next._jump_target_line = explicitLine;
        }
        return next;
    }

    async function fetchFileContentPayload(fileName, options = {}) {
        if (!fileName) throw new Error("file name is required");
        const preferSource = !!(options && options.preferSource);
        const qs = new URLSearchParams({ name: String(fileName) });
        const outputDir = String((options && options.outputDir) || (state.analysisData && state.analysisData.output_dir) || "").trim();
        const cacheKey = `${outputDir}::${String(fileName)}::${preferSource ? "source" : "viewer"}`;
        if (caches.viewerContentCache.has(cacheKey)) {
            return { ...caches.viewerContentCache.get(cacheKey) };
        }
        if (preferSource) {
            qs.set("prefer_source", "true");
        }
        if (outputDir) {
            qs.set("output_dir", outputDir);
        }
        const response = await fetch(`/api/file-content?${qs.toString()}`);
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "파일 내용을 불러오지 못했습니다.");
        }
        caches.viewerContentCache.set(cacheKey, { ...payload });
        return payload;
    }

    async function prepareFunctionScopeCacheForSelectedFiles(selectedFiles) {
        caches.functionScopeCacheByFile.clear();
        caches.reviewedTodoCacheByFile.clear();
        const files = Array.isArray(selectedFiles)
            ? selectedFiles.map((name) => basenamePath(name)).filter((name) => !!name)
            : [];
        if (files.length === 0) return;

        const batchSize = 4;
        for (let i = 0; i < files.length; i += batchSize) {
            const batch = files.slice(i, i + batchSize);
            // Fail-soft: best-effort cache population. Missing files remain unresolved.
            // eslint-disable-next-line no-await-in-loop
            await Promise.all(batch.map(async (fileName) => {
                try {
                    const [sourcePayload, viewPayload] = await Promise.all([
                        fetchFileContentPayload(fileName, { preferSource: true }),
                        fetchFileContentPayload(fileName, { preferSource: false }),
                    ]);
                    const descriptor = fileDescriptorFor(
                        (viewPayload && viewPayload.file_descriptor)
                        || (sourcePayload && sourcePayload.file_descriptor)
                        || fileName,
                        fileName,
                    );
                    const cacheKey = canonicalFileId(descriptor, fileName);
                    cacheFunctionScopesForFile(cacheKey, String((sourcePayload && sourcePayload.content) || ""));
                    if (viewPayload && String(viewPayload.source || "") === "reviewed") {
                        caches.reviewedTodoCacheByFile.set(
                            cacheKey,
                            parseReviewedTodoBlocks(String(viewPayload.content || ""), descriptor.canonical_name || fileName),
                        );
                    }
                } catch (_) {
                    // unresolved scope fallback
                }
            }));
        }
    }

    function setActiveJumpRequestState(status = "idle", line = 0) {
        state.activeJumpRequestState = {
            status: String(status || "idle"),
            line: positiveLineOrZero(line),
        };
        updateCodeViewerHeaderMeta();
    }

    function buildCodeViewerHeader(payload) {
        if (!payload || typeof payload !== "object") return "";
        const sourceMap = {
            reviewed: "REVIEWED.txt",
            normalized: "정규화 TXT",
            source: "원본 파일",
        };
        const sourceType = sourceMap[String(payload.source || "")] || String(payload.source || "파일");
        const descriptor = fileDescriptorFor(payload.file_descriptor || payload, payload.resolved_name || payload.file || "");
        const resolvedName = String(descriptor.display_name || payload.resolved_name || payload.file || "");
        return `// 표시 파일: ${resolvedName} (${sourceType})`;
    }

    function buildCodeViewerStatusText() {
        const fileName = basenamePath(state.currentViewerResolvedName || state.currentViewerFile || "") || "선택된 파일 없음";
        const sourceMap = {
            reviewed: "REVIEWED.txt",
            normalized: "정규화 TXT",
            source: "원본 파일",
        };
        let lineText = "라인 선택 없음";
        if (state.activeJumpRequestState.status === "pending") {
            lineText = state.activeJumpRequestState.line > 0
                ? `라인 ${state.activeJumpRequestState.line} 이동 중`
                : "점프 이동 중";
        } else if (state.activeJumpRequestState.status === "failed") {
            lineText = state.activeJumpRequestState.line > 0
                ? `라인 ${state.activeJumpRequestState.line} 이동 실패`
                : "위치 이동 실패";
        } else if (state.currentHighlightedLine) {
            lineText = `라인 ${state.currentHighlightedLine}${state.currentHighlightedLineNear ? " 근접 이동" : " 직접 이동"}`;
        }
        return {
            fileName,
            sourceText: sourceMap[String(state.currentViewerSource || "").trim()] || "파일",
            lineText,
            filterText: helpers.buildRecommendationWorkspaceFilterText ? helpers.buildRecommendationWorkspaceFilterText() : "필터 없음",
        };
    }

    function createHeaderChip(label, value, tone = "") {
        const chip = document.createElement("span");
        chip.className = `code-viewer-chip${tone ? ` ${tone}` : ""}`;
        const labelEl = document.createElement("strong");
        labelEl.textContent = `${label} `;
        chip.appendChild(labelEl);
        chip.append(value);
        return chip;
    }

    function updateCodeViewerHeaderMeta() {
        const headerEl = virtualState.codeViewerVirtualState.headerEl;
        if (!headerEl) return;
        const status = buildCodeViewerStatusText();
        const titleEl = headerEl.querySelector(".code-viewer-header-title");
        const subtitleEl = headerEl.querySelector(".code-viewer-header-subtitle");
        const metaRow = headerEl.querySelector(".code-viewer-header-meta");
        if (titleEl) titleEl.textContent = status.fileName;
        if (subtitleEl) subtitleEl.textContent = "원본 코드와 분석 이동 상태를 한 화면에서 유지합니다.";
        if (metaRow) {
            metaRow.replaceChildren(
                createHeaderChip("소스", status.sourceText, "code-viewer-chip-muted"),
                createHeaderChip("점프", status.lineText, state.currentHighlightedLine ? "code-viewer-chip-accent" : "code-viewer-chip-muted"),
                createHeaderChip("필터", status.filterText, state.recommendationWorkspaceFilter.mode ? "code-viewer-chip-filter" : "code-viewer-chip-muted"),
            );
        }
    }

    function clearCodeViewerHighlight() {
        if (!dom.codeViewer || !state.currentHighlightedLine) return;
        const prev = dom.codeViewer.querySelector(`.code-line[data-line="${state.currentHighlightedLine}"]`);
        if (prev) {
            prev.classList.remove("line-highlight", "line-highlight-near");
        }
        state.currentHighlightedLine = null;
        state.currentHighlightedLineNear = false;
        updateCodeViewerHeaderMeta();
    }

    function highlightCodeViewerLine(lineNumber, near = false) {
        if (!dom.codeViewer) return false;
        const line = Number.parseInt(lineNumber, 10);
        if (!Number.isFinite(line) || line <= 0) return false;
        if (state.currentViewerLines.length > 0 && (line > state.currentViewerLines.length)) return false;
        queueCodeViewerWindowRender();
        const target = dom.codeViewer.querySelector(`.code-line[data-line="${line}"]`);
        if (!target) return false;

        clearCodeViewerHighlight();
        target.classList.add(near ? "line-highlight-near" : "line-highlight");
        state.currentHighlightedLine = line;
        state.currentHighlightedLineNear = !!near;

        void target.offsetWidth;
        target.classList.add(near ? "line-highlight-near" : "line-highlight");
        updateCodeViewerHeaderMeta();
        return true;
    }

    function revealCodeViewerFocus() {
        if (!dom.codeViewer) return;
        const focusShell = dom.codeViewer.closest(".workspace-code-shell");
        if (focusShell) {
            focusShell.classList.remove("workspace-code-shell-focus");
            void focusShell.offsetWidth;
            focusShell.classList.add("workspace-code-shell-focus");
            if (state.codeViewerFocusTimer) {
                window.clearTimeout(state.codeViewerFocusTimer);
            }
            state.codeViewerFocusTimer = window.setTimeout(() => {
                focusShell.classList.remove("workspace-code-shell-focus");
            }, 1800);
            const rect = focusShell.getBoundingClientRect();
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            const isAboveViewport = rect.top < 70;
            const isBelowViewport = rect.bottom > viewportHeight - 24;
            if ((isAboveViewport || isBelowViewport) && typeof focusShell.scrollIntoView === "function") {
                focusShell.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
        }
    }

    function getViewerLineHeight() {
        if (!dom.codeViewer) return 20;
        const rendered = dom.codeViewer.querySelector(".code-line");
        if (rendered) {
            const h = rendered.getBoundingClientRect().height;
            if (Number.isFinite(h) && h > 0) return h;
        }
        if (
            Number.isFinite(virtualState.codeViewerVirtualState.lineHeight)
            && virtualState.codeViewerVirtualState.lineHeight > 0
        ) {
            return virtualState.codeViewerVirtualState.lineHeight;
        }
        const computed = window.getComputedStyle(dom.codeViewer);
        const lineHeight = Number.parseFloat(computed.lineHeight || "");
        if (Number.isFinite(lineHeight) && lineHeight > 0) return lineHeight;
        const fontSize = Number.parseFloat(computed.fontSize || "");
        return Number.isFinite(fontSize) && fontSize > 0 ? fontSize * 1.4 : 20;
    }

    function scrollCodeViewerToLine(lineNumber, { near = false } = {}) {
        if (!dom.codeViewer) return false;
        const line = Number.parseInt(lineNumber, 10);
        if (!Number.isFinite(line) || line <= 0) return false;
        const totalLines = state.currentViewerLines.length;
        const clampedLine = totalLines > 0 ? Math.min(line, totalLines) : line;
        const lineHeight = Math.max(16, getViewerLineHeight());
        const headerOffset = getCodeViewerLineAreaOffset();
        const viewportHeight = Math.max(1, (Number.parseInt(dom.codeViewer.clientHeight, 10) || 1) - headerOffset);
        const centerOffset = Math.max(0, (viewportHeight - lineHeight) / 2);
        const targetTop = Math.max(0, headerOffset + (clampedLine - 1) * lineHeight - centerOffset);
        dom.codeViewer.scrollTop = targetTop;
        queueCodeViewerWindowRender(true);
        renderCodeViewerWindow();
        highlightCodeViewerLine(clampedLine, near);
        setActiveJumpRequestState("resolved", clampedLine);
        revealCodeViewerFocus();
        return true;
    }

    function findReviewedTodoLineForViolation(violation) {
        const lines = Array.isArray(state.currentViewerLines) ? state.currentViewerLines : [];
        if (!lines.length) return 0;

        const explicitTodoLine = positiveLineOrZero(violation && (violation._reviewed_todo_line || violation.reviewed_todo_line));
        if (explicitTodoLine > 0) {
            return explicitTodoLine;
        }

        const blockIndexes = Array.isArray(violation && violation._reviewed_block_indexes)
            ? violation._reviewed_block_indexes
                .map((value) => Number.parseInt(value, 10))
                .filter((value) => Number.isFinite(value) && value > 0)
            : [];
        if (blockIndexes.length) {
            const todoLines = [];
            for (let idx = 0; idx < lines.length; idx += 1) {
                if (/^\/\/\s*>>TODO/i.test(String(lines[idx] || "").trim())) {
                    todoLines.push(idx + 1);
                }
            }
            for (const blockIndex of blockIndexes) {
                const anchored = todoLines[blockIndex - 1];
                if (anchored > 0) {
                    return anchored;
                }
            }
        }

        const issueId = String((violation && violation.issue_id) || "").trim();
        const ruleId = String((violation && violation.rule_id) || "").trim();
        const normalizedMessage = normalizeReviewedMessageKey(
            String((violation && (violation._reviewed_original_message || violation.message)) || "").trim(),
        );

        const findTodoAnchor = (startIndex) => {
            for (let idx = startIndex; idx >= 0; idx -= 1) {
                if (/^\/\/\s*>>TODO/i.test(String(lines[idx] || "").trim())) {
                    return idx + 1;
                }
            }
            return 0;
        };

        if (issueId) {
            for (let idx = 0; idx < lines.length; idx += 1) {
                if (String(lines[idx] || "").includes(issueId)) {
                    return findTodoAnchor(idx);
                }
            }
        }

        if (ruleId) {
            const ruleToken = `rule_id=${ruleId}`;
            for (let idx = 0; idx < lines.length; idx += 1) {
                if (String(lines[idx] || "").includes(ruleToken)) {
                    return findTodoAnchor(idx);
                }
            }
        }

        if (normalizedMessage) {
            for (let idx = 0; idx < lines.length; idx += 1) {
                const normalizedLine = normalizeReviewedMessageKey(lines[idx]);
                if (
                    normalizedLine
                    && (
                        normalizedLine.includes(normalizedMessage)
                        || normalizedMessage.includes(normalizedLine)
                    )
                ) {
                    return findTodoAnchor(idx);
                }
            }
        }

        return 0;
    }

    function scrollCodeViewerToMessage(message) {
        if (!state.currentViewerContent) return false;
        const token = messageSearchToken(message);
        if (!token) return false;
        const index = state.currentViewerContent.toLowerCase().indexOf(token.toLowerCase());
        if (index < 0) return false;
        const line = state.currentViewerContent.slice(0, index).split("\n").length;
        return scrollCodeViewerToLine(line, { near: true });
    }

    async function jumpCodeViewerToViolation(violation) {
        const safeViolation = applyPrecomputedJumpTarget(violation, String((violation && violation._jump_target_source) || "").trim());
        const sourceKey = helpers.sourceFilterKey ? helpers.sourceFilterKey(safeViolation && safeViolation.priority_origin) : "";
        const isP2 = sourceKey === "p2";
        const isP1 = sourceKey === "p1";
        const targetFilePath = String((safeViolation && (safeViolation.file_path || safeViolation.file || safeViolation.file_name || safeViolation.filename)) || "");
        const fileHint = basenamePath(targetFilePath);
        const lineNo = positiveLineOrZero(safeViolation && safeViolation.line);
        const precomputedLine = positiveLineOrZero(safeViolation && safeViolation._jump_target_line);
        const jumpSource = String((safeViolation && safeViolation._jump_target_source) || (isP2 ? "source" : "")).trim().toLowerCase();
        const ruleId = String((safeViolation && safeViolation.rule_id) || "").toLowerCase();

        if (
            isP2
            && (
                ((!fileHint || !String(fileHint).trim()) && lineNo <= 0 && precomputedLine <= 0)
                || (ruleId === "ctrlppcheck.info" && lineNo <= 0 && precomputedLine <= 0)
            )
        ) {
            return { ok: false, reason: "no-locatable-position" };
        }

        if (isP2 && fileHint && !String(fileHint).toLowerCase().endsWith(".ctl")) {
            return { ok: false, reason: "invalid-target-file" };
        }

        const ensureViewerForTarget = async () => {
            const targetFile = targetFilePath || state.currentViewerFile || fileHint || basenamePath(state.currentViewerFile);
            if (!targetFile) {
                return { ok: false, reason: jumpSource === "source" ? "source-not-found" : "file-load-miss" };
            }
            if (jumpSource === "source" && !String(targetFile).toLowerCase().endsWith(".ctl")) {
                return { ok: false, reason: "invalid-target-file" };
            }
            const wantSource = jumpSource === "source";
            const wantReviewed = jumpSource === "reviewed";
            const currentFile = String(state.currentViewerFile || "");
            const shouldReload =
                currentFile !== targetFile
                || (wantSource && state.currentViewerSource !== "source")
                || (wantReviewed && state.currentViewerSource !== "reviewed")
                || (!state.currentViewerContent && currentFile === targetFile);
            if (!shouldReload) return { ok: true };
            try {
                await loadCodeViewer(targetFile, { preferSource: wantSource });
            } catch (_) {
                return { ok: false, reason: wantSource ? "load-source-failed" : "file-load-miss" };
            }
            if (wantSource && String(state.currentViewerSource || "") !== "source") {
                return { ok: false, reason: "source-not-found" };
            }
            await new Promise((resolve) => {
                window.requestAnimationFrame(() => resolve());
            });
            return { ok: true };
        };

        const retryOnce = async (reason) => {
            const retryable = reason === "reviewed-anchor-miss" || reason === "source-line-miss";
            if (!retryable || (safeViolation && safeViolation._jump_retry_done)) {
                return { ok: false, reason };
            }
            await new Promise((resolve) => {
                window.requestAnimationFrame(() => {
                    window.requestAnimationFrame(resolve);
                });
            });
            return jumpCodeViewerToViolation({ ...safeViolation, _jump_retry_done: true });
        };

        if (isP1 || isP2 || jumpSource) {
            const viewerReady = await ensureViewerForTarget();
            if (!viewerReady.ok) {
                setActiveJumpRequestState("failed", precomputedLine || lineNo);
                return viewerReady;
            }
        }

        if (!state.currentViewerContent) {
            setActiveJumpRequestState("failed", precomputedLine || lineNo);
            return { ok: false, reason: "no-viewer" };
        }

        const isReviewed = state.currentViewerSource === "reviewed";
        const tryNearLine = () => {
            const targetLine = precomputedLine || lineNo;
            if (targetLine <= 0) return false;
            const maxLine = currentViewerLineCount();
            const clamped = maxLine > 0 ? Math.min(targetLine, maxLine) : targetLine;
            if (clamped <= 0) return false;
            return scrollCodeViewerToLine(clamped, { near: true });
        };

        if (precomputedLine > 0 && scrollCodeViewerToLine(precomputedLine, { near: jumpSource !== "source" })) {
            return { ok: true, reason: "hit-precomputed" };
        }

        if (isReviewed) {
            const reviewedTodoLine = findReviewedTodoLineForViolation(safeViolation);
            if (reviewedTodoLine > 0 && scrollCodeViewerToLine(reviewedTodoLine, { near: true })) {
                return { ok: true, reason: "hit-reviewed-todo" };
            }
        }

        if (isP2) {
            if (tryNearLine()) {
                return { ok: true, reason: "hit-line-near" };
            }
            if (scrollCodeViewerToMessage(safeViolation && safeViolation.message)) {
                return { ok: true, reason: "hit-message" };
            }
            setActiveJumpRequestState("failed", precomputedLine || lineNo);
            return retryOnce(isReviewed ? "reviewed-anchor-miss" : "source-line-miss");
        }

        if (!isReviewed && lineNo > 0 && scrollCodeViewerToLine(lineNo)) {
            return { ok: true, reason: "hit-line" };
        }

        if (scrollCodeViewerToMessage(safeViolation && safeViolation.message)) {
            return { ok: true, reason: "hit-message" };
        }

        if (tryNearLine()) {
            return { ok: true, reason: "hit-line-near" };
        }

        setActiveJumpRequestState("failed", precomputedLine || lineNo);
        return retryOnce(isReviewed ? "reviewed-anchor-miss" : "source-line-miss");
    }

    function pendingJumpLineForViolation(violation) {
        return positiveLineOrZero(
            violation
            && (
                violation._jump_target_line
                || violation._reviewed_todo_line
                || violation.line
            ),
        );
    }

    async function loadCodeViewer(fileName, options = {}) {
        if (!fileName) return;
        const preferSource = !!(options && options.preferSource);
        try {
            const payload = await fetchFileContentPayload(fileName, {
                preferSource,
                outputDir: options && options.outputDir,
            });
            const header = buildCodeViewerHeader(payload);
            const content = String(payload.content || "");
            state.currentViewerFile = String(payload.resolved_path || payload.file || fileName || "");
            state.currentViewerResolvedName = String(payload.resolved_name || "");
            state.currentViewerSource = String(payload.source || "");
            state.currentViewerContent = content;
            cacheFunctionScopesForFile(state.currentViewerFile || fileName, content);
            state.currentViewerHeaderLines = header ? 2 : 0;
            renderCodeViewerContent(header, content);
            return payload;
        } catch (err) {
            state.currentViewerSource = "";
            state.currentViewerContent = "";
            state.currentViewerHeaderLines = 0;
            setCodeViewerText(`// 파일 내용을 불러오지 못했습니다.\n// ${String((err && err.message) || err || "")}`);
            throw err;
        }
    }

    return {
        applyPrecomputedJumpTarget,
        attachCodeViewerVirtualScrollHandler,
        buildCodeViewerHeader,
        buildCodeViewerStatusText,
        cacheFunctionScopesForFile,
        clearCodeViewerHighlight,
        createCodeLineRow,
        createHeaderChip,
        fetchFileContentPayload,
        getCodeViewerLineAreaOffset,
        getFunctionScopeFor,
        getViewerLineHeight,
        highlightCodeViewerLine,
        jumpCodeViewerToViolation,
        loadCodeViewer,
        pendingJumpLineForViolation,
        prepareFunctionScopeCacheForSelectedFiles,
        queueCodeViewerWindowRender,
        renderCodeViewerContent,
        renderCodeViewerWindow,
        resolveFunctionScopeForViolation,
        resolveReviewedJumpLineFromCache,
        revealCodeViewerFocus,
        scrollCodeViewerToLine,
        scrollCodeViewerToMessage,
        setActiveJumpRequestState,
        setCodeViewerText,
        updateCodeViewerHeaderMeta,
    };
}
