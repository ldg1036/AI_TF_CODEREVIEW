#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const { URL } = require("url");

function printHelp() {
  console.log(`Playwright UI benchmark for WinCC OA code review frontend (API mocked).

Usage:
  node tools/playwright_ui_benchmark.js [options]

Options:
  --files <n>                   Number of mock files (default: 20)
  --violations-per-file <n>     P1 violations per file (default: 120)
  --code-lines <n>              Lines per mock source file (default: 6000)
  --iterations <n>              Benchmark iterations (default: 3)
  --host <host>                 Static frontend host (default: 127.0.0.1)
  --port <port>                 Static frontend port (default: 4173)
  --python <cmd>                Python executable for static server (default: python)
  --output <path>               JSON result path (default: tools/benchmark_results/ui_benchmark_<ts>.json)
  --headed                      Run browser in headed mode (default: headless)
  --no-sandbox                  Chromium --no-sandbox launch arg
  --max-analyze-ms <n>          Fail if p95 analyze UI latency exceeds threshold
  --max-table-scroll-ms <n>     Fail if p95 result-table scroll benchmark exceeds threshold
  --max-code-jump-ms <n>        Fail if p95 code jump latency exceeds threshold
  --max-code-scroll-ms <n>      Fail if p95 code-view scroll benchmark exceeds threshold
  --server-start-timeout-ms <n> Static server startup timeout (default: 10000)
  --help                        Show this help

Prerequisites:
  npm i -D playwright
  npx playwright install chromium
`);
}

function parseArgs(argv) {
  const opts = {
    files: 20,
    violationsPerFile: 120,
    codeLines: 6000,
    iterations: 3,
    host: "127.0.0.1",
    port: 4173,
    python: "python",
    headed: false,
    noSandbox: false,
    maxAnalyzeMs: null,
    maxTableScrollMs: null,
    maxCodeJumpMs: null,
    maxCodeScrollMs: null,
    serverStartTimeoutMs: 10000,
    output: "",
    help: false,
  };

  const nextValue = (i, name) => {
    if (i + 1 >= argv.length) {
      throw new Error(`Missing value for ${name}`);
    }
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
      case "--files":
        opts.files = Math.max(1, asInt(nextValue(i, arg), arg));
        i += 1;
        break;
      case "--violations-per-file":
        opts.violationsPerFile = Math.max(1, asInt(nextValue(i, arg), arg));
        i += 1;
        break;
      case "--code-lines":
        opts.codeLines = Math.max(100, asInt(nextValue(i, arg), arg));
        i += 1;
        break;
      case "--iterations":
        opts.iterations = Math.max(1, asInt(nextValue(i, arg), arg));
        i += 1;
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
      case "--output":
        opts.output = String(nextValue(i, arg));
        i += 1;
        break;
      case "--headed":
        opts.headed = true;
        break;
      case "--no-sandbox":
        opts.noSandbox = true;
        break;
      case "--max-analyze-ms":
        opts.maxAnalyzeMs = asInt(nextValue(i, arg), arg);
        i += 1;
        break;
      case "--max-table-scroll-ms":
        opts.maxTableScrollMs = asInt(nextValue(i, arg), arg);
        i += 1;
        break;
      case "--max-code-jump-ms":
        opts.maxCodeJumpMs = asInt(nextValue(i, arg), arg);
        i += 1;
        break;
      case "--max-code-scroll-ms":
        opts.maxCodeScrollMs = asInt(nextValue(i, arg), arg);
        i += 1;
        break;
      case "--server-start-timeout-ms":
        opts.serverStartTimeoutMs = Math.max(1000, asInt(nextValue(i, arg), arg));
        i += 1;
        break;
      default:
        throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!opts.output) {
    opts.output = path.join("tools", "benchmark_results", `ui_benchmark_${timestampCompact()}.json`);
  }
  return opts;
}

