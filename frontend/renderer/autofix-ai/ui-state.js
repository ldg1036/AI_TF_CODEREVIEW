export function createAutofixUiStateController({ dom, state, helpers }) {
    function ensureAiEmptyStateNode() {
        let node = document.getElementById("ai-empty-state");
        if (!node && dom.aiPanelWrap) {
            node = document.createElement("div");
            node.id = "ai-empty-state";
            node.className = "inspector-empty-state";
            dom.aiPanelWrap.appendChild(node);
        }
        return node;
    }

    function renderAiEmptyState(title, detail, diagnostic = null) {
        const node = ensureAiEmptyStateNode();
        if (!node) return;
        node.replaceChildren();
        const strong = document.createElement("strong");
        strong.textContent = title || "이 항목에는 아직 AI 개선 제안이 준비되지 않았습니다.";
        const paragraph = document.createElement("p");
        paragraph.textContent = detail || "";
        node.append(strong, paragraph);
        if (diagnostic && typeof diagnostic === "object") {
            const wrap = document.createElement("div");
            wrap.className = "ai-empty-diagnostic";
            const summary = document.createElement("div");
            summary.className = "ai-empty-diagnostic-summary";
            [
                ["분류", String(diagnostic.classification_label || diagnostic.classification || "-")],
                ["AI 상태", String(diagnostic.status_label || diagnostic.status || "-")],
                ["AI 사유", String(diagnostic.reason_label || diagnostic.reason || "-")],
                ["매칭", String(diagnostic.match_label || "-")],
            ].forEach(([label, value]) => {
                const item = document.createElement("div");
                item.className = "ai-empty-diagnostic-item";
                const key = document.createElement("span");
                key.className = "ai-empty-diagnostic-key";
                key.textContent = `${label}:`;
                const val = document.createElement("span");
                val.className = "ai-empty-diagnostic-value";
                val.textContent = value;
                item.append(key, val);
                summary.appendChild(item);
            });
            wrap.appendChild(summary);

            const details = document.createElement("div");
            details.className = "ai-empty-diagnostic-details";
            details.classList.add("is-collapsed");
            const rows = [
                ["선택 소스", String(diagnostic.selected_source || "-")],
                ["선택 issue_id", String(diagnostic.selected_issue_id || "-")],
                ["선택 rule_id", String(diagnostic.selected_rule_id || "-")],
                ["선택 라인", String(diagnostic.selected_line || "-")],
                ["AI 부모 issue_id", String(diagnostic.parent_issue_id || "-")],
                ["AI 부모 rule_id", String(diagnostic.parent_rule_id || "-")],
                ["AI 부모 라인", String(diagnostic.parent_line || "-")],
            ];
            if (diagnostic.match_hint) rows.push(["매칭 힌트", String(diagnostic.match_hint)]);
            if (helpers.positiveLineOrZero(diagnostic.selected_cap || 0) > 0) rows.push(["선택 cap", String(diagnostic.selected_cap)]);
            if (helpers.positiveLineOrZero(diagnostic.selected_rank || 0) > 0) rows.push(["선택 rank", String(diagnostic.selected_rank)]);
            if (diagnostic.detail) rows.push(["상세", String(diagnostic.detail)]);
            rows.forEach(([label, value]) => {
                const row = document.createElement("div");
                row.className = "ai-empty-diagnostic-row";
                const key = document.createElement("span");
                key.className = "ai-empty-diagnostic-key";
                key.textContent = `${label}:`;
                const val = document.createElement("span");
                val.className = "ai-empty-diagnostic-value";
                val.textContent = value;
                row.append(key, val);
                details.appendChild(row);
            });
            if (rows.length > 0) {
                const toggle = document.createElement("button");
                toggle.type = "button";
                toggle.className = "ai-empty-diagnostic-toggle";
                toggle.textContent = "진단 정보 보기";
                toggle.onclick = () => {
                    const collapsed = details.classList.toggle("is-collapsed");
                    toggle.textContent = collapsed ? "진단 정보 보기" : "진단 정보 숨기기";
                };
                wrap.append(toggle, details);
            }
            const actionWrap = document.createElement("div");
            actionWrap.className = "ai-empty-actions";
            const generateBtn = document.createElement("button");
            generateBtn.type = "button";
            generateBtn.id = "btn-ai-generate-empty";
            generateBtn.className = "ai-empty-diagnostic-toggle";
            generateBtn.textContent = "AI 개선 제안 생성";
            actionWrap.appendChild(generateBtn);
            wrap.appendChild(actionWrap);
            node.appendChild(wrap);
        }
        node.style.display = "block";
        if (dom.aiCard) {
            dom.aiCard.style.display = "none";
            dom.aiCard.dataset.aiKey = "";
        }
    }

    function hideAiEmptyState() {
        const node = document.getElementById("ai-empty-state");
        if (node) {
            node.style.display = "none";
            node.replaceChildren();
        }
    }

    function syncAiMoreMenuUi() {
        if (!dom.aiMoreActions) return;
        const show = !!state.aiMoreMenuOpen;
        dom.aiMoreActions.style.display = show ? "grid" : "none";
        if (dom.btnAiMore) {
            dom.btnAiMore.textContent = show ? "추가 작업 닫기" : "추가 작업";
        }
    }

    function ensureAiStatusNode() {
        let node = document.getElementById("ai-status-inline");
        if (!node && dom.aiCard) {
            node = document.createElement("p");
            node.id = "ai-status-inline";
            node.className = "ai-status-inline";
            dom.aiCard.appendChild(node);
        }
        return node;
    }

    function ensureAiActionHintNode() {
        let node = document.getElementById("ai-action-hint");
        if (!node && dom.aiPrimaryActions && dom.aiCard) {
            node = document.createElement("div");
            node.id = "ai-action-hint";
            node.className = "ai-action-hint";
            dom.aiPrimaryActions.parentNode.insertBefore(node, dom.aiPrimaryActions.nextSibling);
        }
        return node;
    }

    function setAiStatusInline(message, color = "") {
        const node = ensureAiStatusNode();
        if (!node) return;
        node.textContent = message || "";
        node.style.display = message ? "block" : "none";
        node.style.color = color || "";
    }

    function setAiActionHint(message, tone = "") {
        const node = ensureAiActionHintNode();
        if (!node) return;
        node.textContent = String(message || "");
        node.className = `ai-action-hint ${tone ? `ai-action-hint-${tone}` : ""}`.trim();
        node.style.display = message ? "block" : "none";
    }

    return {
        hideAiEmptyState,
        renderAiEmptyState,
        setAiActionHint,
        setAiStatusInline,
        syncAiMoreMenuUi,
    };
}
