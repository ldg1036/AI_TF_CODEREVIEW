import { escapeHtml } from "./utils.js";
import {
    buildRulesImportPreviewSummary,
    createEmptyRuleDraft,
    deepClone,
    extractRulesFromImportPayload,
    parseRuleEditorJsonFields,
    validateDetectorJsonText,
} from "./rules-manage-helpers.js";

function renderStatus(host, message, color = "") {
    if (!message) return;
    const row = document.createElement("div");
    row.className = "rules-manage-status";
    row.textContent = message;
    if (color) row.style.color = color;
    host.appendChild(row);
}

function previewSampleText(entry) {
    if (!entry || typeof entry !== "object") return "";
    const id = String(entry.id || "").trim() || "-";
    const status = String(entry.status || "").trim() || "unchanged";
    const beforeRuleId = String(entry.before_rule_id || "").trim();
    const afterRuleId = String(entry.after_rule_id || "").trim();
    const beforeEnabled = typeof entry.before_enabled === "boolean" ? String(entry.before_enabled) : "";
    const afterEnabled = typeof entry.after_enabled === "boolean" ? String(entry.after_enabled) : "";
    const parts = [`${id} [${status}]`];
    if (beforeRuleId || afterRuleId) parts.push(`${beforeRuleId || "-"} -> ${afterRuleId || "-"}`);
    if (beforeEnabled || afterEnabled) parts.push(`enabled ${beforeEnabled || "-"} -> ${afterEnabled || "-"}`);
    return parts.join(" | ");
}

