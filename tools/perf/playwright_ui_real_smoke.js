#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

function printHelp() {
  console.log(`Playwright real-server UI smoke for WinCC OA code review frontend.

Usage:
  node tools/playwright_ui_real_smoke.js [options]

Options:
  --host <host>              Backend host (default: 127.0.0.1)
  --port <port>              Backend port (default: 8765)
  --python <cmd>             Python executable when starting backend locally (default: python)
  --timeout-ms <n>           End-to-end timeout per major wait (default: 120000)
  --target-file <name>       Prefer this file when selecting a focused smoke target
  --output <path>            JSON result path (default: tools/integration_results/ui_real_smoke_<ts>.json)
  --with-live-ai-compare-prepare
                              Extend smoke to Generate -> Compare -> Prepare patch
  --headed                   Run browser in headed mode
  --no-sandbox               Chromium --no-sandbox launch arg
  --help                     Show this help
`);
}

function timestampCompact() {
  return new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
}

function parseArgs(argv) {
  const opts = {
    host: "127.0.0.1",
    port: 8765,
    python: "python",
    timeoutMs: 120000,
    targetFile: "BenchmarkP1Fixture.ctl",
    output: "",
    withLiveAiComparePrepare: false,
    headed: false,
    noSandbox: false,
    help: false,
  };

  const nextValue = (i, name) => {
    if (i + 1 >= argv.length) throw new Error(`Missing value for ${name}`);
    return argv[i + 1];
  };
  const asInt = (value, name) => {
    const n = Number.parseInt(String(value), 10);
    if (!Number.isFinite(n)) throw new Error(`Invalid integer for ${name}: ${value}`);
    return n;
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case "--help":
      case "-h":
        opts.help = true;
        break;
      case "--host":
        opts.host = String(nextValue(i, arg));
        i += 1;
        break;
      case "--port":
        opts.port = asInt(nextValue(i, arg), arg);
        i += 1;
        break;
      case "--python":
        opts.python = String(nextValue(i, arg));
        i += 1;
        break;
      case "--timeout-ms":
        opts.timeoutMs = Math.max(1000, asInt(nextValue(i, arg), arg));
        i += 1;
        break;
      case "--target-file":
        opts.targetFile = String(nextValue(i, arg));
        i += 1;
        break;
      case "--output":
        opts.output = String(nextValue(i, arg));
        i += 1;
        break;
      case "--with-live-ai-compare-prepare":
        opts.withLiveAiComparePrepare = true;
        break;
      case "--headed":
        opts.headed = true;
        break;
      case "--no-sandbox":
        opts.noSandbox = true;
        break;
      default:
        throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!opts.output) {
    opts.output = path.join("tools", "integration_results", `ui_real_smoke_${timestampCompact()}.json`);
  }
  return opts;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeJsonReport(outputPath, payload) {
  // Prepend UTF-8 BOM so Windows-hosted tooling like PowerShell Get-Content
  // shows Korean UI labels without mojibake.
  const body = `\uFEFF${JSON.stringify(payload, null, 2)}`;
  fs.writeFileSync(outputPath, body, "utf-8");
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const body = Buffer.concat(chunks).toString("utf-8");
        resolve({
          status: res.statusCode || 0,
          body,
          json: (() => {
            try {
              return JSON.parse(body);
            } catch (_err) {
              return null;
            }
          })(),
        });
      });
    });
    req.on("error", reject);
    req.setTimeout(3000, () => req.destroy(new Error("HTTP GET timeout")));
  });
}

function httpGetJson(url) {
  return httpGet(url);
}

function httpPostJson(url, payload) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const body = Buffer.from(JSON.stringify(payload || {}), "utf-8");
    const req = http.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port,
        path: `${target.pathname}${target.search}`,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": String(body.length),
        },
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf-8");
          resolve({
            status: res.statusCode || 0,
            body: text,
            json: (() => {
              try {
                return JSON.parse(text);
              } catch (_err) {
                return null;
              }
            })(),
          });
        });
      },
    );
    req.on("error", reject);
    req.setTimeout(5000, () => req.destroy(new Error("HTTP POST timeout")));
    req.write(body);
    req.end();
  });
}

async function resetP1TriageEntries(baseUrl) {
  const result = {
    ok: true,
    deleted_count: 0,
    initial_count: 0,
    errors: [],
  };
  try {
    const listed = await httpGetJson(`${baseUrl}/api/triage/p1`);
    const entries = Array.isArray(listed.json && listed.json.entries) ? listed.json.entries : [];
    result.initial_count = entries.length;
    for (const entry of entries) {
      const triageKey = String((entry && entry.triage_key) || "").trim();
      if (!triageKey) continue;
      const deleted = await httpPostJson(`${baseUrl}/api/triage/p1/delete`, { triage_key: triageKey });
      if (deleted.status !== 200) {
        result.ok = false;
        result.errors.push(`delete failed for ${triageKey}: ${deleted.status}`);
        continue;
      }
      result.deleted_count += 1;
    }
  } catch (err) {
    result.ok = false;
    result.errors.push(String((err && err.message) || err || "triage reset failed"));
  }
  return result;
}