function timestampCompact() {
  return new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function httpGetText(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on("data", (d) => chunks.push(d));
      res.on("end", () => {
        resolve({ status: res.statusCode || 0, body: Buffer.concat(chunks).toString("utf-8") });
      });
    });
    req.on("error", reject);
    req.setTimeout(2000, () => {
      req.destroy(new Error("HTTP GET timeout"));
    });
  });
}

async function waitForStaticServer(baseUrl, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const resp = await httpGetText(`${baseUrl}/index.html`);
      if (resp.status >= 200 && resp.status < 500) {
        return;
      }
    } catch (_err) {
      // retry
    }
    await sleep(200);
  }
  throw new Error(`Static frontend server did not start within ${timeoutMs}ms`);
}

function startStaticServer({ projectRoot, host, port, python }) {
  const frontendDir = path.join(projectRoot, "frontend");
  const args = ["-m", "http.server", String(port), "--bind", host];
  const child = spawn(python, args, {
    cwd: frontendDir,
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

function percentile(values, p) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[idx];
}

function avg(values) {
  if (!values.length) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function median(values) {
  return percentile(values, 50);
}

function tail(str, limit = 800) {
  const text = String(str || "");
  return text.length <= limit ? text : text.slice(-limit);
}

function buildMockDataset(options) {
  const fileMetas = [];
  const fileContents = {};
  const p1Groups = [];
  const p2Findings = [];
  const p3Reviews = [];
  let p1Total = 0;
  let p2Total = 0;

  for (let i = 0; i < options.files; i += 1) {
    const idx = i + 1;
    const fileName = `bench_${String(idx).padStart(3, "0")}.ctl`;
    fileMetas.push({ name: fileName, type: "ctl", selectable: true });

    const lines = [];
    for (let lineNo = 1; lineNo <= options.codeLines; lineNo += 1) {
      if (lineNo === 1) {
        lines.push(`main() { // ${fileName}`);
      } else if (lineNo === options.codeLines) {
        lines.push("}");
      } else if (lineNo % 37 === 0) {
        lines.push(`  dpSet(\"System.${idx}.Value\", ${lineNo});`);
      } else if (lineNo % 41 === 0) {
        lines.push(`  int v${lineNo}; dpGet(\"System.${idx}.Value\", v${lineNo});`);
      } else {
        lines.push(`  int line_${lineNo} = ${lineNo};`);
      }
    }
    fileContents[fileName] = lines.join("\n");

    const violations = [];
    for (let j = 0; j < options.violationsPerFile; j += 1) {
      const line = Math.max(2, ((j * 47) % Math.max(3, options.codeLines - 2)) + 2);
      const ruleId = j % 3 === 0 ? "PERF-02" : (j % 3 === 1 ? "STYLE-NAME-01" : "CLEAN-DEAD-01");
      const severity = j % 11 === 0 ? "Critical" : (j % 4 === 0 ? "Warning" : "Info");
      const issueId = `P1-${ruleId}-${idx}-${j + 1}`;
      violations.push({
        issue_id: issueId,
        rule_id: ruleId,
        rule_item: `Mock item ${ruleId}`,
        priority_origin: "P1",
        severity,
        line,
        file: fileName,
        object: fileName,
        message: `Mock violation ${j + 1} at line ${line} in ${fileName}`,
      });
      p1Total += 1;

      if (j < 2) {
        p3Reviews.push({
          issue_id: `P3-${idx}-${j + 1}`,
          parent_issue_id: issueId,
          object: fileName,
          event: "Global",
          status: "Pending",
          source: "live",
          review: `Mock AI suggestion for ${issueId}`,
        });
      }
    }

    p1Groups.push({
      object: fileName,
      event: "Global",
      violations,
    });

    const p2Line = Math.min(options.codeLines - 1, Math.max(2, 100 + i));
    p2Findings.push({
      issue_id: `P2-CTRLPPCHECK-${idx}`,
      priority_origin: "P2",
      source: "CtrlppCheck",
      severity: "warning",
      line: p2Line,
      file: fileName,
      object: fileName,
      rule_id: "ctrlppcheck.mock",
      message: `Mock ctrlppcheck warning for ${fileName}`,
    });
    p2Total += 1;
  }

  return {
    files: fileMetas,
    fileContents,
    allFileNames: fileMetas.map((f) => f.name),
    allP1Groups: p1Groups,
    allP2: p2Findings,
    allP3: p3Reviews,
    totals: { p1Total, p2Total, p3Total: p3Reviews.length },
  };
}

function filterAnalyzePayload(dataset, selectedFileNames) {
  const selectedSet = new Set((selectedFileNames && selectedFileNames.length ? selectedFileNames : dataset.allFileNames));
  const p1 = dataset.allP1Groups.filter((g) => selectedSet.has(g.object));
  const p2 = dataset.allP2.filter((v) => selectedSet.has(v.file || v.object));
  const p3 = dataset.allP3.filter((r) => selectedSet.has(r.object));
  let p1Total = 0;
  p1.forEach((g) => { p1Total += Array.isArray(g.violations) ? g.violations.length : 0; });
  const p2Total = p2.length;
  const p3Total = p3.length;

  return {
    output_dir: "mock-ui-benchmark-session",
    summary: {
      requested_file_count: selectedSet.size,
      successful_file_count: selectedSet.size,
      failed_file_count: 0,
      p1_total: p1Total,
      p2_total: p2Total,
      p3_total: p3Total,
    },
    violations: { P1: p1, P2: p2, P3: p3 },
    report_paths: { html: [], excel: [], reviewed_txt: [] },
    report_jobs: { excel: { pending_count: 0, running_count: 0, completed_count: 0, failed_count: 0, jobs: [] } },
    metrics: {
      request_id: "mock-ui-benchmark",
      file_count: selectedSet.size,
      timings_ms: { total: 42, collect: 3, analyze: 12, report: 7, ai: 5, server_total: 50 },
      llm_calls: p3.length,
      ctrlpp_calls: selectedSet.size,
      bytes_read: 0,
      bytes_written: 0,
      convert_cache: { hits: 0, misses: 0 },
      excel_template_cache: { hits: 0, misses: 0 },
      per_file: [],
    },
    errors: [],
  };
}

async function installMockRoutes(page, dataset) {
  await page.route("**/api/files*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({ files: dataset.files }),
    });
  });

  await page.route("**/api/file-content*", async (route) => {
    const reqUrl = new URL(route.request().url());
    const name = String(reqUrl.searchParams.get("name") || "");
    const content = dataset.fileContents[name] || dataset.fileContents[dataset.allFileNames[0]] || "main() {}";
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        file: name,
        resolved_name: name,
        source: "source",
        content,
      }),
    });
  });

  await page.route("**/api/analyze", async (route) => {
    let selected = [];
    try {
      const postData = route.request().postData();
      const parsed = postData ? JSON.parse(postData) : {};
      if (parsed && Array.isArray(parsed.selected_files)) {
        selected = parsed.selected_files.filter((x) => typeof x === "string");
      }
    } catch (_err) {
      selected = [];
    }
    const payload = filterAnalyzePayload(dataset, selected);
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(payload),
    });
  });

  await page.route("**/api/report/excel", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        all_completed: true,
        report_paths: { excel: [] },
        report_jobs: { excel: { pending_count: 0, running_count: 0, completed_count: 0, failed_count: 0, jobs: [] } },
      }),
    });
  });

  await page.route("**/api/autofix/**", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({ error: "mock benchmark route" }),
    });
  });
}

