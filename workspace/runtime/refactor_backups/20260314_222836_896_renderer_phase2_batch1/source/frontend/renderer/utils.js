const P1_RULE_ALIAS_MAP = {
    "cfg-perf-01": "PERF-01",
    "cfg-perf-02": "PERF-02",
    "cfg-perf-02-dpt-in-01": "PERF-02-WHERE-DPT-IN-01",
    "cfg-perf-03-active-delay-01": "PERF-03-ACTIVE-DELAY-01",
    "cfg-hard-01": "HARD-01",
    "cfg-clean-dup-01": "CLEAN-DUP-01",
    "cfg-log-dbg-01": "LOG-DBG-01",
    "cfg-log-level-01": "LOG-LEVEL-01",
    "cfg-db-01": "DB-01",
    "cfg-db-02": "DB-02",
    "cfg-active-01": "ACTIVE-01",
    "cfg-dup-act-01": "DUP-ACT-01",
    "cfg-getmultivalue-adopt-01": "PERF-GETMULTIVALUE-ADOPT-01",
};

export function basenamePath(value) {
    const text = String(value || "");
    if (!text) return "";
    const parts = text.split(/[\\/]/);
    return parts[parts.length - 1] || text;
}

export function fileIdentityKey(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return text.replace(/\\/g, "/").toLowerCase();
}

export function violationResolvedFile(violation, fallback = "") {
    return String(
        (violation && (
            violation.file_path
            || violation.parent_file_path
            || violation.file
            || violation.file_name
            || violation.filename
            || violation.object
        )) || fallback || "",
    );
}

export function violationDisplayFile(violation, fallback = "") {
    return basenamePath(violationResolvedFile(violation, fallback)) || String((violation && violation.object) || fallback || "");
}

export function sameFileIdentity(left, right) {
    const leftKey = fileIdentityKey(left);
    const rightKey = fileIdentityKey(right);
    if (!leftKey || !rightKey) return false;
    if (leftKey === rightKey) return true;
    return basenamePath(leftKey) === basenamePath(rightKey);
}

export function positiveLineOrZero(value) {
    const line = Number.parseInt(value, 10);
    return Number.isFinite(line) && line > 0 ? line : 0;
}

export function normalizeP1RuleId(ruleId) {
    const raw = String(ruleId || "").trim();
    if (!raw) return "UNKNOWN";
    const lowered = raw.toLowerCase();
    if (P1_RULE_ALIAS_MAP[lowered]) {
        return String(P1_RULE_ALIAS_MAP[lowered]);
    }
    return raw.toUpperCase();
}

export function countChar(text, ch) {
    let count = 0;
    const s = String(text || "");
    for (let i = 0; i < s.length; i += 1) {
        if (s[i] === ch) count += 1;
    }
    return count;
}