async function waitForServer(baseUrl, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const files = await httpGetJson(`${baseUrl}/api/files`);
      if (files.status === 200 && files.json && Array.isArray(files.json.files)) {
        return files.json.files;
      }
    } catch (_err) {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Backend server did not become ready within ${timeoutMs}ms`);
}

function startBackendServer({ projectRoot, host, port, python }) {
  const args = ["backend/server.py", "--host", String(host), "--port", String(port)];
  const child = spawn(python, args, {
    cwd: projectRoot,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.on("data", () => {});
  child.stderr.on("data", () => {});
  return child;
}

function stopProcess(child) {
  if (!child || child.killed) return;
  try {
    child.kill();
  } catch (_err) {
    // ignore
  }
}

async function ensureBackend({ projectRoot, baseUrl, host, port, python, timeoutMs }) {
  try {
    const files = await waitForServer(baseUrl, 2500);
    return { child: null, startedServer: false, files };
  } catch (_err) {
    const child = startBackendServer({ projectRoot, host, port, python });
    const files = await waitForServer(baseUrl, timeoutMs);
    return { child, startedServer: true, files };
  }
}

async function probeStartupAssets(baseUrl) {
  const targets = {
    root: `${baseUrl}/`,
    style: `${baseUrl}/style.css`,
    renderer: `${baseUrl}/renderer.js`,
  };
  const statuses = {};
  const errors = {};

  for (const [key, url] of Object.entries(targets)) {
    try {
      const response = await httpGet(url);
      statuses[key] = Number(response.status || 0);
    } catch (err) {
      statuses[key] = 0;
      errors[key] = String((err && err.message) || err || "request failed");
    }
  }

  return {
    root_ok: statuses.root === 200,
    style_ok: statuses.style === 200,
    renderer_ok: statuses.renderer === 200,
    ok: statuses.root === 200 && statuses.style === 200 && statuses.renderer === 200,
    status_codes: statuses,
    errors,
  };
}

function pickTargetFile(files, preferredName) {
  if (!Array.isArray(files) || !files.length) {
    throw new Error("No selectable files returned by backend");
  }
  const selectable = files.filter((file) => file && file.selectable !== false && typeof file.name === "string");
  if (!selectable.length) {
    throw new Error("No selectable files available for UI smoke");
  }
  const exact = selectable.find((file) => file.name === preferredName);
  if (exact) return exact.name;
  const ctl = selectable.find((file) => /\.ctl$/i.test(file.name));
  if (ctl) return ctl.name;
  return selectable[0].name;
}

async function readExcelUiState(page) {
  return page.evaluate(() => {
    const button = document.getElementById("btn-flush-excel");
    const statusNode = document.getElementById("excel-job-status");
    const downloadButtons = Array.from(
      document.querySelectorAll("#excel-download-list .excel-download-button"),
    );
    return {
      present: !!button,
      disabled: !!(button && button.disabled),
      button_text: String((button && button.textContent) || "").trim(),
      status_text: String((statusNode && statusNode.textContent) || "").trim(),
      download_button_count: downloadButtons.length,
      download_labels: downloadButtons.map((node) => String(node.textContent || "").trim()),
    };
  });
}

async function readSmokeUiState(page) {
  return page.evaluate(() => {
    const textOf = (id) => String((document.getElementById(id)?.textContent) || "").trim();
    const resultRows = Array.from(document.querySelectorAll("#result-body tr.result-item-row"));
    const unknownRuleRowCount = resultRows.filter((row) => /\bUNKNOWN\b/i.test(String(row.innerText || ""))).length;
    const selectedFiles = Array.from(document.querySelectorAll("#file-list input[data-file]:checked"))
      .map((node) => String(node.getAttribute("data-file") || ""));
    const diagnostics = (window.__rendererDiagnostics && typeof window.__rendererDiagnostics === "object")
      ? window.__rendererDiagnostics
      : {};
    const reviewTargetCount = Number.parseInt(
      String(diagnostics.workspace_filtered_row_count || textOf("current-review-issues") || "0"),
      10,
    ) || 0;
    return {
      file_list_dom_count: document.querySelectorAll("#file-list input[data-file]").length,
      file_list_selected_count: selectedFiles.length,
      file_list_selected_files: selectedFiles,
      result_row_count: resultRows.length,
      unknown_rule_row_count: unknownRuleRowCount,
      review_target_count: reviewTargetCount,
      result_empty_text: String(document.querySelector("#result-body .result-empty-state")?.textContent || "").trim(),
      total_issues: textOf("total-issues"),
      current_review_issues: textOf("current-review-issues"),
      critical_issues: textOf("critical-issues"),
      warning_issues: textOf("warning-issues"),
      workspace_visible: !!document.getElementById("workspace-view")
        && getComputedStyle(document.getElementById("workspace-view")).display !== "none",
      progress_panel_visible: !!document.getElementById("analyze-progress-panel")
        && getComputedStyle(document.getElementById("analyze-progress-panel")).display !== "none",
      progress_status_text: textOf("analyze-progress-status"),
      progress_meta_text: textOf("analyze-progress-meta"),
      last_renderer_error: String(window.__lastRendererError || ""),
      renderer_diagnostics: diagnostics,
    };
  });
}

function effectiveReviewCount(snapshot = {}) {
  const filteredCount = Number(snapshot.review_target_count || 0);
  if (filteredCount > 0) return filteredCount;
  return Number(snapshot.result_row_count || 0);
}

async function readTriageUiState(page) {
  return page.evaluate(() => {
    const section = document.querySelector("[data-triage-role='section']");
    const statusNode = document.querySelector("[data-triage-role='status']");
    const feedbackNode = document.querySelector("[data-triage-role='feedback']");
    const activeRow = document.querySelector("#result-body tr.result-item-row.result-item-row-active");
    const suppressedRows = Array.from(document.querySelectorAll("#result-body tr.result-item-row.result-item-row-suppressed"));
    return {
      section_present: !!section,
      status_text: String((statusNode && statusNode.textContent) || "").trim(),
      feedback_text: String((feedbackNode && feedbackNode.textContent) || "").trim(),
      reason_value: String((document.querySelector("[data-triage-role='reason']")?.value) || "").trim(),
      note_value: String((document.querySelector("[data-triage-role='note']")?.value) || "").trim(),
      suppress_button_present: !!document.querySelector("[data-triage-role='suppress']"),
      unsuppress_button_present: !!document.querySelector("[data-triage-role='unsuppress']"),
      active_row_id: String((activeRow && activeRow.getAttribute("data-row-id")) || "").trim(),
      suppressed_row_count: suppressedRows.length,
      suppressed_row_ids: suppressedRows.map((row) => String(row.getAttribute("data-row-id") || "").trim()),
      show_suppressed_checked: !!document.getElementById("workspace-command-show-suppressed")?.checked,
    };
  });
}

async function setShowSuppressedToggle(page, checked) {
  return page.evaluate((nextChecked) => {
    const checkbox = document.getElementById("workspace-command-show-suppressed");
    if (!checkbox) {
      return { ok: false, reason: "toggle not found" };
    }
    checkbox.checked = !!nextChecked;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, checked: !!checkbox.checked };
  }, !!checked);
}

async function selectWorkspaceRow(page, { timeoutMs, source = "", suppressedOnly = false, rowId = "", containsText = "" } = {}) {
  const selected = await page.evaluate(({ preferredSource, requireSuppressed, preferredRowId, preferredText }) => {
    const safeSource = String(preferredSource || "").trim().toUpperCase();
    const safeRowId = String(preferredRowId || "").trim();
    const safeText = String(preferredText || "").trim().toUpperCase();
    const rows = Array.from(document.querySelectorAll("#result-body tr.result-item-row"));
    const match = rows.find((row) => {
      if (safeRowId && String(row.getAttribute("data-row-id") || "").trim() !== safeRowId) return false;
      if (requireSuppressed && !row.classList.contains("result-item-row-suppressed")) return false;
      if (safeText && !String(row.innerText || "").trim().toUpperCase().includes(safeText)) return false;
      if (!safeSource) return true;
      const badge = row.querySelector(".result-cell-source .badge");
      const badgeText = String((badge && badge.textContent) || "").trim().toUpperCase();
      return badgeText === safeSource;
    });
    if (!match) {
      return { ok: false, rowId: "", source: safeSource };
    }
    match.click();
    return {
      ok: true,
      rowId: String(match.getAttribute("data-row-id") || "").trim(),
      source: safeSource,
      suppressed: match.classList.contains("result-item-row-suppressed"),
    };
  }, { preferredSource: source, requireSuppressed: suppressedOnly, preferredRowId: rowId, preferredText: containsText });
  if (!selected.ok) {
    return selected;
  }
  await page.waitForFunction(
    (rowId) => {
      const active = document.querySelector("#result-body tr.result-item-row.result-item-row-active");
      return !!active && String(active.getAttribute("data-row-id") || "").trim() === String(rowId || "").trim();
    },
    selected.rowId,
    { timeout: timeoutMs },
  );
  return selected;
}

async function runP1TriageSmoke(page, { timeoutMs }) {
  const before = await readSmokeUiState(page);
  const baselineCount = effectiveReviewCount(before);
  const selectedP1 = await selectWorkspaceRow(page, { timeoutMs, source: "P1" });
  if (!selectedP1.ok) {
    return {
      attempted: false,
      completed: false,
      skipped_reason: "no visible P1 row available",
      baseline_row_count: baselineCount,
      before,
      after_suppress: null,
      after_show_suppressed: null,
      after_unsuppress: null,
      selected_row_id: "",
      suppressed_row_id: "",
    };
  }

  await page.click("#inspector-tab-detail", { timeout: Math.min(timeoutMs, 15000) });
  await page.waitForSelector("[data-triage-role='section']", { timeout: Math.min(timeoutMs, 15000) });

  await page.locator("[data-triage-role='reason']").fill("already reviewed in smoke");
  await page.locator("[data-triage-role='note']").fill("triage smoke round trip");
  await page.click("[data-triage-role='suppress']", { timeout: Math.min(timeoutMs, 15000) });

  const expectedSuppressedCount = Math.max(0, baselineCount - 1);
  await page.waitForFunction(
    ({ nextCount }) => {
      const diagnostics = (window.__rendererDiagnostics && typeof window.__rendererDiagnostics === "object")
        ? window.__rendererDiagnostics
        : {};
      const rowCount = Number((diagnostics.workspace_filtered_row_count) || 0);
      const triageCount = Number((window.__rendererDiagnostics && window.__rendererDiagnostics.p1_triage_count) || 0);
      return rowCount === nextCount && triageCount >= 1;
    },
    { nextCount: expectedSuppressedCount },
    { timeout: Math.min(timeoutMs, 30000) },
  );
  const afterSuppress = {
    ui: await readSmokeUiState(page),
    triage: await readTriageUiState(page),
  };

  const showToggle = await setShowSuppressedToggle(page, true);
  if (!showToggle.ok) {
    throw new Error(`Failed to enable Show suppressed: ${showToggle.reason || "unknown"}`);
  }
  await page.waitForFunction(
    ({ expectedCount, targetRowId }) => {
      const diagnostics = (window.__rendererDiagnostics && typeof window.__rendererDiagnostics === "object")
        ? window.__rendererDiagnostics
        : {};
      const rowCount = Number((diagnostics.workspace_filtered_row_count) || 0);
      const targetRow = document.querySelector(`#result-body tr.result-item-row[data-row-id="${CSS.escape(String(targetRowId || ""))}"]`);
      return rowCount === expectedCount && !!targetRow;
    },
    { expectedCount: baselineCount, targetRowId: selectedP1.rowId },
    { timeout: Math.min(timeoutMs, 30000) },
  );
  const afterShowSuppressed = {
    ui: await readSmokeUiState(page),
    triage: await readTriageUiState(page),
  };

  const selectedSuppressed = await selectWorkspaceRow(page, {
    timeoutMs,
    source: "P1",
    suppressedOnly: true,
    rowId: selectedP1.rowId,
  });
  if (!selectedSuppressed.ok) {
    throw new Error("Failed to re-select the suppressed P1 row");
  }
  await page.waitForFunction(
    () => {
      const statusNode = document.querySelector("[data-triage-role='status']");
      const unsuppress = document.querySelector("[data-triage-role='unsuppress']");
      return !!statusNode
        && /(suppressed|숨김)/i.test(String(statusNode.textContent || ""))
        && !!unsuppress;
    },
    { timeout: Math.min(timeoutMs, 15000) },
  );

  await page.click("[data-triage-role='unsuppress']", { timeout: Math.min(timeoutMs, 15000) });
  await page.waitForFunction(
    (expectedCount) => {
      const diagnostics = (window.__rendererDiagnostics && typeof window.__rendererDiagnostics === "object")
        ? window.__rendererDiagnostics
        : {};
      const rowCount = Number((diagnostics.workspace_filtered_row_count) || 0);
      const suppressedCount = document.querySelectorAll("#result-body tr.result-item-row.result-item-row-suppressed").length;
      const triageCount = Number((window.__rendererDiagnostics && window.__rendererDiagnostics.p1_triage_count) || 0);
      return rowCount === expectedCount && suppressedCount === 0 && triageCount === 0;
    },
    baselineCount,
    { timeout: Math.min(timeoutMs, 30000) },
  );
  const afterUnsuppress = {
    ui: await readSmokeUiState(page),
    triage: await readTriageUiState(page),
  };

  if (afterUnsuppress.triage.show_suppressed_checked) {
    const hideToggle = await setShowSuppressedToggle(page, false);
    if (!hideToggle.ok) {
      throw new Error(`Failed to disable Show suppressed: ${hideToggle.reason || "unknown"}`);
    }
    await page.waitForFunction(
      () => !document.getElementById("workspace-command-show-suppressed")?.checked,
      { timeout: Math.min(timeoutMs, 15000) },
    );
  }

  return {
    attempted: true,
    completed:
      effectiveReviewCount(afterSuppress.ui) === expectedSuppressedCount
      && effectiveReviewCount(afterShowSuppressed.ui) === baselineCount
      && effectiveReviewCount(afterUnsuppress.ui) === baselineCount
      && Number(afterShowSuppressed.triage.suppressed_row_count || 0) >= 1
      && Number(afterUnsuppress.triage.suppressed_row_count || 0) === 0,
    skipped_reason: "",
    baseline_row_count: baselineCount,
    before,
    after_suppress: afterSuppress,
    after_show_suppressed: afterShowSuppressed,
    after_unsuppress: afterUnsuppress,
    selected_row_id: selectedP1.rowId,
    suppressed_row_id: selectedSuppressed.rowId,
  };
}