async function waitDoubleRaf(page) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function measureTableScroll(page) {
  return page.evaluate(async () => {
    const wrap = document.querySelector(".result-table");
    if (!wrap) return { ms: 0, steps: 0, maxRenderedRows: 0, scrollHeight: 0, clientHeight: 0 };
    const max = Math.max(0, wrap.scrollHeight - wrap.clientHeight);
    const samples = [];
    const start = performance.now();
    const pass = async (positions) => {
      for (const pos of positions) {
        wrap.scrollTop = pos;
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        samples.push({
          pos,
          renderedRows: document.querySelectorAll("#result-body tr.result-item-row").length,
        });
      }
    };
    const forward = [];
    for (let i = 0; i <= 12; i += 1) {
      forward.push(Math.round((max * i) / 12));
    }
    const backward = [];
    for (let i = 11; i >= 0; i -= 1) {
      backward.push(Math.round((max * i) / 11));
    }
    await pass(forward);
    await pass(backward);
    const elapsed = performance.now() - start;
    const maxRenderedRows = samples.reduce((acc, item) => Math.max(acc, item.renderedRows || 0), 0);
    return {
      ms: Math.round(elapsed),
      steps: samples.length,
      maxRenderedRows,
      minRenderedRows: samples.reduce((acc, item) => Math.min(acc, item.renderedRows || 0), Number.MAX_SAFE_INTEGER),
      scrollHeight: wrap.scrollHeight,
      clientHeight: wrap.clientHeight,
    };
  });
}

