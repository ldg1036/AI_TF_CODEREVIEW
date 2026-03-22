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
        strong.textContent = title || "AI detail is not available for this item yet.";
        const paragraph = document.createElement("p");
        paragraph.textContent = detail || "";
        node.append(strong, paragraph);
        if (diagnostic && typeof diagnostic === "object") {
            const wrap = document.createElement("div");
            wrap.className = "ai-empty-diagnostic";
            const summary = document.createElement("div");
            summary.className = "ai-empty-diagnostic-summary";
            [
                ["Classification", String(diagnostic.classification_label || diagnostic.classification || "-")],
                ["AI status", String(diagnostic.status_label || diagnostic.status || "-")],
                ["AI reason", String(diagnostic.reason_label || diagnostic.reason || "-")],
                ["Match", String(diagnostic.match_label || "-")],
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
                ["Selected source", String(diagnostic.selected_source || "-")],
                ["Selected issue_id", String(diagnostic.selected_issue_id || "-")],
                ["Selected rule_id", String(diagnostic.selected_rule_id || "-")],
                ["Selected line", String(diagnostic.selected_line || "-")],
                ["AI parent issue_id", String(diagnostic.parent_issue_id || "-")],
                ["AI parent rule_id", String(diagnostic.parent_rule_id || "-")],
                ["AI parent line", String(diagnostic.parent_line || "-")],
            ];
            if (diagnostic.match_hint) rows.push(["Match hint", String(diagnostic.match_hint)]);
            if (helpers.positiveLineOrZero(diagnostic.selected_cap || 0) > 0) rows.push(["Selected cap", String(diagnostic.selected_cap)]);
            if (helpers.positiveLineOrZero(diagnostic.selected_rank || 0) > 0) rows.push(["Selected rank", String(diagnostic.selected_rank)]);
            if (diagnostic.detail) rows.push(["Detail", String(diagnostic.detail)]);
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
                toggle.textContent = "Show diagnostics";
                toggle.onclick = () => {
                    const collapsed = details.classList.toggle("is-collapsed");
                    toggle.textContent = collapsed ? "Show diagnostics" : "Hide diagnostics";
                };
                wrap.append(toggle, details);
            }
            const actionWrap = document.createElement("div");
            actionWrap.className = "ai-empty-actions";
            const generateBtn = document.createElement("button");
            generateBtn.type = "button";
            generateBtn.id = "btn-ai-generate-empty";
            generateBtn.className = "ai-empty-diagnostic-toggle";
            generateBtn.textContent = "Generate AI Review";
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
            dom.btnAiMore.textContent = show ? "Close more actions" : "More actions";
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
