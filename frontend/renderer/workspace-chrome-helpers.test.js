import {
    buildWorkspaceCommandSummary,
    buildWorkspaceSelectionSummary,
    deriveInspectorActionState,
    deriveWorkspaceCommandButtonState,
} from "./workspace-chrome-helpers.js";

describe("workspace chrome helpers", () => {
    test("buildWorkspaceCommandSummary reports selected and visible counts", () => {
        expect(buildWorkspaceCommandSummary({
            selectedCount: 2,
            visibleCount: 6,
            totalCount: 10,
            hiddenSuppressedCount: 1,
            activeFilterText: "빠른 보기: P1만",
        })).toBe("선택 파일 2개 | 현재 표시 6개 | 전체 검토 대상 10개 | 숨김 처리 1개 | 빠른 보기: P1만");
    });

    test("buildWorkspaceSelectionSummary returns a readable active selection", () => {
        expect(buildWorkspaceSelectionSummary({ source: "p2", object: "MainPanel", line: 18 }))
            .toBe("P2 | MainPanel | 줄 18");
        expect(buildWorkspaceSelectionSummary(null)).toBe("활성 이슈 없음");
    });

    test("deriveWorkspaceCommandButtonState disables actions without rows or selection", () => {
        expect(deriveWorkspaceCommandButtonState({
            hasRows: false,
            hasActiveSelection: false,
            hasAiAvailable: false,
            hasQuickFilter: false,
            hasCustomFilter: false,
        })).toEqual({
            prevDisabled: true,
            nextDisabled: true,
            jumpDisabled: true,
            detailDisabled: true,
            aiDisabled: true,
            resetDisabled: true,
            prevTitle: "이동할 이슈가 없습니다.",
            nextTitle: "이동할 이슈가 없습니다.",
            jumpTitle: "선택된 이슈가 없어 코드를 열 수 없습니다.",
            detailTitle: "선택된 이슈가 없어 상세를 열 수 없습니다.",
            aiTitle: "선택된 이슈가 없어 AI 탭을 열 수 없습니다.",
            resetTitle: "초기화할 보기 조건이 없습니다.",
        });
    });

    test("deriveWorkspaceCommandButtonState enables reset when any filter is active", () => {
        expect(deriveWorkspaceCommandButtonState({
            hasRows: true,
            hasActiveSelection: true,
            hasAiAvailable: true,
            hasQuickFilter: true,
            hasCustomFilter: false,
        }).resetDisabled).toBe(false);
    });

    test("deriveInspectorActionState respects active tab and compare availability", () => {
        expect(deriveInspectorActionState({
            hasActiveSelection: true,
            aiEnabled: true,
            compareEnabled: true,
            activeInspectorTab: "ai",
        })).toEqual({
            jumpDisabled: false,
            detailDisabled: false,
            detailPressed: false,
            aiDisabled: false,
            aiPressed: true,
            compareDisabled: false,
            jumpTitle: "현재 이슈 위치의 코드를 엽니다.",
            detailTitle: "상세 패널을 표시합니다.",
            aiTitle: "AI 제안 패널을 표시합니다.",
            compareTitle: "현재 선택 항목의 비교 보기를 엽니다.",
        });
    });

    test("deriveInspectorActionState falls back to detail when ai is unavailable", () => {
        expect(deriveInspectorActionState({
            hasActiveSelection: true,
            aiEnabled: false,
            compareEnabled: false,
            activeInspectorTab: "ai",
        })).toEqual({
            jumpDisabled: false,
            detailDisabled: false,
            detailPressed: true,
            aiDisabled: true,
            aiPressed: false,
            compareDisabled: true,
            jumpTitle: "현재 이슈 위치의 코드를 엽니다.",
            detailTitle: "상세 패널을 표시합니다.",
            aiTitle: "현재 이슈에는 AI 제안을 사용할 수 없습니다.",
            compareTitle: "현재 선택 항목에는 비교 가능한 제안이 없습니다.",
        });
    });
});