async function clickDeepRowAndMeasureJump(page) {
  await page.evaluate(() => {
    const wrap = document.querySelector(".result-table");
    if (wrap) {
      wrap.scrollTop = Math.max(0, (wrap.scrollHeight - wrap.clientHeight) * 0.8);
    }
  });
  await waitDoubleRaf(page);
  const rows = page.locator("#result-body tr.result-item-row");
  const rowCount = await rows.count();
  if (rowCount < 1) {
    throw new Error("No result rows rendered for jump benchmark");
  }
  const target = rows.nth(Math.max(0, rowCount - 1));

  const t0 = Date.now();
  await target.evaluate((el) => el.click());
  await page.waitForFunction(
    () => {
      const highlighted = document.querySelector(".code-lines-window .line-highlight, .code-lines-window .line-highlight-near");
      if (highlighted) return true;
      const codeViewer = document.getElementById("code-viewer");
      if (!codeViewer) return false;
      const renderedLines = document.querySelectorAll(".code-lines-window .code-line").length;
      return renderedLines > 0 && Number(codeViewer.scrollTop || 0) >= 0;
    },
    { timeout: 15000 },
  );
  await waitDoubleRaf(page);
  const elapsedMs = Date.now() - t0;

  const details = await page.evaluate(() => {
    const highlighted = document.querySelector(".code-lines-window .line-highlight, .code-lines-window .line-highlight-near");
    const codeViewer = document.getElementById("code-viewer");
    const renderedLines = document.querySelectorAll(".code-lines-window .code-line").length;
    return {
      highlightedLine: highlighted ? Number.parseInt(highlighted.getAttribute("data-line") || "0", 10) || 0 : 0,
      renderedLines,
      codeScrollTop: codeViewer ? Math.round(codeViewer.scrollTop || 0) : 0,
    };
  });

  return { ms: elapsedMs, visibleRowsBeforeClick: rowCount, ...details };
}

async function measureCodeViewerScroll(page) {
  return page.evaluate(async () => {
    const viewer = document.getElementById("code-viewer");
    if (!viewer) return { ms: 0, steps: 0, maxRenderedLines: 0, scrollHeight: 0, clientHeight: 0 };
    const max = Math.max(0, viewer.scrollHeight - viewer.clientHeight);
    const positions = [];
    for (let i = 0; i <= 10; i += 1) {
      positions.push(Math.round((max * i) / 10));
    }
    const start = performance.now();
    let maxRenderedLines = 0;
    for (const pos of positions) {
      viewer.scrollTop = pos;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      maxRenderedLines = Math.max(maxRenderedLines, document.querySelectorAll(".code-lines-window .code-line").length);
    }
    const elapsed = performance.now() - start;
    return {
      ms: Math.round(elapsed),
      steps: positions.length,
      maxRenderedLines,
      scrollHeight: viewer.scrollHeight,
      clientHeight: viewer.clientHeight,
    };
  });
}