function summarizeAnalyzeStatusPayload(payload) {
  const progress = payload && typeof payload.progress === "object" ? payload.progress : {};
  const result = payload && typeof payload.result === "object" ? payload.result : {};
  const summary = result && typeof result.summary === "object" ? result.summary : {};
  return {
    status: String((payload && payload.status) || ""),
    error: String((payload && payload.error) || ""),
    request_id: String((payload && payload.request_id) || ""),
    progress: {
      total_files: Number(progress.total_files || 0),
      completed_files: Number(progress.completed_files || 0),
      failed_files: Number(progress.failed_files || 0),
      percent: Number(progress.percent || 0),
      current_file: String(progress.current_file || ""),
      phase: String(progress.phase || ""),
    },
    result_summary: {
      total: Number(summary.total || 0),
      critical: Number(summary.critical || 0),
      warning: Number(summary.warning || 0),
      info: Number(summary.info || 0),
      score: Number(summary.score || 0),
    },
  };
}

async function waitForAnalyzeOutcome(page, { timeoutMs }) {
  const startedAt = Date.now();
  let sawProgress = false;
  while (Date.now() - startedAt < timeoutMs) {
    const snapshot = await readSmokeUiState(page);
    if (snapshot.progress_panel_visible) {
      sawProgress = true;
    }
    if (effectiveReviewCount(snapshot) > 0) {
      return { outcome: "rows_rendered", sawProgress, snapshot };
    }
    if (snapshot.last_renderer_error) {
      return { outcome: "renderer_error", sawProgress, snapshot };
    }
    if (sawProgress && !snapshot.progress_panel_visible) {
      return { outcome: "progress_finished_without_rows", sawProgress, snapshot };
    }
    await page.waitForTimeout(250);
  }
  return { outcome: "timeout", sawProgress, snapshot: await readSmokeUiState(page) };
}

