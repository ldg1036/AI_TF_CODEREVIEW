import {
    basenamePath,
    normalizeP1RuleId,
    positiveLineOrZero,
    stripDetailEvidence,
    truncateMiddle,
} from "./utils.js";

export function createDetailPanelController({ dom, state, helpers }) {
    function appendDetailFact(container, label, value) {
        const row = document.createElement("div");
        row.className = "detail-fact-row";
        const labelEl = document.createElement("div");
        labelEl.className = "detail-fact-label";
        labelEl.textContent = label;
        const valueEl = document.createElement("div");
        valueEl.className = "detail-fact-value";
        valueEl.textContent = value;
        row.append(labelEl, valueEl);
        container.appendChild(row);
    }

    function appendDetailNote(container, text, tone = "") {
        const note = document.createElement("p");
        note.className = `detail-note${tone ? ` ${tone}` : ""}`;
        note.textContent = text;
        container.appendChild(note);
    }

    function renderInspectorSelectionMeta(violation, options = {}) {
        if (!dom.inspectorSelectionMeta) return;
        const chips = [];
        const objectName = basenamePath((violation && (violation.file || violation.object)) || "")
            || String((violation && violation.object) || "").trim();
        const source = String((violation && violation.priority_origin) || "").trim();
        const lineNo = positiveLineOrZero(
            (options && options.jumpResult && options.jumpResult.ok && state.currentHighlightedLine)
            || (options && options.jumpPendingLine)
            || (violation && (violation._jump_target_line || violation.line)),
        );
        const ruleId = String((violation && violation.rule_id) || "").trim();
        if (objectName) chips.push({ label: "객체", value: objectName });
        if (lineNo > 0) chips.push({ label: "라인", value: String(lineNo) });
        if (ruleId) chips.push({ label: "Rule", value: ruleId });
        if (source) chips.push({ label: "출처", value: source });
        if (!chips.length) {
            dom.inspectorSelectionMeta.replaceChildren();
            dom.inspectorSelectionMeta.classList.add("hidden");
            return;
        }
        dom.inspectorSelectionMeta.replaceChildren(...chips.map((chip) => {
            const node = document.createElement("span");
            node.className = "inspector-selection-chip";
            node.textContent = `${chip.label} ${chip.value}`;
            return node;
        }));
        dom.inspectorSelectionMeta.classList.remove("hidden");
    }

    function localizeCtrlppMessage(message) {
        const text = String(message || "");
        if (!text) return text;

        let out = text;
        out = out.replace(/^Uninitialized variable:\s*(.+)$/i, "초기화되지 않은 변수: $1");
        out = out.replace(
            /^It is potentially a safety issue to use the function\s+(.+)$/i,
            "함수 $1 사용은 잠재적인 안전성 이슈가 될 수 있습니다",
        );
        out = out.replace(
            /^It is really neccessary to use the function\s+(.+)$/i,
            "함수 $1 사용이 정말 필요한지 검토하세요",
        );
        out = out.replace(
            /^It is really necessary to use the function\s+(.+)$/i,
            "함수 $1 사용이 정말 필요한지 검토하세요",
        );
        out = out.replace(
            /^Cppcheck cannot find all the include files \(use --check-config for details\)$/i,
            "Cppcheck가 일부 include 파일을 찾지 못했습니다 (--check-config로 상세 확인)",
        );
        return out;
    }

    function localizeCtrlppByRuleId(ruleId, message, verbose) {
        const id = String(ruleId || "").toLowerCase();
        const msg = String(message || "");
        const details = String(verbose || "");
        const mapping = [
            { keys: ["uninitializedvariable", "uninitvar"], text: "초기화되지 않은 변수 사용 가능성이 있습니다." },
            { keys: ["nullpointer", "nullpointerdereference"], text: "널 포인터 접근 가능성이 있습니다." },
            { keys: ["checklibrarynoreturn", "noreturn"], text: "반환값/예외 처리 누락 가능성이 있습니다." },
            { keys: ["memleak", "resourceleak"], text: "메모리/자원 해제 누락 가능성이 있습니다." },
            { keys: ["unusedfunction", "unusedvariable"], text: "미사용 코드(함수/변수)가 포함되어 있습니다." },
            { keys: ["syntaxerror", "parseerror"], text: "문법/구문 오류 가능성이 있습니다." },
            { keys: ["bufferaccessoutofbounds", "outofbounds"], text: "배열/버퍼 경계 초과 접근 가능성이 있습니다." },
            { keys: ["useafterfree"], text: "해제된 자원 접근(use-after-free) 가능성이 있습니다." },
            { keys: ["shadowvariable", "shadowedvariable"], text: "변수 그림자(shadowing)로 인한 혼동 가능성이 있습니다." },
        ];
        for (const entry of mapping) {
            if (entry.keys.some((key) => id.includes(key))) return entry.text;
        }
        if (id === "ctrlppcheck.info") {
            const localized = localizeCtrlppMessage(msg || details);
            return localized || "CtrlppCheck 정보성 메시지입니다.";
        }
        return "";
    }

    function localizeCtrlppByPattern(message) {
        const text = String(message || "").trim();
        if (!text) return "";
        const localized = localizeCtrlppMessage(text);
        if (localized !== text) return localized;

        const nullMatch = text.match(/null(?:\s+pointer)?\s+([A-Za-z_][A-Za-z0-9_]*)?/i);
        if (nullMatch) {
            const name = String(nullMatch[1] || "").trim();
            return name ? `포인터 ${name}가 null일 수 있어 접근 시 오류 가능성이 있습니다.` : "null 포인터 접근 가능성이 있습니다.";
        }
        const callMatch = text.match(/function\s+([A-Za-z_][A-Za-z0-9_]*)/i);
        if (callMatch) return `함수 ${callMatch[1]} 호출부에서 안전성/예외 처리 점검이 필요합니다.`;
        const varMatch = text.match(/variable:\s*([A-Za-z_][A-Za-z0-9_]*)/i);
        if (varMatch) return `변수 ${varMatch[1]} 사용 전에 초기화/유효성 검증이 필요합니다.`;
        return "";
    }

    function buildP2LocalizedMessage(violation) {
        const ruleId = String((violation && violation.rule_id) || "");
        const rawMessage = String((violation && violation.message) || "").trim();
        const verbose = String((violation && violation.verbose) || "").trim();
        const byRule = localizeCtrlppByRuleId(ruleId, rawMessage, verbose);
        const byPattern = localizeCtrlppByPattern(rawMessage || verbose);
        const localizedText = byRule || byPattern || (rawMessage ? `(원문) ${truncateMiddle(rawMessage, 180)}` : "P2 점검 메시지");
        const shortText = truncateMiddle(localizedText.replace(/^\(원문\)\s*/i, ""), 80) || "P2 점검 메시지";
        return { shortText, localizedText, rawText: rawMessage || verbose || "" };
    }

    function buildP2DetailBlocks(violation) {
        const ruleId = String((violation && violation.rule_id) || "unknown");
        const severity = String((violation && (violation.severity || violation.type)) || "information").toLowerCase();
        const lineNo = positiveLineOrZero(violation && violation.line);
        const fileName = basenamePath(violation && (violation.file || violation.file_name || violation.filename));
        const localized = buildP2LocalizedMessage(violation);

        const cause = localized.localizedText || "P2 정적 분석에서 위험 신호가 감지되었습니다.";
        const impactMap = {
            error: "실행 중 오류 또는 안전성 문제로 이어질 가능성이 높습니다.",
            warning: "기능 안정성/유지보수성 저하 가능성이 있습니다.",
            performance: "성능 저하 또는 불필요한 리소스 사용이 발생할 수 있습니다.",
            information: "즉시 오류는 아니지만 코드 품질 개선이 필요할 수 있습니다.",
            style: "가독성/일관성 저하로 유지보수 비용이 증가할 수 있습니다.",
            portability: "환경/버전 차이에서 동작 차이가 발생할 수 있습니다.",
        };
        const impact = impactMap[severity] || "코드 품질 및 안정성에 부정적 영향이 있을 수 있습니다.";

        let action = "관련 코드에서 입력값 검증, 예외 처리, 반환값 확인을 추가하고 동일 패턴을 함께 점검하세요.";
        const lowerRule = ruleId.toLowerCase();
        if (lowerRule.includes("uninitialized")) {
            action = "변수 선언 시 초기값을 명시하고 사용 전에 초기화 경로를 보장하세요.";
        } else if (lowerRule.includes("null")) {
            action = "포인터/핸들 사용 전 null 검사와 실패 분기 처리를 추가하세요.";
        } else if (lowerRule.includes("noreturn")) {
            action = "함수 반환값을 확인하고 실패 시 로그/복구 로직을 추가하세요.";
        }

        const evidenceParts = [];
        if (fileName) evidenceParts.push(fileName);
        if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
        evidenceParts.push(`rule_id=${ruleId || "unknown"}`);
        const evidence = evidenceParts.join(", ");

        return {
            cause: `원인: ${cause}`,
            impact: `영향: ${impact}`,
            action: `권장조치: ${action} (근거: ${evidence})`,
            raw: localized.rawText ? `원문: ${truncateMiddle(localized.rawText, 180)}` : "",
        };
    }

    function buildP1DetailBlocks(violation) {
        const rawRuleId = String((violation && violation.rule_id) || "unknown");
        const message = String((violation && violation.message) || "").trim();
        const severityRaw = String((violation && violation.severity) || "warning");
        const severity = helpers.severityFilterKey ? helpers.severityFilterKey(severityRaw) : "info";
        const lineNo = positiveLineOrZero(violation && violation.line);
        const fileName = basenamePath(violation && (violation.file || violation.file_name || violation.filename || violation.object));
        const ruleUpper = normalizeP1RuleId(rawRuleId);
        const msgLower = message.toLowerCase();

        let cause = message || "P1 정적 규칙 분석에서 개선이 필요한 코드 패턴이 감지되었습니다.";
        let impact = "코드 품질 및 유지보수성 저하 가능성이 있습니다.";
        let action = "규칙 의도에 맞게 로직을 정리하고 동일 패턴을 함께 점검하세요.";

        const exactTemplates = {
            "CLEAN-DUP-01": {
                cause: "동일/유사 코드가 반복되어 중복 패턴이 감지되었습니다.",
                impact: "수정 누락 가능성이 커지고 유지보수 비용이 증가할 수 있습니다.",
                action: "공통 로직을 함수/헬퍼로 추출해 중복 코드를 제거하세요.",
            },
            "CLEAN-DEAD-01": {
                cause: "도달 불가 또는 미사용 코드가 감지되었습니다.",
                impact: "가독성이 저하되고 코드 의도를 오해할 가능성이 있습니다.",
                action: "불필요 코드를 제거하고 참조/호출 영향 범위를 함께 점검하세요.",
            },
            "HARD-01": {
                cause: "하드코딩된 문자열/값 사용이 감지되었습니다.",
                impact: "환경 변경 시 수정 범위가 커지고 운영 유연성이 저하될 수 있습니다.",
                action: "상수 또는 Config 기반으로 분리하고 의미 있는 이름을 부여하세요.",
            },
            "HARD-02": {
                cause: "하드코딩된 값 사용 패턴이 감지되었습니다.",
                impact: "배포 환경별 조건 대응이 어려워지고 변경 리스크가 증가할 수 있습니다.",
                action: "값을 설정/상수화하고 변경 가능한 파라미터로 분리하세요.",
            },
            "HARD-03": {
                cause: "하드코딩 값 의존 패턴이 감지되었습니다.",
                impact: "운영 정책 변경 시 코드 수정이 반복되어 장애 가능성이 높아질 수 있습니다.",
                action: "Config/상수 테이블로 이관해 값 변경이 코드 수정 없이 가능하도록 정리하세요.",
            },
            "CFG-01": {
                cause: "config 계약 또는 키 정합성 불일치 가능성이 감지되었습니다.",
                impact: "런타임 설정 오동작으로 기능 실패가 발생할 수 있습니다.",
                action: "config 키/타입/기본값을 점검하고 누락 케이스에 대한 방어 분기를 추가하세요.",
            },
            "CFG-ERR-01": {
                cause: "config 로드/검증 오류 처리 누락 가능성이 감지되었습니다.",
                impact: "설정 오류가 연쇄 장애로 전파될 수 있습니다.",
                action: "config 오류 처리 경로를 명시하고 실패 시 안전한 기본 동작을 정의하세요.",
            },
            "STYLE-NAME-01": {
                cause: "명명 규칙 위반 가능성이 감지되었습니다.",
                impact: "코드 의도 파악이 어려워져 협업 비용이 증가할 수 있습니다.",
                action: "프로젝트 명명 규칙에 맞게 식별자 이름을 정리하세요.",
            },
            "STYLE-INDENT-01": {
                cause: "들여쓰기/정렬 규칙 위반 가능성이 감지되었습니다.",
                impact: "가독성이 저하되고 리뷰 효율이 떨어질 수 있습니다.",
                action: "일관된 들여쓰기 규칙으로 정리하고 블록 구조를 명확히 맞추세요.",
            },
            "STYLE-HEADER-01": {
                cause: "헤더/주석 스타일 규칙 위반 가능성이 감지되었습니다.",
                impact: "파일 목적/변경 이력 파악이 어려워질 수 있습니다.",
                action: "프로젝트 표준 헤더/주석 포맷을 적용하세요.",
            },
            "STD-01": {
                cause: "코딩 표준 규칙 위반 가능성이 감지되었습니다.",
                impact: "팀 내 일관성이 깨져 유지보수 효율이 저하될 수 있습니다.",
                action: "표준 가이드에 맞춰 코드 스타일과 구조를 정리하세요.",
            },
            "EXC-TRY-01": {
                cause: "예외 가능 구간에 대한 보호 처리 부족이 감지되었습니다.",
                impact: "실패가 상위 로직으로 전파되어 복구 지연이 발생할 수 있습니다.",
                action: "try-catch와 오류 로깅/복구 분기를 추가해 예외 경로를 명시적으로 처리하세요.",
            },
            "COMP-01": {
                cause: "복잡도 과다 패턴이 감지되었습니다.",
                impact: "이해/테스트 난이도가 올라가 결함 유입률이 증가할 수 있습니다.",
                action: "함수를 분리하고 분기 구조를 단순화해 복잡도를 낮추세요.",
            },
            "COMP-02": {
                cause: "분기 과밀 또는 과도한 복합 조건 패턴이 감지되었습니다.",
                impact: "수정 시 사이드이펙트 가능성이 커질 수 있습니다.",
                action: "조건식을 분해하고 조기 반환 패턴으로 로직 흐름을 단순화하세요.",
            },
        };
        const prefixTemplates = [
            ["PERF-", { cause: "반복 호출/업데이트 패턴으로 인한 비효율 가능성이 감지되었습니다.", impact: "불필요한 호출 누적으로 응답 지연 및 리소스 사용량 증가가 발생할 수 있습니다.", action: "반복 호출을 묶음 처리하거나 배치 방식으로 변경하고, 동일 구간 호출 횟수를 줄이세요." }],
            ["SEC-", { cause: "입력값 검증 또는 보안 방어 로직이 충분하지 않은 패턴이 감지되었습니다.", impact: "비정상 입력으로 인한 오동작 또는 보안 취약점으로 이어질 수 있습니다.", action: "입력값 검증/정규화와 방어 로직을 추가하고, 외부 입력 경로를 우선 점검하세요." }],
            ["DB-", { cause: "데이터 조회/갱신 쿼리 관리 규칙 위반 가능성이 감지되었습니다.", impact: "쿼리 변경 영향 추적이 어려워지고 운영 안정성이 저하될 수 있습니다.", action: "쿼리 작성 방식을 표준화하고 바인딩/주석/오류처리 규칙을 보강하세요." }],
            ["SAFE-", { cause: "안전성 관련 보호 조건이 부족한 코드 패턴이 감지되었습니다.", impact: "예외 상황에서 런타임 오류나 예기치 않은 상태 전이가 발생할 수 있습니다.", action: "가드 조건과 실패 분기 처리를 보강하고, 예외 경로를 명시적으로 처리하세요." }],
            ["VAL-", { cause: "값 유효성 검증이 누락되었거나 불충분한 패턴이 감지되었습니다.", impact: "잘못된 데이터 전파로 기능 오작동 및 디버깅 비용 증가가 발생할 수 있습니다.", action: "입력/중간값 검증을 추가하고 범위/형식 체크를 명확히 분리하세요." }],
            ["LOG-", { cause: "로그 처리 규칙 위반 가능성이 감지되었습니다.", impact: "운영 이슈 추적성이 저하되어 장애 분석 시간이 증가할 수 있습니다.", action: "로그 레벨과 메시지 포맷을 규칙에 맞게 정리하고 핵심 분기 로그를 보완하세요." }],
            ["CLEAN-", { cause: "코드 정리(클린업) 규칙 위반 가능성이 감지되었습니다.", impact: "가독성과 유지보수성이 저하될 수 있습니다.", action: "중복/미사용/불필요 코드를 정리하고 공통 로직으로 통합하세요." }],
            ["HARD-", { cause: "하드코딩 지양 규칙 위반 가능성이 감지되었습니다.", impact: "환경/요구사항 변경 대응이 어려워질 수 있습니다.", action: "하드코딩 값을 설정/상수화하고 코드 의존도를 낮추세요." }],
            ["CFG-", { cause: "설정(config) 정합성 규칙 위반 가능성이 감지되었습니다.", impact: "런타임 설정 오류로 기능 오작동이 발생할 수 있습니다.", action: "config 키/기본값/오류처리 분기를 점검해 설정 계약을 맞추세요." }],
            ["STYLE-", { cause: "코딩 스타일 규칙 위반 가능성이 감지되었습니다.", impact: "협업 가독성과 일관성이 저하될 수 있습니다.", action: "팀 스타일 가이드에 맞게 명명/들여쓰기/헤더를 정리하세요." }],
            ["EXC-", { cause: "예외 처리 규칙 위반 가능성이 감지되었습니다.", impact: "실패 전파로 장애 분석/복구 시간이 증가할 수 있습니다.", action: "예외 처리와 로그/복구 분기를 명시적으로 보강하세요." }],
            ["ACTIVE-", { cause: "활성 상태/실행 조건 검증 규칙 위반 가능성이 감지되었습니다.", impact: "비활성 구간에서 동작이 수행되어 상태 불일치가 발생할 수 있습니다.", action: "Active/Enable 조건 가드와 실패 경로 처리를 명시적으로 추가하세요." }],
            ["DUP-", { cause: "중복 동작 방지 규칙 위반 가능성이 감지되었습니다.", impact: "중복 호출 누적으로 성능 저하와 예기치 않은 동작이 발생할 수 있습니다.", action: "중복 방지 가드와 변경 감지 조건을 추가해 반복 동작을 줄이세요." }],
            ["COMP-", { cause: "복잡도 관리 규칙 위반 가능성이 감지되었습니다.", impact: "코드 이해도 저하로 결함 유입 위험이 높아질 수 있습니다.", action: "함수 분리, 분기 단순화, 조기 반환으로 복잡도를 낮추세요." }],
        ];
        const exact = exactTemplates[ruleUpper];
        if (exact) {
            cause = message || exact.cause;
            impact = exact.impact;
            action = exact.action;
        } else {
            for (const [prefix, template] of prefixTemplates) {
                if (ruleUpper.startsWith(prefix)) {
                    cause = message || template.cause;
                    impact = template.impact;
                    action = template.action;
                    break;
                }
            }
            if (!exact && ruleUpper === "UNKNOWN" && (msgLower.includes("성능") || msgLower.includes("update"))) {
                cause = message || "반복 호출/업데이트 패턴으로 인한 비효율 가능성이 감지되었습니다.";
                impact = "불필요한 호출 누적으로 응답 지연 및 리소스 사용량 증가가 발생할 수 있습니다.";
                action = "반복 호출을 묶음 처리하거나 배치 방식으로 변경하고, 동일 구간 호출 횟수를 줄이세요.";
            }
        }
        if (severity === "critical") {
            impact = `${impact} (긴급도: 치명, 즉시 수정 필요)`;
        }
        const evidenceParts = [];
        if (fileName) evidenceParts.push(fileName);
        if (lineNo > 0) evidenceParts.push(`line ${lineNo}`);
        evidenceParts.push(`rule_id=${ruleUpper || "unknown"}`);
        const evidence = evidenceParts.join(", ");
        return {
            cause: `원인: ${truncateMiddle(cause, 160)}`,
            impact: `영향: ${truncateMiddle(impact, 160)}`,
            action: `권장조치: ${truncateMiddle(action, 120)} (근거: ${evidence})`,
            raw: "",
        };
    }

    function renderDetailDescriptionBlocks(container, blocks) {
        const title = document.createElement("p");
        title.className = "detail-description-title";
        const titleStrong = document.createElement("strong");
        titleStrong.textContent = "설명:";
        title.appendChild(titleStrong);
        container.appendChild(title);
        [blocks.cause, blocks.impact, stripDetailEvidence(blocks.action)].forEach((line) => {
            const paragraph = document.createElement("p");
            paragraph.className = "detail-description-line";
            paragraph.textContent = line;
            container.appendChild(paragraph);
        });
    }

    function localizeCtrlppSeverity(severity) {
        const sev = String(severity || "").toLowerCase();
        if (sev === "error") return "오류";
        if (sev === "information" || sev === "info") return "정보";
        if (sev === "performance") return "성능";
        if (sev === "warning") return "경고";
        if (sev === "style") return "스타일";
        if (sev === "portability") return "이식성";
        return severity || "정보";
    }

    return {
        appendDetailFact,
        appendDetailNote,
        buildP1DetailBlocks,
        buildP2DetailBlocks,
        buildP2LocalizedMessage,
        localizeCtrlppSeverity,
        renderDetailDescriptionBlocks,
        renderInspectorSelectionMeta,
    };
}
