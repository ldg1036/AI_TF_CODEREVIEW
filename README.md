# WinCC OA Code Inspector

> Structure note (2026-02-26)
> - Canonical project paths are root directories: `Config`, `CodeReview_Data`, `docs`.
> - `workspace/` is reserved for runtime/support grouping (for example `workspace/runtime/CodeReview_Report`).
> - Legacy tool commands under `tools/*.py` / `tools/*.js` still work via compatibility wrappers.
> - See `workspace/README.md` and `tools/README.md` for details.
> - Official review quality verification is based on `P1 (rules) + P2 (CtrlppCheck) + P3 (AI)` plus regression tests.
> - GoldenTime workbook/reference Excel comparison is no longer an official quality criterion.

> WinCC OA 肄붾뱶 由щ럭/?뺤쟻 遺꾩꽍/AI 蹂댁“ 由щ럭/?뱀씤???먮룞?섏젙???꾪븳 濡쒖뺄 ?ㅽ뻾???덉쭏 ?먭? ?꾧뎄

## 媛쒖슂

`WinCC OA Code Inspector`??WinCC OA ?꾨줈?앺듃??肄붾뱶 由щ럭瑜??먮룞??諛섏옄?숉솕?섍린 ?꾪븳 ?꾧뎄?낅땲??