async function runExcelSmoke(page, { timeoutMs }) {
  const initial = await readExcelUiState(page);
  if (!initial.present) {
    return {
      attempted: false,
      clicked: false,
      completed: false,
      skipped_reason: "excel controls not found",
      initial,
      final: initial,
      download_triggered: false,
      suggested_filename: "",
      download_error: "",
    };
  }

  if (initial.download_button_count > 0) {
    return {
      attempted: false,
      clicked: false,
      completed: true,
      skipped_reason: "excel files already available",
      initial,
      final: initial,
      download_triggered: false,
      suggested_filename: "",
      download_error: "",
    };
  }

  if (initial.disabled) {
    return {
      attempted: false,
      clicked: false,
      completed: false,
      skipped_reason: initial.status_text || "excel generate button disabled",
      initial,
      final: initial,
      download_triggered: false,
      suggested_filename: "",
      download_error: "",
    };
  }

  await page.click("#btn-flush-excel", { timeout: Math.min(timeoutMs, 15000) });

  try {
    await page.waitForFunction(
      () => {
        const count = document.querySelectorAll("#excel-download-list .excel-download-button").length;
        const statusText = String((document.getElementById("excel-job-status")?.textContent) || "");
        return count > 0 || statusText.includes("Excel 실패");
      },
      { timeout: timeoutMs },
    );
  } catch (_err) {
    // final state below captures timeout outcomes
  }

  const final = await readExcelUiState(page);
  let downloadTriggered = false;
  let suggestedFilename = "";
  let downloadError = "";

  if (final.download_button_count > 0) {
    try {
      const firstButton = page.locator("#excel-download-list .excel-download-button").first();
      const downloadPromise = page.waitForEvent("download", {
        timeout: Math.min(timeoutMs, 30000),
      });
      await firstButton.click();
      const download = await downloadPromise;
      suggestedFilename = String(download.suggestedFilename() || "");
      downloadTriggered = true;
    } catch (err) {
      downloadError = String((err && err.message) || err || "download failed");
    }
  }

  return {
    attempted: true,
    clicked: true,
    completed: final.download_button_count > 0,
    skipped_reason: "",
    initial,
    final,
    download_triggered: downloadTriggered,
    suggested_filename: suggestedFilename,
    download_error: downloadError,
  };
}

async function readAiComparePrepareState(page) {
  return page.evaluate(() => {
    const modal = document.getElementById("autofix-diff-modal");
    const meta = String((document.getElementById("autofix-diff-modal-meta")?.innerText) || "").trim();
    const summary = String((document.getElementById("autofix-diff-modal-summary")?.innerText) || "").trim();
    const diffText = String((document.getElementById("autofix-diff-modal-text")?.innerText) || "").trim();
    const applyButton = document.getElementById("btn-ai-source-apply");
    const candidateButtons = Array.from(document.querySelectorAll("#autofix-diff-modal-candidates button")).map((btn) => ({
      label: String(btn.innerText || "").trim(),
      active: btn.classList.contains("diff-modal-candidate-active"),
    }));
    const activeCandidate = candidateButtons.find((item) => item.active);
    const metaProposalMatch = meta.match(/Proposal\\s+([A-Z_]+)/i);
    const prepareButtonPresent = Array.from(document.querySelectorAll("#autofix-diff-modal-summary button"))
      .some((btn) => /Prepare patch/i.test(String(btn.innerText || "")));
    const unifiedButton = document.getElementById("autofix-diff-view-unified");
    const patchReady = /Patch ready/i.test(meta) || /A source patch diff is available\\./i.test(summary);
    const realDpNameMatches = Array.from(
      diffText.matchAll(/A\.B\.C[123]/g),
      (match) => String((match && match[0]) || "").trim(),
    ).filter(Boolean);
    const distinctRealDpNames = Array.from(new Set(realDpNameMatches));
    return {
      modal_visible: !!modal && !modal.classList.contains("hidden"),
      meta,
      summary,
      patch_ready: patchReady,
      prepare_button_present: prepareButtonPresent,
      unified_enabled: !!unifiedButton && !unifiedButton.disabled,
      candidate_labels: candidateButtons.map((item) => item.label),
      selected_candidate: String(
        (activeCandidate && activeCandidate.label)
        || (metaProposalMatch && metaProposalMatch[1])
        || "",
      ).trim(),
      diff_excerpt: diffText.slice(0, 2000),
      contains_obj_auto_sel: /obj_auto_sel/i.test(diffText),
      contains_arrow_marker: /=>/.test(diffText),
      contains_placeholder_system_obj: /System1:Obj1/i.test(diffText),
      contains_real_dp_names: distinctRealDpNames.length >= 2,
      apply_button_present: !!applyButton,
      apply_button_disabled: !!applyButton && !!applyButton.disabled,
      apply_button_text: String((applyButton && applyButton.innerText) || "").trim(),
      apply_blocked_reason: String((applyButton && applyButton.title) || "").replace(/^Blocked:\s*/i, "").trim(),
    };
  });
}