export function compactUiText(value, maxLength = 160) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength - 3)}...` : text;
}

export function stripDetailEvidence(text) {
    return String(text || "").replace(/\s*\(근거:\s*.*\)\s*$/u, "").trim();
}

export function truncateUiText(value, maxLength = 96) {
    const text = String(value || "").trim();
    if (text.length <= maxLength) return text;
    return `${text.slice(0, Math.max(0, maxLength - 1))}…`;
}

export function truncateMiddle(text, maxLen = 140) {
    const s = String(text || "").trim();
    if (s.length <= maxLen) return s;
    const keep = Math.max(20, Math.floor((maxLen - 3) / 2));
    return `${s.slice(0, keep)}...${s.slice(s.length - keep)}`;
}

export function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

export function isLikelyFunctionKeyword(name) {
    const lowered = String(name || "").toLowerCase();
    return lowered === "if"
        || lowered === "for"
        || lowered === "while"
        || lowered === "switch"
        || lowered === "catch"
        || lowered === "return";
}

export function buildFunctionScopes(lines) {
    const src = Array.isArray(lines) ? lines : [];
    const scopes = [];
    const fnHeaderRe = /^\s*(?:[A-Za-z_]\w*\s+)*([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$/;

    for (let i = 0; i < src.length; i += 1) {
        const raw = String(src[i] || "");
        const trimmed = raw.trim();
        if (!trimmed || trimmed.startsWith("//") || trimmed.startsWith("*")) continue;

        const m = trimmed.match(fnHeaderRe);
        if (!m) continue;
        const fnName = String(m[1] || "").trim();
        if (!fnName || isLikelyFunctionKeyword(fnName)) continue;

        let openLineIdx = -1;
        if (trimmed.includes("{")) {
            openLineIdx = i;
        } else {
            for (let j = i + 1; j < Math.min(src.length, i + 4); j += 1) {
                const t = String(src[j] || "").trim();
                if (!t) continue;
                if (t.startsWith("{")) {
                    openLineIdx = j;
                }
                break;
            }
        }
        if (openLineIdx < 0) continue;

        let depth = 0;
        let endLineIdx = -1;
        for (let k = openLineIdx; k < src.length; k += 1) {
            const lineText = String(src[k] || "");
            depth += countChar(lineText, "{");
            depth -= countChar(lineText, "}");
            if (depth <= 0 && k >= openLineIdx) {
                endLineIdx = k;
                break;
            }
        }
        if (endLineIdx < openLineIdx) continue;

        scopes.push({
            name: fnName,
            start: i + 1,
            end: endLineIdx + 1,
        });
        i = Math.max(i, endLineIdx);
    }

    return scopes;
}

export function findScopeForLine(scopes, lineNo) {
    const targetLine = positiveLineOrZero(lineNo);
    if (targetLine <= 0 || !Array.isArray(scopes) || scopes.length === 0) return null;
    let picked = null;
    for (const s of scopes) {
        const start = positiveLineOrZero(s && s.start);
        const end = positiveLineOrZero(s && s.end);
        if (start <= 0 || end <= 0) continue;
        if (targetLine >= start && targetLine <= end) {
            if (!picked || ((end - start) < (picked.end - picked.start))) {
                picked = { name: String((s && s.name) || "Global"), start, end };
            }
        }
    }
    return picked;
}

export function parseReviewedMetaLine(lineText) {
    const text = String(lineText || "");
    const m = text.match(/^\/\/\s*\[META\]\s*(.+)$/i);
    if (!m || !m[1]) return null;
    const meta = {};
    String(m[1]).split(";").forEach((entry) => {
        const token = String(entry || "").trim();
        if (!token) return;
        const sep = token.indexOf("=");
        if (sep <= 0) return;
        const key = token.slice(0, sep).trim().toLowerCase();
        const value = token.slice(sep + 1).trim();
        meta[key] = value;
    });
    return meta;
}

export function parseReviewedSeverity(reviewLine) {
    const text = String(reviewLine || "");
    const m = text.match(/^\/\/\s*\[REVIEW\]\s*([A-Za-z]+)/i);
    return m && m[1] ? m[1] : "Info";
}

export function parseReviewedTodoBlocks(content, fileName = "") {
    const lines = String(content || "").split("\n");
    const blocks = [];
    for (let i = 0; i < lines.length; i += 1) {
        const raw = String(lines[i] || "");
        if (!/^\/\/\s*>>TODO/i.test(raw.trim())) continue;

        const block = {
            file: basenamePath(fileName),
            todo_line: i + 1,
            message: "",
            review_line: "",
            severity: "Info",
            meta: {},
        };

        let j = i + 1;
        while (j < lines.length) {
            const lraw = String(lines[j] || "");
            const ltrim = lraw.trim();
            if (!ltrim.startsWith("//")) break;

            if (/^\/\/\s*\[REVIEW\]/i.test(ltrim)) {
                block.review_line = ltrim;
                block.severity = parseReviewedSeverity(ltrim);
            } else if (/^\/\/\s*\[META\]/i.test(ltrim)) {
                const meta = parseReviewedMetaLine(ltrim);
                if (meta && typeof meta === "object") {
                    block.meta = meta;
                }
            } else if (!/^\/\/\s*>>TODO/i.test(ltrim) && !block.message) {
                block.message = ltrim.replace(/^\/\/\s*/, "").trim();
            }
            j += 1;
        }
        blocks.push(block);
        i = Math.max(i, j - 1);
    }
    return blocks;
}

export function normalizeReviewedMessageKey(message) {
    return String(message || "")
        .replace(/^\/\/\s*/g, "")
        .replace(/\[review\]\s*warning\s*-\s*/gi, "")
        .replace(/\[review\]\s*info\s*-\s*/gi, "")
        .replace(/[()[\]{}.,:;!?'"`]/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
}

