import {
    fileIdentityKey,
    messageSearchToken,
    normalizeP1RuleId,
    positiveLineOrZero,
    violationResolvedFile,
} from "./utils.js";

const EMPTY_TRIAGE_META = Object.freeze({
    triageKey: "",
    entry: null,
    status: "open",
    suppressed: false,
    reason: "",
    note: "",
});

function normalizeTriageEntry(entryLike) {
    const entry = (entryLike && typeof entryLike === "object") ? entryLike : {};
    return {
        triage_key: String(entry.triage_key || "").trim(),
        status: String(entry.status || "open").trim().toLowerCase() === "suppressed" ? "suppressed" : "open",
        reason: String(entry.reason || "").trim(),
        note: String(entry.note || ""),
        updated_at_ms: Number.parseInt(entry.updated_at_ms, 10) || 0,
        match: {
            file: String((entry.match && entry.match.file) || "").trim(),
            line: positiveLineOrZero(entry.match && entry.match.line),
            rule_id: String((entry.match && entry.match.rule_id) || "").trim(),
            message: String((entry.match && entry.match.message) || "").trim(),
            issue_id: String((entry.match && entry.match.issue_id) || "").trim(),
        },
    };
}

export function buildP1TriageMatch(violation = {}) {
    const primaryRuleId = String(
        violation.ruleId
        || violation.rule_id
        || (Array.isArray(violation.ruleIds) ? violation.ruleIds[0] : "")
        || "",
    ).trim();
    return {
        file: violationResolvedFile(violation, String(violation.object || "")).trim(),
        line: positiveLineOrZero(violation._primary_line || violation.line),
        rule_id: normalizeP1RuleId(primaryRuleId),
        message: String(violation.message || "").trim(),
        issue_id: String(violation.issue_id || violation.issueId || "").trim(),
    };
}

export function buildP1TriageKey(matchLike = {}) {
    const match = buildP1TriageMatch(matchLike);
    const fileKey = fileIdentityKey(match.file);
    const ruleId = normalizeP1RuleId(match.rule_id);
    const messageKey = messageSearchToken(match.message);
    const line = positiveLineOrZero(match.line);
    return [fileKey, ruleId, messageKey, String(line)].join("||");
}

export function buildP1TriageMap(entries = []) {
    const next = new Map();
    (Array.isArray(entries) ? entries : []).forEach((entryLike) => {
        const entry = normalizeTriageEntry(entryLike);
        if (!entry.triage_key) return;
        next.set(entry.triage_key, entry);
    });
    return next;
}

export function getP1TriageMeta(violation = {}, triageByKey = new Map()) {
    const triageKey = buildP1TriageKey(violation);
    if (!triageKey || !(triageByKey instanceof Map)) return { ...EMPTY_TRIAGE_META };
    const entry = triageByKey.get(triageKey) || null;
    if (!entry) {
        return {
            triageKey,
            entry: null,
            status: "open",
            suppressed: false,
            reason: "",
            note: "",
        };
    }
    return {
        triageKey,
        entry,
        status: String(entry.status || "open"),
        suppressed: String(entry.status || "open") === "suppressed",
        reason: String(entry.reason || ""),
        note: String(entry.note || ""),
    };
}

export function applyP1TriageToRow(row = {}, triageByKey = new Map()) {
    if (String(row.source || "").toUpperCase() !== "P1") {
        return {
            ...row,
            p1TriageKey: "",
            p1TriageStatus: "open",
            p1TriageSuppressed: false,
            p1TriageReason: "",
            p1TriageNote: "",
            p1TriageEntry: null,
        };
    }
    const meta = getP1TriageMeta({
        file: row.file,
        line: row.line,
        rule_id: row.ruleId || row.rule_id || (Array.isArray(row.ruleIds) ? row.ruleIds[0] : ""),
        message: row.message,
        issue_id: row.issueId,
        object: row.object,
    }, triageByKey);
    return {
        ...row,
        p1TriageKey: meta.triageKey,
        p1TriageStatus: meta.status,
        p1TriageSuppressed: meta.suppressed,
        p1TriageReason: meta.reason,
        p1TriageNote: meta.note,
        p1TriageEntry: meta.entry,
    };
}

export function shouldHideSuppressedP1Row(row = {}, showSuppressedP1 = false) {
    return String(row.source || "").toUpperCase() === "P1" && !!row.p1TriageSuppressed && !showSuppressedP1;
}