async function runAiComparePrepareSmoke(page, { timeoutMs }) {
  const result = {
    attempted: true,
    compare_opened: false,
    prepare_clicked: false,
    patch_ready: false,
    unified_view_opened: false,
    candidate_labels: [],
    selected_candidate: "",
    diff_excerpt: "",
    contains_obj_auto_sel: false,
    contains_arrow_marker: false,
    contains_placeholder_system_obj: false,
    contains_real_dp_names: false,
    apply_button_present: false,
    apply_button_disabled: false,
    apply_button_text: "",
    apply_blocked_reason: "",
    skipped_reason: "",
    before: null,
    after: null,
  };

  await page.waitForFunction(
    () => {
      const button = document.getElementById("btn-ai-diff");
      return !!button && !button.disabled && typeof button.onclick === "function";
    },
    { timeout: Math.min(timeoutMs, 30000) },
  );

  const compareClick = await page.evaluate(() => {
    const button = document.getElementById("btn-ai-diff");
    const style = button ? window.getComputedStyle(button) : null;
    const visible = !!button && style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
    if (!button) {
      return { ok: false, reason: "compare button not found", visible: false, disabled: false };
    }
    if (button.disabled) {
      return { ok: false, reason: "compare button disabled", visible, disabled: true };
    }
    button.click();
    return { ok: true, visible, disabled: false };
  });
  if (!compareClick.ok) {
    result.attempted = false;
    result.skipped_reason = String(compareClick.reason || "compare button unavailable");
    return result;
  }
  await page.waitForFunction(
    () => {
      const modal = document.getElementById("autofix-diff-modal");
      return !!modal && !modal.classList.contains("hidden");
    },
    { timeout: timeoutMs },
  );
  result.compare_opened = true;

  await page.waitForFunction(
    () => {
      const meta = String((document.getElementById("autofix-diff-modal-meta")?.innerText) || "");
      const summary = String((document.getElementById("autofix-diff-modal-summary")?.innerText) || "");
      return meta.includes("Patch missing") || meta.includes("Patch ready") || summary.includes("Prepare patch");
    },
    { timeout: Math.min(timeoutMs, 30000) },
  );

  result.before = await readAiComparePrepareState(page);

  if (!result.before.patch_ready) {
    await page.waitForFunction(
      () => Array.from(document.querySelectorAll("#autofix-diff-modal-summary button"))
        .some((btn) => /Prepare patch/i.test(String(btn.innerText || ""))),
      { timeout: Math.min(timeoutMs, 30000) },
    );
    const prepareClick = await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll("#autofix-diff-modal-summary button"))
        .find((btn) => /Prepare patch/i.test(String(btn.innerText || "")));
      if (!button) return { ok: false, reason: "prepare button not found" };
      if (button.disabled) return { ok: false, reason: "prepare button disabled" };
      button.click();
      return { ok: true };
    });
    if (!prepareClick.ok) {
      throw new Error(String(prepareClick.reason || "Prepare patch click failed"));
    }
    result.prepare_clicked = true;
  }

  await page.waitForFunction(
    () => {
      const meta = String((document.getElementById("autofix-diff-modal-meta")?.innerText) || "");
      const summary = String((document.getElementById("autofix-diff-modal-summary")?.innerText) || "");
      const unifiedButton = document.getElementById("autofix-diff-view-unified");
      return (
        /Patch ready/i.test(meta)
        || /A source patch diff is available\\./i.test(summary)
        || (!!unifiedButton && !unifiedButton.disabled)
      );
    },
    { timeout: timeoutMs },
  );

  const unifiedButton = page.locator("#autofix-diff-view-unified");
  if ((await unifiedButton.count()) && (await unifiedButton.isEnabled())) {
    await unifiedButton.click({ timeout: Math.min(timeoutMs, 15000) });
    result.unified_view_opened = true;
  }

  result.after = await readAiComparePrepareState(page);
  result.patch_ready = !!(result.after && result.after.patch_ready);
  result.candidate_labels = Array.isArray(result.after && result.after.candidate_labels) ? result.after.candidate_labels : [];
  result.selected_candidate = String((result.after && result.after.selected_candidate) || "");
  result.diff_excerpt = String((result.after && result.after.diff_excerpt) || "");
  result.contains_obj_auto_sel = !!(result.after && result.after.contains_obj_auto_sel);
  result.contains_arrow_marker = !!(result.after && result.after.contains_arrow_marker);
  result.contains_placeholder_system_obj = !!(result.after && result.after.contains_placeholder_system_obj);
  result.contains_real_dp_names = !!(result.after && result.after.contains_real_dp_names);
  result.apply_button_present = !!(result.after && result.after.apply_button_present);
  result.apply_button_disabled = !!(result.after && result.after.apply_button_disabled);
  result.apply_button_text = String((result.after && result.after.apply_button_text) || "");
  result.apply_blocked_reason = String((result.after && result.after.apply_blocked_reason) || "");
  return result;
}

async function closeAiCompareModal(page, { timeoutMs }) {
  const visible = await page.evaluate(() => {
    const modal = document.getElementById("autofix-diff-modal");
    return !!modal && !modal.classList.contains("hidden");
  });
  if (!visible) return;
  const closeButton = page.locator("#autofix-diff-modal-close");
  if (await closeButton.count()) {
    await closeButton.click({ timeout: Math.min(timeoutMs, 15000) });
  } else {
    await page.keyboard.press("Escape");
  }
  await page.waitForFunction(
    () => {
      const modal = document.getElementById("autofix-diff-modal");
      return !modal || modal.classList.contains("hidden");
    },
    { timeout: Math.min(timeoutMs, 15000) },
  );
}