export function inferRuleIdFromReviewedBlock(block) {
    const meta = (block && block.meta && typeof block.meta === "object") ? block.meta : {};
    const metaRule = normalizeP1RuleId(meta.rule_id);
    if (metaRule !== "UNKNOWN") {
        return { inferredRuleId: metaRule, confidence: 1.0, source: "meta" };
    }
    const reviewLine = String((block && block.review_line) || "").toLowerCase();
    const message = String((block && block.message) || "").toLowerCase();
    const text = `${reviewLine} ${message}`;

    const rules = [
        { pattern: /dpget|반복\s*구간\s*dpget|일괄\/캐시\s*처리\s*권장/, ruleId: "PERF-DPGET-BATCH-01", confidence: 0.9 },
        { pattern: /dpsetwait|dpsettimed/, ruleId: "PERF-05", confidence: 0.9 },
        { pattern: /연속\s*dpset|반복\s*구간\s*dpset|dpset.*일괄|dpset.*배치|배치\/동기\/조건부 업데이트/, ruleId: "PERF-DPSET-BATCH-01", confidence: 0.88 },
        { pattern: /active\/?enable|enable\/?active|active.*조건|enable.*조건/, ruleId: "ACTIVE-01", confidence: 0.88 },
        { pattern: /try\/catch|getlasterror|예외 처리/, ruleId: "EXC-TRY-01", confidence: 0.85 },
        { pattern: /setmultivalue|다중\s*set\s*업데이트/, ruleId: "PERF-SETMULTIVALUE-ADOPT-01", confidence: 0.86 },
        { pattern: /getmultivalue|다중\s*get\s*업데이트/, ruleId: "PERF-GETMULTIVALUE-ADOPT-01", confidence: 0.86 },
        { pattern: /dp query.*_dpt.*in/, ruleId: "PERF-02-WHERE-DPT-IN-01", confidence: 0.82 },
        { pattern: /dp query|전체 범위 조회/, ruleId: "PERF-02", confidence: 0.8 },
        { pattern: /divide by zero|0.*나눗셈|분모.*0/, ruleId: "SAFE-DIV-01", confidence: 0.82 },
        { pattern: /유효성|범위|형식.*검증/, ruleId: "VAL-01", confidence: 0.78 },
        { pattern: /디버그 로그|debug/, ruleId: "LOG-DBG-01", confidence: 0.78 },
        { pattern: /로그 레벨/, ruleId: "LOG-LEVEL-01", confidence: 0.78 },
        { pattern: /중복 동작|중복 처리/, ruleId: "DUP-ACT-01", confidence: 0.8 },
    ];
    for (const entry of rules) {
        if (entry.pattern.test(text)) {
            return { inferredRuleId: entry.ruleId, confidence: entry.confidence, source: "review_text" };
        }
    }
    return { inferredRuleId: "UNKNOWN", confidence: 0, source: "none" };
}

