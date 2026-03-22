import { createDetailPanelController } from "./detail-panel.js";

describe("detail panel controller", () => {
    test("buildViolationEvidenceRows exposes backend evidence fields", () => {
        const controller = createDetailPanelController({
            dom: {},
            state: {},
            helpers: {
                severityFilterKey: () => "warning",
            },
        });
        const rows = controller.buildViolationEvidenceRows({
            rule_id: "EXC-DP-01",
            line: 14,
            canonical_file_id: "sample.ctl",
            evidence: {
                matched_text: 'dpSet("A.B.C", 1);',
                matched_lines: [14],
                detector_kind: "heuristic",
                canonical_file_id: "sample.ctl",
                display_reason: "P1 detector matched EXC-DP-01 near line 14.",
            },
        });
        expect(rows).toEqual([
            { label: "Detector", value: "heuristic" },
            { label: "Matched lines", value: "14" },
            { label: "Matched text", value: 'dpSet("A.B.C", 1);' },
            { label: "Reason", value: "P1 detector matched EXC-DP-01 near line 14." },
            { label: "Canonical file", value: "sample.ctl" },
        ]);
    });
});