export function createRulesManageController({ state, helpers }) {
    function getRulesManageUpdates() {
        return state.rulesManageRows
            .filter((row) => state.rulesManageDraftById.has(row.id) && state.rulesManageDraftById.get(row.id) !== !!row.enabled)
            .map((row) => ({ id: row.id, enabled: !!state.rulesManageDraftById.get(row.id) }));
    }

    function clearImportPreview() {
        state.rulesManageImportPreview = null;
        state.rulesManageImportDraft = null;
    }

    function startNewRuleDraft() {
        state.rulesManageEditorMode = "create";
        state.rulesManageEditorRuleId = "";
        state.rulesManageEditorDraft = createEmptyRuleDraft(state.rulesManageRows);
        state.rulesManageStatusMessage = "Started a new rule draft.";
    }

    function loadRuleIntoEditor(ruleId) {
        const target = state.rulesManageRows.find((row) => String(row.id || "") === String(ruleId || ""));
        if (!target) return;
        state.rulesManageEditorMode = "edit";
        state.rulesManageEditorRuleId = String(target.id || "");
        state.rulesManageEditorDraft = deepClone({
            id: target.id,
            order: target.order,
            enabled: !!target.enabled,
            file_types: Array.isArray(target.file_types) ? target.file_types : ["Client", "Server"],
            rule_id: target.rule_id,
            item: target.item,
            detector: target.detector || { kind: target.detector_kind || "regex" },
            finding: target.finding || { severity: target.severity || "Warning", message: target.message || "" },
            meta: target.meta || {},
        });
    }

    function ensureRuleEditorState() {
        if (state.rulesManageEditorDraft) return;
        if (state.rulesManageRows.length) {
            loadRuleIntoEditor(state.rulesManageEditorRuleId || state.rulesManageRows[0].id);
            return;
        }
        startNewRuleDraft();
    }

    function readRuleEditorForm(form) {
        const detectorText = form.querySelector('[name="detector_json"]').value.trim() || "{}";
        const metaText = form.querySelector('[name="meta_json"]').value.trim() || "{}";
        const { detector, meta } = parseRuleEditorJsonFields(detectorText, metaText);
        const fileTypes = [];
        if (form.querySelector('[name="file_type_client"]').checked) fileTypes.push("Client");
        if (form.querySelector('[name="file_type_server"]').checked) fileTypes.push("Server");
        return {
            id: form.querySelector('[name="id"]').value.trim(),
            order: Number(form.querySelector('[name="order"]').value || 0),
            enabled: !!form.querySelector('[name="enabled"]').checked,
            file_types: fileTypes,
            rule_id: form.querySelector('[name="rule_id"]').value.trim(),
            item: form.querySelector('[name="item"]').value.trim(),
            detector,
            finding: {
                severity: form.querySelector('[name="severity"]').value.trim(),
                message: form.querySelector('[name="message"]').value.trim(),
            },
            meta,
        };
    }

    function applyRulesManagePayload(payload) {
        if (payload && Array.isArray(payload.rules)) {
            state.rulesManageRows = payload.rules;
            state.rulesManageDraftById = new Map(state.rulesManageRows.map((row) => [row.id, !!row.enabled]));
            if (state.rulesManageEditorMode === "create") {
                startNewRuleDraft();
            } else if (state.rulesManageEditorRuleId) {
                loadRuleIntoEditor(state.rulesManageEditorRuleId);
            } else if (state.rulesManageRows.length) {
                loadRuleIntoEditor(state.rulesManageRows[0].id);
            } else {
                startNewRuleDraft();
            }
        }
    }

    async function previewRulesImport(mode, rules, sourceName = "") {
        state.rulesManageSaving = true;
        state.rulesManageImportDraft = { mode, rules, sourceName };
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode, rules, dry_run: true }),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(result.error || `Rules import preview failed (${response.status})`);
            }
            state.rulesManageImportPreview = result;
            const summary = buildRulesImportPreviewSummary(result);
            state.rulesManageStatusMessage = `Preview ready: ${summary.created} create, ${summary.updated} update, ${summary.unchanged} unchanged.`;
        } catch (err) {
            state.rulesManageImportPreview = null;
            state.rulesManageStatusMessage = (err && err.message) || String(err);
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    function triggerRulesImport(mode) {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".json,application/json";
        input.addEventListener("change", async () => {
            const file = input.files && input.files[0];
            if (!file) return;
            const text = await file.text();
            let payload;
            try {
                payload = JSON.parse(text);
            } catch (_) {
                state.rulesManageStatusMessage = "Imported JSON is invalid.";
                clearImportPreview();
                helpers.renderRulesHealth();
                return;
            }
            const rules = extractRulesFromImportPayload(payload);
            if (!rules.length) {
                state.rulesManageStatusMessage = "Imported file does not contain any rules.";
                clearImportPreview();
                helpers.renderRulesHealth();
                return;
            }
            await previewRulesImport(mode, rules, String(file.name || ""));
        });
        input.click();
    }

    async function applyRulesImportPreview() {
        const draft = state.rulesManageImportDraft;
        if (!draft || state.rulesManageSaving) return;
        state.rulesManageSaving = true;
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: draft.mode, rules: draft.rules }),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(result.error || `Rules import failed (${response.status})`);
            }
            applyRulesManagePayload(result);
            const backupFile = String((((result.backup || {}).source_file) || ""));
            state.rulesManageStatusMessage = backupFile
                ? `Rules import complete. Backup saved as ${backupFile}.`
                : `Rules import complete (${Number(result.imported_count || 0)} items).`;
            clearImportPreview();
            await helpers.loadRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    async function rollbackLatestRules() {
        if (state.rulesManageSaving) return;
        state.rulesManageSaving = true;
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/rollback/latest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(result.error || `Rules rollback failed (${response.status})`);
            }
            applyRulesManagePayload(result);
            clearImportPreview();
            state.rulesManageStatusMessage = `Rules rollback complete (${Number(result.restored_count || 0)} items restored).`;
            await helpers.loadRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    async function exportRulesManagePayload() {
        try {
            const response = await fetch("/api/rules/export");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || `Rules export failed (${response.status})`);
            }
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `p1_rules_export_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 0);
            state.rulesManageStatusMessage = "Rules export complete.";
            helpers.renderRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
        }
    }

    async function saveRuleEditorForm(form) {
        if (state.rulesManageSaving) return;
        let rule;
        try {
            rule = readRuleEditorForm(form);
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
            return;
        }
        state.rulesManageSaving = true;
        helpers.renderRulesHealth();
        try {
            const endpoint = state.rulesManageEditorMode === "create" ? "/api/rules/create" : "/api/rules/replace";
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ rule }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || `Rule save failed (${response.status})`);
            }
            applyRulesManagePayload(payload);
            state.rulesManageEditorMode = "edit";
            state.rulesManageEditorRuleId = String((payload.rule || {}).id || rule.id || "");
            loadRuleIntoEditor(state.rulesManageEditorRuleId);
            state.rulesManageStatusMessage = "Rule saved.";
            await helpers.loadRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    async function deleteCurrentRule() {
        if (state.rulesManageSaving || state.rulesManageEditorMode !== "edit" || !state.rulesManageEditorRuleId) return;
        state.rulesManageSaving = true;
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: state.rulesManageEditorRuleId }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || `Rule delete failed (${response.status})`);
            }
            applyRulesManagePayload(payload);
            if (state.rulesManageRows.length) {
                loadRuleIntoEditor(state.rulesManageRows[0].id);
            } else {
                startNewRuleDraft();
            }
            state.rulesManageStatusMessage = "Rule deleted.";
            await helpers.loadRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
            helpers.renderRulesHealth();
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    function renderRulesManageEditor(panel) {
        ensureRuleEditorState();
        const draft = state.rulesManageEditorDraft || createEmptyRuleDraft(state.rulesManageRows);

        const wrap = document.createElement("div");
        wrap.className = "rules-manage-editor";

        const heading = document.createElement("div");
        heading.className = "rules-manage-editor-heading";
        heading.textContent = state.rulesManageEditorMode === "create" ? "Create rule" : `Edit rule: ${draft.id || "-"}`;
        wrap.appendChild(heading);
        renderStatus(wrap, state.rulesManageStatusMessage);

        const form = document.createElement("form");
        form.className = "rules-manage-form";
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            void saveRuleEditorForm(form);
        });

        const fileTypeSet = new Set(Array.isArray(draft.file_types) ? draft.file_types : []);
        form.innerHTML = `
            <label class="rules-manage-field"><span>ID</span><input name="id" value="${escapeHtml(draft.id || "")}" ${state.rulesManageEditorMode === "edit" ? "readonly" : ""}></label>
            <label class="rules-manage-field"><span>Rule ID</span><input name="rule_id" value="${escapeHtml(draft.rule_id || "")}"></label>
            <label class="rules-manage-field"><span>Item</span><input name="item" value="${escapeHtml(draft.item || "")}"></label>
            <label class="rules-manage-field"><span>Order</span><input name="order" type="number" value="${Number(draft.order || 0)}"></label>
            <label class="rules-manage-field rules-manage-field-inline"><span>Enabled</span><input name="enabled" type="checkbox" ${draft.enabled ? "checked" : ""}></label>
            <div class="rules-manage-field">
                <span>File Types</span>
                <label><input type="checkbox" name="file_type_client" ${fileTypeSet.has("Client") ? "checked" : ""}> Client</label>
                <label><input type="checkbox" name="file_type_server" ${fileTypeSet.has("Server") ? "checked" : ""}> Server</label>
            </div>
            <label class="rules-manage-field"><span>Severity</span><input name="severity" value="${escapeHtml((((draft.finding || {}).severity) || ""))}"></label>
            <label class="rules-manage-field rules-manage-field-wide"><span>Message</span><textarea name="message" rows="3">${escapeHtml((((draft.finding || {}).message) || ""))}</textarea></label>
            <label class="rules-manage-field rules-manage-field-wide"><span>Detector JSON</span><textarea name="detector_json" rows="8">${escapeHtml(JSON.stringify(draft.detector || {}, null, 2))}</textarea></label>
            <label class="rules-manage-field rules-manage-field-wide"><span>Meta JSON</span><textarea name="meta_json" rows="5">${escapeHtml(JSON.stringify(draft.meta || {}, null, 2))}</textarea></label>
        `;

        const detectorField = form.querySelector('[name="detector_json"]');
        const detectorValidation = document.createElement("div");
        detectorValidation.className = "rules-manage-status";
        const syncDetectorValidation = () => {
            const validation = validateDetectorJsonText(detectorField ? detectorField.value : "{}");
            detectorValidation.textContent = validation.message;
            detectorValidation.style.color = validation.ok ? "#2e7d32" : "#c62828";
        };
        if (detectorField) detectorField.addEventListener("input", syncDetectorValidation);
        syncDetectorValidation();
        form.appendChild(detectorValidation);

        const formActions = document.createElement("div");
        formActions.className = "rules-manage-actions";
        const submitButton = document.createElement("button");
        submitButton.type = "submit";
        submitButton.className = "rules-manage-button rules-manage-button-primary";
        submitButton.textContent = state.rulesManageSaving ? "Saving..." : (state.rulesManageEditorMode === "create" ? "Create rule" : "Save rule");
        submitButton.disabled = state.rulesManageSaving;

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "rules-manage-button";
        deleteButton.textContent = "Delete";
        deleteButton.disabled = state.rulesManageSaving || state.rulesManageEditorMode !== "edit" || !state.rulesManageEditorRuleId;
        deleteButton.addEventListener("click", () => {
            void deleteCurrentRule();
        });

        formActions.append(submitButton, deleteButton);
        form.appendChild(formActions);
        wrap.appendChild(form);
        panel.appendChild(wrap);
    }

    function renderImportPreview(panel) {
        if (!state.rulesManageImportPreview) return;
        const preview = state.rulesManageImportPreview;
        const summary = buildRulesImportPreviewSummary(preview);
        const wrap = document.createElement("div");
        wrap.className = "rules-manage-editor";

        const heading = document.createElement("div");
        heading.className = "rules-manage-editor-heading";
        heading.textContent = `Import preview (${String(preview.mode || "replace")})`;
        wrap.appendChild(heading);

        renderStatus(
            wrap,
            `Requested ${summary.requestedCount} | valid ${summary.validCount} | create ${summary.created} | update ${summary.updated} | unchanged ${summary.unchanged} | effective total ${summary.effectiveRuleCount}`,
        );

        const duplicates = Array.isArray(preview.duplicates) ? preview.duplicates : [];
        const errors = Array.isArray(preview.errors) ? preview.errors : [];
        if (duplicates.length) {
            renderStatus(wrap, `Duplicate IDs: ${duplicates.join(", ")}`, "#c62828");
        }
        errors.slice(0, 5).forEach((entry) => {
            renderStatus(wrap, `Error[${Number(entry.index || 0)}] ${String(entry.id || "-")}: ${String(entry.error || "")}`, "#c62828");
        });

        const sampleDiff = Array.isArray(preview.sample_diff) ? preview.sample_diff : [];
        if (sampleDiff.length) {
            const list = document.createElement("div");
            list.className = "rules-manage-list";
            sampleDiff.forEach((entry) => {
                const item = document.createElement("div");
                item.className = "rules-manage-item";
                const copy = document.createElement("div");
                copy.className = "rules-manage-copy";
                const title = document.createElement("div");
                title.className = "rules-manage-title";
                title.textContent = previewSampleText(entry);
                copy.appendChild(title);
                item.appendChild(copy);
                list.appendChild(item);
            });
            wrap.appendChild(list);
        }

        const actionRow = document.createElement("div");
        actionRow.className = "rules-manage-actions";
        const applyButton = document.createElement("button");
        applyButton.type = "button";
        applyButton.className = "rules-manage-button rules-manage-button-primary";
        applyButton.textContent = "Apply preview";
        applyButton.disabled = state.rulesManageSaving || !summary.canApply;
        applyButton.addEventListener("click", () => {
            void applyRulesImportPreview();
        });
        const clearButton = document.createElement("button");
        clearButton.type = "button";
        clearButton.className = "rules-manage-button";
        clearButton.textContent = "Clear preview";
        clearButton.disabled = state.rulesManageSaving;
        clearButton.addEventListener("click", () => {
            clearImportPreview();
            helpers.renderRulesHealth();
        });
        actionRow.append(applyButton, clearButton);
        wrap.appendChild(actionRow);
        panel.appendChild(wrap);
    }

    function renderRulesManagePanel(host) {
        const panel = document.createElement("div");
        panel.className = "rules-manage-panel";
        const actionRow = document.createElement("div");
        actionRow.className = "rules-manage-actions";

        const refreshButton = document.createElement("button");
        refreshButton.type = "button";
        refreshButton.className = "rules-manage-button";
        refreshButton.textContent = state.rulesManageLoading ? "Loading..." : "Refresh";
        refreshButton.disabled = state.rulesManageLoading || state.rulesManageSaving;
        refreshButton.addEventListener("click", () => {
            void loadRulesList(true);
        });

        const dirtyUpdates = getRulesManageUpdates();
        const toggleSaveButton = document.createElement("button");
        toggleSaveButton.type = "button";
        toggleSaveButton.className = "rules-manage-button rules-manage-button-primary";
        toggleSaveButton.textContent = state.rulesManageSaving ? "Saving..." : `Save toggles${dirtyUpdates.length ? ` (${dirtyUpdates.length})` : ""}`;
        toggleSaveButton.disabled = state.rulesManageSaving || state.rulesManageLoading || !dirtyUpdates.length;
        toggleSaveButton.addEventListener("click", () => {
            void saveRulesManageUpdates();
        });

        const newButton = document.createElement("button");
        newButton.type = "button";
        newButton.className = "rules-manage-button";
        newButton.textContent = "New rule";
        newButton.disabled = state.rulesManageSaving || state.rulesManageLoading;
        newButton.addEventListener("click", () => {
            startNewRuleDraft();
            helpers.renderRulesHealth();
        });

        const exportButton = document.createElement("button");
        exportButton.type = "button";
        exportButton.className = "rules-manage-button";
        exportButton.textContent = "Export";
        exportButton.disabled = state.rulesManageSaving || state.rulesManageLoading;
        exportButton.addEventListener("click", () => {
            void exportRulesManagePayload();
        });

        const importMergeButton = document.createElement("button");
        importMergeButton.type = "button";
        importMergeButton.className = "rules-manage-button";
        importMergeButton.textContent = "Preview import (merge)";
        importMergeButton.disabled = state.rulesManageSaving || state.rulesManageLoading;
        importMergeButton.addEventListener("click", () => {
            triggerRulesImport("merge");
        });

        const importReplaceButton = document.createElement("button");
        importReplaceButton.type = "button";
        importReplaceButton.className = "rules-manage-button";
        importReplaceButton.textContent = "Preview import (replace)";
        importReplaceButton.disabled = state.rulesManageSaving || state.rulesManageLoading;
        importReplaceButton.addEventListener("click", () => {
            triggerRulesImport("replace");
        });

        const rollbackButton = document.createElement("button");
        rollbackButton.type = "button";
        rollbackButton.className = "rules-manage-button";
        rollbackButton.textContent = "Rollback latest";
        rollbackButton.disabled = state.rulesManageSaving || state.rulesManageLoading;
        rollbackButton.addEventListener("click", () => {
            void rollbackLatestRules();
        });

        actionRow.append(refreshButton, toggleSaveButton, newButton, exportButton, importMergeButton, importReplaceButton, rollbackButton);
        panel.appendChild(actionRow);

        if (state.rulesManageLoading) {
            const loading = document.createElement("div");
            loading.className = "review-insight-empty";
            loading.textContent = "Loading rules list.";
            panel.appendChild(loading);
            host.appendChild(panel);
            return;
        }

        renderImportPreview(panel);

        if (!state.rulesManageRows.length) {
            const empty = document.createElement("div");
            empty.className = "review-insight-empty";
            empty.textContent = "No rules are currently loaded.";
            panel.appendChild(empty);
            host.appendChild(panel);
            return;
        }

        const content = document.createElement("div");
        content.className = "rules-manage-content";
        const list = document.createElement("div");
        list.className = "rules-manage-list";
        state.rulesManageRows.forEach((row) => {
            const item = document.createElement("div");
            item.className = "rules-manage-item";
            item.classList.toggle("rules-manage-item-active", String(row.id || "") === String(state.rulesManageEditorRuleId || ""));

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = !!state.rulesManageDraftById.get(row.id);
            checkbox.disabled = state.rulesManageSaving;
            checkbox.addEventListener("change", () => {
                state.rulesManageDraftById.set(row.id, !!checkbox.checked);
                helpers.renderRulesHealth();
            });

            const copy = document.createElement("div");
            copy.className = "rules-manage-copy";
            copy.addEventListener("click", () => {
                loadRuleIntoEditor(row.id);
                state.rulesManageStatusMessage = "";
                helpers.renderRulesHealth();
            });

            const title = document.createElement("div");
            title.className = "rules-manage-title";
            title.textContent = `${row.rule_id || row.id} | ${row.item || "-"}`;

            const meta = document.createElement("div");
            meta.className = "rules-manage-meta";
            meta.textContent = `${row.detector_kind || "unknown"} | ${row.severity || "unknown"} | ${(row.file_types || []).join("/") || "-"}`;

            copy.append(title, meta);
            item.append(checkbox, copy);
            list.appendChild(item);
        });

        content.appendChild(list);
        renderRulesManageEditor(content);
        panel.appendChild(content);
        host.appendChild(panel);
    }

    async function loadRulesList(force = false) {
        if (state.rulesManageLoading || (state.rulesManageRows.length && !force)) {
            helpers.renderRulesHealth();
            return;
        }
        state.rulesManageLoading = true;
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/list");
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || `Rules list load failed (${response.status})`);
            }
            applyRulesManagePayload(payload);
            state.rulesManageStatusMessage = "";
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
        } finally {
            state.rulesManageLoading = false;
            helpers.renderRulesHealth();
        }
    }

    async function saveRulesManageUpdates() {
        const updates = getRulesManageUpdates();
        if (!updates.length || state.rulesManageSaving) return;
        state.rulesManageSaving = true;
        helpers.renderRulesHealth();
        try {
            const response = await fetch("/api/rules/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ updates }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || `Rules update failed (${response.status})`);
            }
            applyRulesManagePayload(payload);
            state.rulesManageStatusMessage = `Toggle update complete (${Number(payload.updated_count || updates.length)} items).`;
            await helpers.loadRulesHealth();
        } catch (err) {
            state.rulesManageStatusMessage = (err && err.message) || String(err);
        } finally {
            state.rulesManageSaving = false;
            helpers.renderRulesHealth();
        }
    }

    return {
        applyRulesImportPreview,
        applyRulesManagePayload,
        clearImportPreview,
        deleteCurrentRule,
        ensureRuleEditorState,
        exportRulesManagePayload,
        getRulesManageUpdates,
        loadRuleIntoEditor,
        loadRulesList,
        previewRulesImport,
        readRuleEditorForm,
        renderRulesManagePanel,
        rollbackLatestRules,
        saveRuleEditorForm,
        saveRulesManageUpdates,
        startNewRuleDraft,
        triggerRulesImport,
    };
}