async function selectSmokeTarget(page, preferredFile) {
  return page.evaluate((preferred) => {
    const all = Array.from(document.querySelectorAll("#file-list input[data-file]"));
    const target = all.find((node) => node.getAttribute("data-file") === preferred)
      || all.find((node) => /\.ctl$/i.test(node.getAttribute("data-file") || ""))
      || all[0];
    if (!target) {
      return { selectedFile: "", availableCount: 0 };
    }
    all.forEach((node) => {
      const nextChecked = node === target;
      if (node.checked === nextChecked) return;
      node.checked = nextChecked;
      node.dispatchEvent(new Event("change", { bubbles: true }));
      node.dispatchEvent(new Event("input", { bubbles: true }));
    });
    return {
      selectedFile: target.getAttribute("data-file") || "",
      availableCount: all.length,
    };
  }, preferredFile);
}

async function setCheckboxValue(page, elementId, checked) {
  return page.evaluate(({ id, nextChecked }) => {
    const node = document.getElementById(String(id || ""));
    if (!(node instanceof HTMLInputElement) || node.type !== "checkbox") {
      return { ok: false, reason: "checkbox not found" };
    }
    node.checked = !!nextChecked;
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return { ok: true, checked: !!node.checked };
  }, { id: elementId, nextChecked: !!checked });
}

async function ensureCheckboxCheckedByClick(page, selector, checked, { timeoutMs }) {
  const locator = page.locator(selector);
  if (!(await locator.count())) {
    return { ok: false, reason: "checkbox not found" };
  }
  const current = await locator.isChecked();
  if (current !== !!checked) {
    await locator.click({ timeout: Math.min(timeoutMs, 15000) });
  }
  return { ok: true, checked: await locator.isChecked() };
}