export function parseUnifiedDiffForSplit(diffText) {
    const lines = String(diffText || "").split(/\r?\n/);
    const beforeRows = [];
    const afterRows = [];
    let oldLine = 0;
    let newLine = 0;
    let pendingDeletes = [];
    let pendingAdds = [];

    const flushPending = () => {
        if (!pendingDeletes.length && !pendingAdds.length) return;
        const size = Math.max(pendingDeletes.length, pendingAdds.length);
        for (let idx = 0; idx < size; idx += 1) {
            const before = pendingDeletes[idx] || null;
            const after = pendingAdds[idx] || null;
            beforeRows.push({
                lineNo: before ? before.lineNo : 0,
                text: before ? before.text : "",
                kind: before && after ? "change-old" : before ? "remove" : "placeholder",
            });
            afterRows.push({
                lineNo: after ? after.lineNo : 0,
                text: after ? after.text : "",
                kind: before && after ? "change-new" : after ? "add" : "placeholder",
            });
        }
        pendingDeletes = [];
        pendingAdds = [];
    };

    for (const rawLine of lines) {
        if (/^---\s/.test(rawLine) || /^\+\+\+\s/.test(rawLine) || /^\\ No newline/.test(rawLine)) {
            continue;
        }
        const headerMatch = rawLine.match(/^@@\s+\-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
        if (headerMatch) {
            flushPending();
            oldLine = Number.parseInt(headerMatch[1], 10) || 0;
            newLine = Number.parseInt(headerMatch[2], 10) || 0;
            continue;
        }
        if (!rawLine) {
            flushPending();
            beforeRows.push({ lineNo: oldLine, text: "", kind: "context" });
            afterRows.push({ lineNo: newLine, text: "", kind: "context" });
            oldLine += 1;
            newLine += 1;
            continue;
        }
        const prefix = rawLine[0];
        const text = rawLine.slice(1);
        if (prefix === " ") {
            flushPending();
            beforeRows.push({ lineNo: oldLine, text, kind: "context" });
            afterRows.push({ lineNo: newLine, text, kind: "context" });
            oldLine += 1;
            newLine += 1;
        } else if (prefix === "-") {
            pendingDeletes.push({ lineNo: oldLine, text });
            oldLine += 1;
        } else if (prefix === "+") {
            pendingAdds.push({ lineNo: newLine, text });
            newLine += 1;
        }
    }
    flushPending();
    return { beforeRows, afterRows };
}

export function scoreSeverityWeight(severity) {
    const key = String(severity || "").trim().toLowerCase();
    if (key === "critical") return 9;
    if (key === "warning") return 4;
    return 1;
}

export function scoreSourceWeight(source) {
    const key = String(source || "").trim().toLowerCase();
    if (key === "p1") return 4;
    if (key === "p2") return 3;
    if (key === "p3") return 2;
    return 1;
}

export function normalizeInsightToken(value, fallback = "global") {
    const text = String(value || "").trim();
    return text ? text.toLowerCase() : fallback;
}

export function summarizeRuleCluster(ruleIds) {
    const ids = Array.isArray(ruleIds) ? ruleIds : [];
    const normalized = ids
        .map((id) => String(id || "").trim())
        .filter(Boolean);
    if (!normalized.length) {
        return { label: "규칙 미상", familyCount: 0, dominantFamily: "unknown", dominantCount: 0, repeatedFamilyBonus: 0 };
    }
    const families = new Map();
    normalized.forEach((id) => {
        const family = normalizeInsightToken(id.split("-")[0] || id, "unknown");
        families.set(family, (families.get(family) || 0) + 1);
    });
    let dominantFamily = "unknown";
    let dominantCount = 0;
    families.forEach((count, family) => {
        if (count > dominantCount) {
            dominantFamily = family;
            dominantCount = count;
        }
    });
    return {
        label: dominantFamily.toUpperCase(),
        familyCount: families.size,
        dominantFamily,
        dominantCount,
        repeatedFamilyBonus: Math.min(5, Math.max(0, dominantCount - 1)),
    };
}