async function runIteration(page, baseUrl, iterationIndex) {
  await page.goto(`${baseUrl}/index.html`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#file-list input[data-file]", { timeout: 15000 });
  await page.evaluate(() => {
    const el = document.getElementById("nav-workspace");
    if (el) el.click();
  });

  const analyzeStarted = Date.now();
  await page.evaluate(() => {
    const el = document.getElementById("btn-analyze");
    if (el) el.click();
  });
  await page.waitForFunction(
    () => document.querySelectorAll("#result-body tr.result-item-row").length > 0,
    { timeout: 30000 },
  );
  await waitDoubleRaf(page);
  const analyzeUiMs = Date.now() - analyzeStarted;

  const tableSnapshot = await page.evaluate(() => ({
    renderedRows: document.querySelectorAll("#result-body tr.result-item-row").length,
    totalIssues: document.getElementById("total-issues") ? document.getElementById("total-issues").textContent : "",
    workspaceVisible: getComputedStyle(document.getElementById("workspace-view")).display !== "none",
  }));

  const tableScroll = await measureTableScroll(page);
  const codeJump = await clickDeepRowAndMeasureJump(page);
  const codeScroll = await measureCodeViewerScroll(page);

  return {
    iteration: iterationIndex,
    analyzeUiMs,
    tableSnapshot,
    tableScroll,
    codeJump,
    codeScroll,
  };
}

function summarizeIterations(iterations) {
  const analyze = iterations.map((x) => x.analyzeUiMs);
  const tableScroll = iterations.map((x) => x.tableScroll.ms);
  const codeJump = iterations.map((x) => x.codeJump.ms);
  const codeScroll = iterations.map((x) => x.codeScroll.ms);

  const metricSummary = (arr) => ({
    min: Math.min(...arr),
    avg: Math.round(avg(arr)),
    median: Math.round(median(arr)),
    p95: Math.round(percentile(arr, 95)),
    max: Math.max(...arr),
  });

  return {
    analyzeUiMs: metricSummary(analyze),
    resultTableScrollMs: metricSummary(tableScroll),
    codeJumpMs: metricSummary(codeJump),
    codeViewerScrollMs: metricSummary(codeScroll),
    maxVisibleResultRows: Math.max(...iterations.map((x) => x.tableScroll.maxRenderedRows || 0)),
    maxVisibleCodeLines: Math.max(...iterations.map((x) => x.codeScroll.maxRenderedLines || 0), ...iterations.map((x) => x.codeJump.renderedLines || 0)),
  };
}

function evaluateThresholds(summary, opts) {
  const failures = [];
  if (opts.maxAnalyzeMs != null && summary.analyzeUiMs.p95 > opts.maxAnalyzeMs) {
    failures.push(`analyzeUiMs.p95 ${summary.analyzeUiMs.p95} > ${opts.maxAnalyzeMs}`);
  }
  if (opts.maxTableScrollMs != null && summary.resultTableScrollMs.p95 > opts.maxTableScrollMs) {
    failures.push(`resultTableScrollMs.p95 ${summary.resultTableScrollMs.p95} > ${opts.maxTableScrollMs}`);
  }
  if (opts.maxCodeJumpMs != null && summary.codeJumpMs.p95 > opts.maxCodeJumpMs) {
    failures.push(`codeJumpMs.p95 ${summary.codeJumpMs.p95} > ${opts.maxCodeJumpMs}`);
  }
  if (opts.maxCodeScrollMs != null && summary.codeViewerScrollMs.p95 > opts.maxCodeScrollMs) {
    failures.push(`codeViewerScrollMs.p95 ${summary.codeViewerScrollMs.p95} > ${opts.maxCodeScrollMs}`);
  }
  return failures;
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
  const dataset = buildMockDataset(opts);

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch (err) {
    console.error("Failed to load 'playwright'. Install prerequisites first:");
    console.error("  npm i -D playwright");
    console.error("  npx playwright install chromium");
    console.error(`Detail: ${tail(err && err.stack ? err.stack : err)}`);
    process.exit(2);
    return;
  }

  const staticServer = startStaticServer({ projectRoot, host: opts.host, port: opts.port, python: opts.python });
  let browser;
  let context;
  const startedAt = new Date().toISOString();

  const report = {
    tool: "playwright_ui_benchmark",
    started_at: startedAt,
    config: {
      files: opts.files,
      violations_per_file: opts.violationsPerFile,
      code_lines: opts.codeLines,
      iterations: opts.iterations,
      host: opts.host,
      port: opts.port,
      headed: opts.headed,
      no_sandbox: opts.noSandbox,
    },
    environment: {
      node: process.version,
      platform: process.platform,
      arch: process.arch,
    },
    dataset: {
      total_files: dataset.files.length,
      total_p1_groups: dataset.allP1Groups.length,
      total_p1_violations: dataset.totals.p1Total,
      total_p2: dataset.totals.p2Total,
      total_p3: dataset.totals.p3Total,
    },
    iterations: [],
    summary: null,
    thresholds: {
      maxAnalyzeMs: opts.maxAnalyzeMs,
      maxTableScrollMs: opts.maxTableScrollMs,
      maxCodeJumpMs: opts.maxCodeJumpMs,
      maxCodeScrollMs: opts.maxCodeScrollMs,
    },
    threshold_failures: [],
  };

  try {
    await waitForStaticServer(baseUrl, opts.serverStartTimeoutMs);
    browser = await chromium.launch({
      headless: !opts.headed,
      args: opts.noSandbox ? ["--no-sandbox"] : [],
    });
    report.environment.browser = await browser.version();
    context = await browser.newContext();
    const page = await context.newPage();
    await installMockRoutes(page, dataset);

    for (let i = 0; i < opts.iterations; i += 1) {
      const iterationResult = await runIteration(page, baseUrl, i + 1);
      report.iterations.push(iterationResult);
      process.stdout.write(
        `[${i + 1}/${opts.iterations}] analyze=${iterationResult.analyzeUiMs}ms tableScroll=${iterationResult.tableScroll.ms}ms ` +
        `jump=${iterationResult.codeJump.ms}ms codeScroll=${iterationResult.codeScroll.ms}ms\n`
      );
    }

    report.summary = summarizeIterations(report.iterations);
    report.threshold_failures = evaluateThresholds(report.summary, opts);
  } catch (err) {
    report.error = tail(err && err.stack ? err.stack : err, 2000);
    throw err;
  } finally {
    try {
      if (context) await context.close();
    } catch (_err) {}
    try {
      if (browser) await browser.close();
    } catch (_err) {}
    stopProcess(staticServer);
  }

  const outputPath = path.isAbsolute(opts.output) ? opts.output : path.join(projectRoot, opts.output);
  ensureDir(path.dirname(outputPath));
  report.finished_at = new Date().toISOString();
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), "utf-8");

  console.log("\nSummary:");
  console.log(`- analyzeUiMs p95: ${report.summary.analyzeUiMs.p95}`);
  console.log(`- resultTableScrollMs p95: ${report.summary.resultTableScrollMs.p95}`);
  console.log(`- codeJumpMs p95: ${report.summary.codeJumpMs.p95}`);
  console.log(`- codeViewerScrollMs p95: ${report.summary.codeViewerScrollMs.p95}`);
  console.log(`- maxVisibleResultRows(rendered): ${report.summary.maxVisibleResultRows}`);
  console.log(`- maxVisibleCodeLines(rendered): ${report.summary.maxVisibleCodeLines}`);
  console.log(`- report: ${outputPath}`);

  if (report.threshold_failures.length) {
    console.error("\nThreshold failures:");
    report.threshold_failures.forEach((msg) => console.error(`- ${msg}`));
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(`Benchmark failed: ${tail(err && err.stack ? err.stack : err, 2000)}`);
  process.exit(1);
});