async function runSmoke(page, { baseUrl, timeoutMs, targetFile, targetCandidates = [], withLiveAiComparePrepare = false }) {
  await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#file-list input[data-file]", { timeout: timeoutMs });

  if (withLiveAiComparePrepare) {
    const liveAiToggle = await ensureCheckboxCheckedByClick(page, "#toggle-live-ai", true, { timeoutMs });
    if (!liveAiToggle.ok) {
      throw new Error(`Failed to enable Live AI before analyze: ${liveAiToggle.reason || "unknown"}`);
    }
    await page.waitForFunction(
      () => {
        const toggle = document.getElementById("toggle-live-ai");
        const modelSelect = document.getElementById("select-ai-model");
        return !!toggle
          && !!toggle.checked
          && !!modelSelect
          && !modelSelect.disabled;
      },
      { timeout: Math.min(timeoutMs, 30000) },
    );
  }

  const candidates = Array.from(new Set([targetFile, ...targetCandidates].filter(Boolean)));
  let selection = { selectedFile: "", availableCount: 0 };
  let beforeClick = { buttonFound: false };
  let beforeAnalyzeUi = {};
  let analyzeOutcome = { outcome: "timeout", sawProgress: false, snapshot: await readSmokeUiState(page) };
  const selectionAttempts = [];

  async function attemptAnalyzeCandidates(ctrlppEnabled) {
    const ctrlppResult = await setCheckboxValue(page, "toggle-ctrlppcheck", ctrlppEnabled);
    if (!ctrlppResult.ok && ctrlppEnabled) {
      return false;
    }
    for (const candidate of candidates) {
      selection = await selectSmokeTarget(page, candidate);
      if (!selection.selectedFile) {
        continue;
      }
      beforeClick = await page.evaluate(() => {
        const btn = document.getElementById("btn-analyze");
        if (!btn) return { buttonFound: false };
        const rect = btn.getBoundingClientRect().toJSON();
        const center = { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        const atPoint = document.elementFromPoint(center.x, center.y);
        return {
          buttonFound: true,
          buttonRect: rect,
          interceptingNode: atPoint ? {
            tag: atPoint.tagName,
            id: atPoint.id,
            className: atPoint.className,
          } : null,
        };
      });
      beforeAnalyzeUi = await readSmokeUiState(page);

      await page.click("#btn-analyze", { timeout: Math.min(timeoutMs, 15000) });
      analyzeOutcome = await waitForAnalyzeOutcome(page, { timeoutMs });
      selectionAttempts.push({
        file: selection.selectedFile,
        ctrlpp_enabled: !!ctrlppEnabled,
        outcome: analyzeOutcome.outcome,
        review_target_count: Number(analyzeOutcome.snapshot?.review_target_count || 0),
        result_row_count: Number(analyzeOutcome.snapshot?.result_row_count || 0),
      });
      if (effectiveReviewCount(analyzeOutcome.snapshot) > 0) {
        return true;
      }
    }
    return false;
  }

  let foundRows = await attemptAnalyzeCandidates(false);
  if (!foundRows) {
    foundRows = await attemptAnalyzeCandidates(true);
  }

  if (!selection.selectedFile) {
    throw new Error("Failed to select a file for UI smoke");
  }

  if (effectiveReviewCount(analyzeOutcome.snapshot) <= 0) {
    return {
      selection,
      selectionAttempts,
      beforeClick,
      beforeAnalyzeUi,
      analyzeOutcome,
      liveAiToggle: { ok: true, checked: false },
      aiOnDemand: {
        attempted: false,
        clicked: false,
        completed: false,
        skipped_reason: `analyze outcome=${analyzeOutcome.outcome}`,
      },
      aiComparePrepare: {
        attempted: false,
        compare_opened: false,
        prepare_clicked: false,
        patch_ready: false,
        unified_view_opened: false,
        candidate_labels: [],
        selected_candidate: "",
        diff_excerpt: "",
        contains_obj_auto_sel: false,
        contains_arrow_marker: false,
        contains_placeholder_system_obj: false,
        contains_real_dp_names: false,
        skipped_reason: `analyze outcome=${analyzeOutcome.outcome}`,
        before: null,
        after: null,
      },
      excelOnDemand: {
        attempted: false,
        clicked: false,
        completed: false,
        skipped_reason: `analyze outcome=${analyzeOutcome.outcome}`,
      },
      afterRun: analyzeOutcome.snapshot,
    };
  }

  const triageFlow = await runP1TriageSmoke(page, { timeoutMs });

  let liveAiToggle = { ok: true, checked: false };
  if (withLiveAiComparePrepare) {
    liveAiToggle = await ensureCheckboxCheckedByClick(page, "#toggle-live-ai", true, { timeoutMs });
    if (!liveAiToggle.ok) {
      throw new Error(`Failed to enable Live AI: ${liveAiToggle.reason || "unknown"}`);
    }
    await page.waitForFunction(
      () => {
        const toggle = document.getElementById("toggle-live-ai");
        const modelSelect = document.getElementById("select-ai-model");
        return !!toggle
          && !!toggle.checked
          && !!modelSelect
          && !modelSelect.disabled;
      },
      { timeout: Math.min(timeoutMs, 30000) },
    );
    await page.fill("#workspace-result-search", "PERF-SETMULTIVALUE-ADOPT-01");
    await page.waitForFunction(
      () => document.querySelectorAll("#result-body tr.result-item-row").length > 0,
      { timeout: Math.min(timeoutMs, 30000) },
    );
  }

  const selectedForAi = await selectWorkspaceRow(page, {
    timeoutMs,
    source: withLiveAiComparePrepare ? "P1" : "",
  });
  if (!selectedForAi.ok) {
    throw new Error("Failed to select a workspace row for AI smoke");
  }
  await page.click("#inspector-tab-ai", { timeout: Math.min(timeoutMs, 15000) });

  const aiOnDemand = await page.evaluate(async () => {
    const isVisible = (node) => {
      if (!node) return false;
      const style = window.getComputedStyle(node);
      return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
    };
    const pickGenerateButton = () => {
      const primary = document.getElementById("btn-ai-generate");
      const empty = document.getElementById("btn-ai-generate-empty");
      if (isVisible(primary)) return primary;
      if (isVisible(empty)) return empty;
      if (primary) return primary;
      if (empty) return empty;
      return null;
    };
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const waitForCompletion = async (button, maxMs = 40000) => {
      const startedAt = Date.now();
      while (Date.now() - startedAt < maxMs) {
        const text = String((button && button.textContent) || "").trim();
        const processing = text.includes("추가 분석 중");
        const statusNode = document.getElementById("ai-status-inline");
        const statusText = String((statusNode && statusNode.textContent) || "").trim();
        const hasOutcomeStatus =
          statusText.includes("추가 AI 분석 완료") ||
          statusText.includes("추가 AI 분석 실패") ||
          statusText.includes("결과를 찾지 못했습니다");
        if (!processing && hasOutcomeStatus) {
          return { done: true, statusText };
        }
        if (!processing && button && !button.disabled && !text.includes("추가 분석 중")) {
          return { done: true, statusText };
        }
        await wait(250);
      }
      return { done: false, statusText: String((document.getElementById("ai-status-inline")?.textContent) || "").trim() };
    };

    const button = pickGenerateButton();
    if (!button) {
      return {
        attempted: false,
        clicked: false,
        completed: false,
        skipped_reason: "generate button not found",
        button_id: "",
        button_text_before: "",
        button_text_after: "",
        status_text: "",
      };
    }
    const buttonTextBefore = String(button.textContent || "").trim();
    const buttonId = String(button.id || "");
    try {
      button.click();
      const completion = await waitForCompletion(button);
      return {
        attempted: true,
        clicked: true,
        completed: !!completion.done,
        skipped_reason: "",
        button_id: buttonId,
        button_text_before: buttonTextBefore,
        button_text_after: String((button && button.textContent) || "").trim(),
        status_text: String(completion.statusText || ""),
      };
    } catch (err) {
      return {
        attempted: true,
        clicked: false,
        completed: false,
        skipped_reason: String((err && err.message) || err || "unknown"),
        button_id: buttonId,
        button_text_before: buttonTextBefore,
        button_text_after: String((button && button.textContent) || "").trim(),
        status_text: String((document.getElementById("ai-status-inline")?.textContent) || "").trim(),
      };
    }
  });

  let aiComparePrepare = {
    attempted: false,
    compare_opened: false,
    prepare_clicked: false,
    patch_ready: false,
    unified_view_opened: false,
    candidate_labels: [],
    selected_candidate: "",
    diff_excerpt: "",
    contains_obj_auto_sel: false,
    contains_arrow_marker: false,
    contains_placeholder_system_obj: false,
    contains_real_dp_names: false,
    skipped_reason: "optional compare/prepare smoke disabled",
    before: null,
    after: null,
  };
  if (withLiveAiComparePrepare) {
    if (aiOnDemand.clicked && aiOnDemand.completed) {
      aiComparePrepare = await runAiComparePrepareSmoke(page, { timeoutMs });
      await closeAiCompareModal(page, { timeoutMs });
    } else {
      aiComparePrepare = {
        ...aiComparePrepare,
        attempted: false,
        skipped_reason: `ai on-demand incomplete: ${String(aiOnDemand.skipped_reason || aiOnDemand.status_text || "unknown")}`,
      };
    }
  }

  const excelOnDemand = await runExcelSmoke(page, { timeoutMs });

  return {
    selection,
    selectionAttempts,
    beforeClick,
    beforeAnalyzeUi,
    analyzeOutcome,
    triageFlow,
    liveAiToggle,
    aiOnDemand,
    aiComparePrepare,
    excelOnDemand,
    afterRun: await readSmokeUiState(page),
  };
}

async function main() {
  let opts;
  try {
    opts = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(`Argument error: ${err.message}`);
    printHelp();
    process.exit(2);
    return;
  }
  if (opts.help) {
    printHelp();
    return;
  }

  const projectRoot = path.resolve(__dirname, "..", "..");
  const baseUrl = `http://${opts.host}:${opts.port}`;

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (err) {
    console.error("Failed to load 'playwright'. Install prerequisites first:");
    console.error("  npm i -D playwright");
    console.error("  npx playwright install chromium");
    console.error(String(err && err.stack ? err.stack : err));
    process.exit(2);
    return;
  }

  const report = {
    tool: "playwright_ui_real_smoke",
    started_at: new Date().toISOString(),
    config: {
      host: opts.host,
      port: opts.port,
      target_file_preference: opts.targetFile,
      timeout_ms: opts.timeoutMs,
      with_live_ai_compare_prepare: opts.withLiveAiComparePrepare,
      headed: opts.headed,
      no_sandbox: opts.noSandbox,
    },
    environment: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
  };

  let backendChild = null;
  let browser;
  let context;
  let triageCleanup = null;

  try {
    const backend = await ensureBackend({
      projectRoot,
      baseUrl,
      host: opts.host,
      port: opts.port,
      python: opts.python,
      timeoutMs: opts.timeoutMs,
    });
    backendChild = backend.child;
    report.backend = {
      started_server: backend.startedServer,
      discovered_file_count: Array.isArray(backend.files) ? backend.files.length : 0,
    };
    report.startupProbe = await probeStartupAssets(baseUrl);
    if (!report.startupProbe.ok) {
      throw new Error(
        "Server/static readiness failure: "
        + JSON.stringify(report.startupProbe.status_codes || {}),
      );
    }
    report.backend.triage_reset = await resetP1TriageEntries(baseUrl);
    const targetFile = pickTargetFile(backend.files, opts.targetFile);
    report.backend.selected_target_file = targetFile;

    browser = await chromium.launch({
      headless: !opts.headed,
      args: opts.noSandbox ? ["--no-sandbox"] : [],
    });
    report.environment.browser = await browser.version();
    context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    const runtimeDiagnostics = {
      console: [],
      page_errors: [],
      dialogs: [],
      api: {
        files: null,
        analyze_start: null,
        analyze_status_last: null,
      },
    };
    page.on("console", (msg) => {
      const type = String(msg.type() || "log");
      if (type !== "error" && type !== "warning") return;
      runtimeDiagnostics.console.push({
        type,
        text: String(msg.text() || ""),
      });
    });
    page.on("pageerror", (err) => {
      runtimeDiagnostics.page_errors.push(String((err && err.stack) || (err && err.message) || err || ""));
    });
    page.on("dialog", async (dialog) => {
      runtimeDiagnostics.dialogs.push({
        type: String(dialog.type() || ""),
        message: String(dialog.message() || ""),
      });
      await dialog.dismiss();
    });
    page.on("response", async (response) => {
      try {
        const url = new URL(response.url());
        if (url.origin !== baseUrl) return;
        if (url.pathname === "/api/files") {
          runtimeDiagnostics.api.files = {
            status: response.status(),
            body: await response.text(),
          };
          return;
        }
        if (url.pathname === "/api/analyze/start") {
          let body = "";
          try {
            body = await response.text();
          } catch (_err) {}
          runtimeDiagnostics.api.analyze_start = {
            status: response.status(),
            body,
          };
          return;
        }
        if (url.pathname === "/api/analyze/status") {
          let payload = null;
          try {
            payload = await response.json();
          } catch (_err) {}
          runtimeDiagnostics.api.analyze_status_last = {
            status: response.status(),
            payload: payload ? summarizeAnalyzeStatusPayload(payload) : null,
          };
        }
      } catch (_err) {
        // ignore diagnostics errors
      }
    });
    const runStarted = Date.now();
    report.run = await runSmoke(page, {
      baseUrl,
      timeoutMs: opts.timeoutMs,
      targetFile,
      targetCandidates: Array.isArray(backend.files) ? backend.files.map((file) => file && file.name).filter(Boolean) : [],
      withLiveAiComparePrepare: opts.withLiveAiComparePrepare,
    });
    report.run.elapsed_ms = Date.now() - runStarted;
    report.diagnostics = runtimeDiagnostics;
    const triageAttempted = !!(report.run.triageFlow && report.run.triageFlow.attempted);
    const triageFlowHealthy = !triageAttempted || !!(report.run.triageFlow && report.run.triageFlow.completed);
    const aiAttempted = !!(report.run.aiOnDemand && report.run.aiOnDemand.attempted);
    const aiFlowHealthy = !aiAttempted || !!(report.run.aiOnDemand.clicked && report.run.aiOnDemand.completed);
    const aiComparePrepare = report.run.aiComparePrepare || {};
    const aiComparePrepareUnsafe =
      !!aiComparePrepare.contains_obj_auto_sel
      || !!aiComparePrepare.contains_arrow_marker
      || !!aiComparePrepare.contains_placeholder_system_obj
      || !aiComparePrepare.contains_real_dp_names;
    const aiComparePrepareConservativelyBlocked =
      !!aiComparePrepare.apply_button_present
      && !!aiComparePrepare.apply_button_disabled
      && !!aiComparePrepare.apply_blocked_reason;
    const aiComparePrepareHealthy =
      !opts.withLiveAiComparePrepare
      || (
        !!aiComparePrepare.compare_opened
        && (!!aiComparePrepare.prepare_clicked || !!(aiComparePrepare.before && aiComparePrepare.before.patch_ready))
        && !!aiComparePrepare.patch_ready
        && !!aiComparePrepare.unified_view_opened
        && (
          (!aiComparePrepareUnsafe)
          || aiComparePrepareConservativelyBlocked
        )
      );
    const excelAttempted = !!(report.run.excelOnDemand && report.run.excelOnDemand.attempted);
    const excelSkipped = !!(report.run.excelOnDemand && report.run.excelOnDemand.skipped_reason);
    const excelFlowHealthy =
      !excelAttempted ||
      (!!report.run.excelOnDemand.completed &&
        Number(report.run.excelOnDemand.final?.download_button_count || 0) > 0 &&
        !!report.run.excelOnDemand.download_triggered);
    const visibleReviewCount = effectiveReviewCount(report.run.afterRun || {});
    report.ok =
      !!(report.startupProbe && report.startupProbe.ok) &&
      !!report.run.afterRun.workspace_visible &&
      visibleReviewCount > 0 &&
      report.run.beforeClick.interceptingNode &&
      report.run.beforeClick.interceptingNode.id === "btn-analyze" &&
      triageFlowHealthy &&
      aiFlowHealthy &&
      aiComparePrepareHealthy &&
      (excelSkipped || excelFlowHealthy);
    if (!report.ok) {
      throw new Error("Real-server UI smoke assertions failed");
    }
  } catch (err) {
    report.ok = false;
    report.error = String(err && err.stack ? err.stack : err);
    throw err;
  } finally {
    try {
      triageCleanup = await resetP1TriageEntries(baseUrl);
      report.backend = {
        ...(report.backend || {}),
        triage_cleanup: triageCleanup,
      };
    } catch (_err) {}
    try {
      if (context) await context.close();
    } catch (_err) {}
    try {
      if (browser) await browser.close();
    } catch (_err) {}
    stopProcess(backendChild);
    report.finished_at = new Date().toISOString();
    const outputPath = path.isAbsolute(opts.output) ? opts.output : path.join(projectRoot, opts.output);
    ensureDir(path.dirname(outputPath));
    writeJsonReport(outputPath, report);
    console.log(`report: ${outputPath}`);
  }
}

main().catch((err) => {
  console.error(`UI smoke failed: ${String(err && err.message ? err.message : err)}`);
  process.exit(1);
});