export function excludeSuppressedP1Rows(rows = []) {
    return (Array.isArray(rows) ? rows : []).filter((row) => !shouldHideSuppressedP1Row(row, false));
}

async function readJsonLikeResponse(response) {
    const text = await response.text();
    try {
        return text ? JSON.parse(text) : {};
    } catch (_) {
        return {};
    }
}

export function createP1TriageController({ state, helpers = {} }) {
    let entriesLoaded = false;

    function syncDiagnostics(entryCount, errorMessage = "") {
        if (typeof helpers.updateRendererDiagnostics !== "function") return;
        helpers.updateRendererDiagnostics({
            p1_triage_count: Math.max(0, Number.parseInt(entryCount, 10) || 0),
            p1_triage_error: String(errorMessage || "").trim(),
        });
    }

    function setEntries(entries = []) {
        const safeEntries = Array.isArray(entries) ? entries.map((item) => normalizeTriageEntry(item)) : [];
        state.p1TriageEntries = safeEntries;
        state.p1TriageByKey = buildP1TriageMap(safeEntries);
        state.p1TriageError = "";
        entriesLoaded = true;
        syncDiagnostics(safeEntries.length, "");
        return safeEntries;
    }

    function clearEntries() {
        state.p1TriageEntries = [];
        state.p1TriageByKey = new Map();
        syncDiagnostics(0, state.p1TriageError);
    }

    function reportError(message) {
        state.p1TriageError = String(message || "").trim();
        syncDiagnostics(Array.isArray(state.p1TriageEntries) ? state.p1TriageEntries.length : 0, state.p1TriageError);
    }

    async function loadEntries({ force = false } = {}) {
        if (entriesLoaded && !force) return state.p1TriageEntries;
        state.p1TriageLoading = true;
        try {
            const response = await fetch("/api/triage/p1");
            const payload = await readJsonLikeResponse(response);
            if (!response.ok) {
                throw new Error(payload.error || `P1 triage load failed (${response.status})`);
            }
            return setEntries(payload.entries || []);
        } catch (err) {
            clearEntries();
            entriesLoaded = false;
            reportError((err && err.message) || String(err));
            return [];
        } finally {
            state.p1TriageLoading = false;
        }
    }

    function getViolationTriageMeta(violation = {}) {
        return getP1TriageMeta(violation, state.p1TriageByKey);
    }

    function setShowSuppressedP1(value) {
        state.showSuppressedP1 = !!value;
        return state.showSuppressedP1;
    }

    async function postJson(path, payload) {
        const response = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {}),
        });
        const data = await readJsonLikeResponse(response);
        if (!response.ok) {
            throw new Error(data.error || `${path} failed (${response.status})`);
        }
        return data;
    }

    async function suppressViolation(violation = {}, { reason = "", note = "" } = {}) {
        if (!entriesLoaded) {
            await loadEntries();
        }
        const match = buildP1TriageMatch(violation);
        const triageKey = buildP1TriageKey(match);
        if (!triageKey) throw new Error("P1 triage key is missing");
        const payload = await postJson("/api/triage/p1/upsert", {
            triage_key: triageKey,
            status: "suppressed",
            reason,
            note,
            match,
        });
        const nextEntries = Array.isArray(state.p1TriageEntries) ? [...state.p1TriageEntries] : [];
        const normalizedEntry = normalizeTriageEntry(payload.entry || {});
        const existingIndex = nextEntries.findIndex((entry) => String(entry.triage_key || "") === normalizedEntry.triage_key);
        if (existingIndex >= 0) nextEntries.splice(existingIndex, 1, normalizedEntry);
        else nextEntries.push(normalizedEntry);
        setEntries(nextEntries);
        return normalizedEntry;
    }

    async function unsuppressViolation(violation = {}) {
        if (!entriesLoaded) {
            await loadEntries();
        }
        const triageKey = buildP1TriageKey(violation);
        if (!triageKey) throw new Error("P1 triage key is missing");
        await postJson("/api/triage/p1/delete", { triage_key: triageKey });
        const nextEntries = (Array.isArray(state.p1TriageEntries) ? state.p1TriageEntries : []).filter(
            (entry) => String(entry.triage_key || "") !== triageKey,
        );
        setEntries(nextEntries);
        return triageKey;
    }

    return {
        buildP1TriageKey: (violation = {}) => buildP1TriageKey(violation),
        getViolationTriageMeta,
        loadEntries,
        setShowSuppressedP1,
        suppressViolation,
        unsuppressViolation,
    };
}