?ㅼ쓬 ?낅젰????곸쑝濡?遺꾩꽍?????덉뒿?덈떎.
- `.ctl` (Server 肄붾뱶)
- `.pnl`, `.xml`?먯꽌 蹂?섎맂 ?띿뒪??(`*_pnl.txt`, `*_xml.txt`)
- ?꾩슂 ??raw `.txt` (?듭뀡 ?덉슜 ??

遺꾩꽍 寃곌낵???ㅼ쓬 ?뺥깭濡??뺤씤?????덉뒿?덈떎.
- UI (濡쒖뺄 ???명꽣?섏씠??
- HTML 由ы룷??- Excel 泥댄겕由ъ뒪??由ы룷??- Annotated TXT (`*_REVIEWED.txt`)

?먰븳 ?꾩옱 踰꾩쟾? ?뱀씤??diff review) 湲곕컲??source autofix(`.ctl` ?꾩슜)瑜?吏?먰빀?덈떎.

## 二쇱슂 湲곕뒫

### 1) 肄붾뱶 遺꾩꽍 (P1 / P2 / P3)
- `P1`: ?대━?ㅽ떛/?뺤쟻 洹쒖튃 湲곕컲 肄붾뱶 遺꾩꽍
- `P2`: `CtrlppCheck` ?곕룞 寃곌낵
- `P3`: LLM 湲곕컲 AI 由щ럭 (?좏깮)

### 2) ?깅뒫/?댁쁺 理쒖쟻??- `/api/analyze` `metrics` ?묐떟 (?④퀎蹂?timing, ?몄텧 ?? cache hit/miss)
- ?뚯씪 ?⑥쐞 bounded parallel 遺꾩꽍
- `.pnl/.xml -> *_txt` 蹂??罹먯떆 (`mtime + size`)
- Excel 吏???앹꽦(`defer_excel_reports`) + flush API
- ?꾨줎??寃곌낵 ?뚯씠釉?肄붾뱶酉?virtualization

### 3) ?뱀씤???먮룞?섏젙 (CTL only)
- `autofix/prepare` ??`file-diff` ?뺤씤 ??`autofix/apply`
- `.ctl`留??곸슜 ?덉슜
- `llm` / `rule` / `auto(rule-first, llm-fallback)` generator
- hash / anchor / syntax / heuristic / optional Ctrlpp ?뚭?寃??- 諛깆뾽 ?뚯씪 + 媛먯궗 濡쒓렇 + ?먯옄???곌린

### 4) ?덉쭏 寃뚯씠??/ 踰ㅼ튂留덊겕
- Playwright UI 踰ㅼ튂 (`tools/playwright_ui_benchmark.js`)
- `/api/analyze` HTTP baseline 留ㅽ듃由?뒪 (`tools/http_perf_baseline.py`)
- Ctrlpp ?듯빀 ?ㅻえ??(`tools/run_ctrlpp_integration_smoke.py`)

## Release Verification (P1/P2/P3)

Use regression tests and fail-soft optional smokes as the release baseline.
GoldenTime reference workbook comparison and `goldentime_compare_result.json` are not part of the official quality criteria.

Required:

1. `python -m unittest backend.tests.test_api_and_reports -v`
2. `python -m unittest backend.tests.test_todo_rule_mining -v`
3. `python -m unittest backend.tests.test_winccoa_context_server -v`
4. `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`

Optional (change-dependent):

1. Ctrlpp integration: `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
2. Frontend/perf: `node --check frontend/renderer.js`, `node tools/playwright_ui_benchmark.js --help`
3. Rules/config: `python backend/tools/check_config_rule_alignment.py --json`, `python backend/tools/analyze_template_coverage.py`

## ?꾩옱 援ы쁽 ?곹깭 (?붿빟)

?꾩옱 肄붾뱶踰좎씠??湲곗??쇰줈 ?ㅼ쓬??援ы쁽?섏뼱 ?덉뒿?덈떎.
- [x] ?깅뒫 怨꾩륫 (`metrics`)
- [x] 蹂??罹먯떆 + 蹂묐젹 遺꾩꽍 + 寃쎈줈蹂??숈떆???쒗븳
- [x] ?몄뀡 TTL/LRU + per-session/per-file lock
- [x] Diff ?뱀씤??source autofix (`.ctl`)
- [x] hybrid prepare (`llm` / `rule` / `auto`)
- [x] autofix ?덉쭏 硫뷀듃由?/ ?ㅽ뙣 肄붾뱶 / stats API
- [x] Excel 吏???앹꽦 + flush API
- [x] UI virtualization + Playwright 踰ㅼ튂 baseline
- [x] Ctrlpp ?ㅼ젣 諛붿씠?덈━ ?듯빀 ?ㅻえ??- [x] UTF-8 怨좎젙 ?몄퐫???뺤콉 + `.editorconfig`

## ?꾨줈?앺듃 援ъ“

```text
AI_TF_CodeReview/
?쒋? backend/
?? ?쒋? main.py                      # CodeInspectorApp (analysis/session/autofix orchestration)
?? ?쒋? server.py                    # HTTP API + static UI server
?? ?쒋? core/
?? ?? ?쒋? analysis_pipeline.py      # analysis orchestration pipeline
?? ?? ?쒋? reporter.py               # HTML/Excel/Annotated TXT reports
?? ?? ?쒋? llm_reviewer.py           # LLM review generation
?? ?? ?쒋? ctrl_wrapper.py           # CtrlppCheck integration
?? ?? ?붴? ...
?? ?붴? tests/
?쒋? frontend/
?? ?쒋? index.html
?? ?쒋? renderer.js
?? ?붴? style.css
?쒋? tools/
?? ?쒋? perf/                        # actual perf tool implementations
?? ?? ?쒋? playwright_ui_benchmark.js
?? ?? ?붴? http_perf_baseline.py
?? ?쒋? ctrlpp/                      # actual Ctrlpp helper implementations
?? ?? ?쒋? run_ctrlpp_integration_smoke.py
?? ?? ?쒋? ctrlppcheck_updater.py
?? ?? ?쒋? ctrlppcheck_wrapper.py
?? ?? ?붴? README_CtrlppCheck.md
?? ?쒋? CtrlppCheck/                 # runtime install/cache path (legacy path kept)
?? ?쒋? benchmark_results/           # benchmark outputs (legacy path kept)
?? ?쒋? integration_results/         # integration smoke outputs (legacy path kept)
?? ?쒋? README.md                    # tools layout guide
?? ?쒋? playwright_ui_benchmark.js   # compatibility wrapper (legacy command path)
?? ?쒋? http_perf_baseline.py        # compatibility wrapper (legacy command path)
?? ?쒋? run_ctrlpp_integration_smoke.py
?? ?쒋? ctrlppcheck_updater.py
?? ?쒋? ctrlppcheck_wrapper.py
?? ?붴? README_CtrlppCheck.md        # compatibility pointer doc
?쒋? workspace/                      # runtime/support area
?? ?쒋? resources/
?? ?? ?붴? README.md                 # note: canonical config/data paths are at root
?? ?쒋? runtime/
?? ?? ?붴? CodeReview_Report/        # runtime generated reports (gitignored)
?? ?쒋? documentation/
?? ?? ?붴? README.md                 # note: canonical docs path is root
?? ?붴? README.md
?쒋? docs/                           # canonical docs path
?쒋? Config/                         # canonical config path
?쒋? CodeReview_Data/                # canonical review input data path
?쒋? CodeReview_Report/              # report output path (gitignored)
?쒋? README.md
?붴? todo.md
```

## 鍮좊Ⅸ ?쒖옉 (Quick Start)

### ?붽뎄?ы빆
- Python 3.x
- (?좏깮) Ollama / 濡쒖뺄 LLM
- (?좏깮) CtrlppCheck ?ㅽ뻾 ?뚯씪
- (?좏깮) Node.js (UI 踰ㅼ튂/Playwright ?ㅽ뻾 ??

### 1) UI ?쒕쾭 ?ㅽ뻾

```powershell
python backend/server.py
```

釉뚮씪?곗? ?묒냽:
- `http://127.0.0.1:8765`

### 2) CLI 遺꾩꽍 ?ㅽ뻾

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

Note: `GoldenTime.ctl` is shown only as an example input filename.

異붽? ?덉떆:

```powershell
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
python backend/main.py --selected-files raw_input.txt --allow-raw-txt
python backend/main.py --selected-files GoldenTime.ctl --enable-live-ai
```

## API 媛쒖슂

### ?뚯씪 議고쉶
- `GET /api/files`
- raw `.txt` ?ы븿 議고쉶: `GET /api/files?allow_raw_txt=true`

### 遺꾩꽍 ?ㅽ뻾
- `POST /api/analyze`

二쇱슂 ?붿껌 ?꾨뱶:
- `selected_files`
- `allow_raw_txt`
- `enable_ctrlppcheck`
- `enable_live_ai`
- `ai_with_context`
- `defer_excel_reports`

二쇱슂 ?묐떟 ?꾨뱶:
- `summary`
- `violations` (`P1`, `P2`, `P3`)
- `output_dir`
- `metrics`
- `report_jobs`

### ?뚯씪 ?댁슜 議고쉶
- `GET /api/file-content`
- `prefer_source=true` 吏??(source patch ?곸슜 ???뚯뒪 ?곗꽑 ?쒖떆)

### AI 由щ럭 諛섏쁺 (`REVIEWED.txt`)
- `POST /api/ai-review/apply`

### Diff ?뱀씤??Autofix (CTL only)
- `POST /api/autofix/prepare`
- `GET /api/autofix/file-diff`
- `POST /api/autofix/apply`
- `GET /api/autofix/stats`

#### `autofix/prepare` ?덉떆

```json
{
  "file": "GoldenTime.ctl",
  "object": "GoldenTime.ctl",
  "event": "Global",
  "review": "?붿빟: ...

肄붾뱶:
```cpp
...
```",
  "session_id": "<output_dir from /api/analyze>",
  "generator_preference": "auto",
  "allow_fallback": true
}
```

Note: The sample uses `GoldenTime.ctl` only as an example target file, not as a quality gate baseline.

?묐떟 ?뺤옣 ?꾨뱶(?섏쐞?명솚):
- `generator_type` (`llm` | `rule`)
- `generator_reason`
- `quality_preview`
- `llm_meta` (LLM 寃쎈줈????

#### `autofix/apply` ?덉떆

```json
{
  "proposal_id": "<proposal_id>",
  "session_id": "<output_dir from /api/analyze>",
  "file": "GoldenTime.ctl",
  "expected_base_hash": "<base_hash>",
  "apply_mode": "source_ctl",
  "block_on_regression": true,
  "check_ctrlpp_regression": false
}
```

?묐떟 ?뺤옣 ?꾨뱶(?섏쐞?명솚):
- ?깃났: `quality_metrics`, `validation`, `reanalysis_summary`
- ?ㅽ뙣: `error_code`, `quality_metrics` (寃利?寃곌낵媛 ?덈뒗 寃쎌슦)

## ?깅뒫 湲곗???/ ?덉쭏 寃뚯씠??
### UI ?깅뒫 踰ㅼ튂 (Playwright)

?ㅼ튂:

```powershell
npm i -D playwright
npx playwright install chromium
```

?ㅽ뻾:

```powershell
node tools/playwright_ui_benchmark.js --iterations 5 --files 20 --violations-per-file 120 --code-lines 6000
```

?꾧퀎移?泥댄겕 ?덉떆:

```powershell
node tools/playwright_ui_benchmark.js --max-analyze-ms 180 --max-table-scroll-ms 1050 --max-code-jump-ms 100 --max-code-scroll-ms 500
```

愿???뚯씪:
- `docs/perf_baselines/ui_benchmark_baseline_20260225_1119.json`
- `docs/perf_baselines/ui_thresholds_20260225.json`

### HTTP baseline (`/api/analyze`)

```powershell
python backend/server.py
python tools/http_perf_baseline.py --dataset-name local_code_review_data --discover-count 1 --live-ai off --ctrlpp off,on --defer-excel off,on --iterations 2 --flush-excel
```

?앹꽦 ?덉떆:
- `docs/perf_baselines/http_perf_baseline_local_code_review_data_20260225_111410.json`

## CtrlppCheck ?곕룞 / ?댁쁺 ?꾧뎄

### 硫붿씤 ?꾨줈洹몃옩 ?곕룞
- 硫붿씤 ?꾨줈洹몃옩? `backend/core/ctrl_wrapper.py`瑜??듯빐 CtrlppCheck瑜??ъ슜?⑸땲??
- `Config/config.json`??`ctrlppcheck` ?뱀뀡?쇰줈 ?숈옉???쒖뼱?⑸땲??

### ?⑤룆 ?먭?/?낅뜲?댄듃 ?꾧뎄
- `tools/README_CtrlppCheck.md` 李멸퀬
- ?듯빀 ?ㅻえ??

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

## ?ㅼ젙 (`Config/config.json`)

二쇱슂 ?뱀뀡:
- `ai`
  - provider/model/timeout/snippet window/batch groups
- `ctrlppcheck`
  - binary path/auto install/version/rule files
- `performance`
  - worker limits, deferred Excel default
- `autofix`
  - session TTL/LRU, proposal limit, regression policy
  - `prepare_generator_default`, `allow_fallback_default`

## ?뚯뒪??/ 寃利?
?듭떖 ?뚭? ?뚯뒪??

```powershell
python -m unittest backend.tests.test_api_and_reports
```

?꾩껜 ?듭떖 ?뚯뒪??臾띠쓬:

```powershell
python -m unittest backend.system_verification backend.tests.test_api_and_reports backend.tests.test_todo_rule_mining backend.tests.test_winccoa_context_server
```

臾몃쾿/?뺤쟻 ?뺤씤 ?덉떆:

```powershell
python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py
node --check frontend/renderer.js
```

## 臾몄꽌

### ?쒗뭹/?ㅺ퀎 臾몄꽌
- `docs/WinCC OA Code Inspector ??Design Guide.md`
- `docs/WinCC OA Code Inspector ??Information Architecture.md`
- `docs/WinCC OA Code Inspector ??Product Requir.md`
- `docs/WinCC OA Code Inspector ??Use-case.md`

### ?댁쁺/?덉쭏 臾몄꽌
- `docs/performance.md`
- `docs/autofix_safety.md`
- `docs/encoding_policy.md`
- `docs/perf_baselines/README.md`

### 援ы쁽/吏꾪뻾 ?꾪솴
- `todo.md`

## ?몄퐫???뺤콉 (以묒슂)

- ?띿뒪???뚯뒪/臾몄꽌??UTF-8 怨좎젙
- `.editorconfig` 湲곗? 以??- ?몄퐫???댁긽 諛쒖깮 ??諛깆뾽 ??遺遺?蹂듦뎄 + diff 寃??
## 李멸퀬

- CtrlppCheck Releases: https://github.com/siemens/CtrlppCheck/releases
- (?대? ?댁쁺) ?먮룞?섏젙 怨좊룄???꾩냽 怨꾪쉷? `todo.md`??`8) ?꾩냽 怨좊룄??怨꾪쉷` ?뱀뀡 李멸퀬
