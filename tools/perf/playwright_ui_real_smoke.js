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

function httpGetJson(url) {
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
  const args = [
    "-c",
    "import sys; sys.path.insert(0, r'" + projectRoot.replace(/\\/g, "\\\\") + "\\backend'); "
      + "from server import run_server; run_server(port=" + String(port) + ")",
  ];
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

async function runSmoke(page, { baseUrl, timeoutMs, targetFile }) {
  await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#file-list input[data-file]", { timeout: timeoutMs });

  const selection = await page.evaluate((preferred) => {
    const all = Array.from(document.querySelectorAll("#file-list input[data-file]"));
    const target = all.find((node) => node.getAttribute("data-file") === preferred) || all.find((node) => /\.ctl$/i.test(node.getAttribute("data-file") || "")) || all[0];
    if (!target) {
      return { selectedFile: "", availableCount: 0 };
    }
    all.forEach((node) => { node.checked = false; });
    target.checked = true;
    return {
      selectedFile: target.getAttribute("data-file") || "",
      availableCount: all.length,
    };
  }, targetFile);

  if (!selection.selectedFile) {
    throw new Error("Failed to select a file for UI smoke");
  }

  const beforeClick = await page.evaluate(() => {
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

  await page.click("#btn-analyze", { timeout: Math.min(timeoutMs, 15000) });
  await page.waitForFunction(
    () => document.querySelectorAll("#result-body tr.result-item-row").length > 0,
    { timeout: timeoutMs },
  );

  return {
    selection,
    beforeClick,
    afterRun: await page.evaluate(() => ({
      rows: document.querySelectorAll("#result-body tr.result-item-row").length,
      totalIssues: document.getElementById("total-issues") ? String(document.getElementById("total-issues").textContent || "") : "",
      criticalIssues: document.getElementById("critical-issues") ? String(document.getElementById("critical-issues").textContent || "") : "",
      warningIssues: document.getElementById("warning-issues") ? String(document.getElementById("warning-issues").textContent || "") : "",
      workspaceVisible: !!document.getElementById("workspace-view") && getComputedStyle(document.getElementById("workspace-view")).display !== "none",
      resultBodyVisible: !!document.getElementById("result-body"),
      progressPanelVisible: !!document.getElementById("analyze-progress-panel") && getComputedStyle(document.getElementById("analyze-progress-panel")).display !== "none",
    })),
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
    const targetFile = pickTargetFile(backend.files, opts.targetFile);
    report.backend.selected_target_file = targetFile;

    browser = await chromium.launch({
      headless: !opts.headed,
      args: opts.noSandbox ? ["--no-sandbox"] : [],
    });
    report.environment.browser = await browser.version();
    context = await browser.newContext();
    const page = await context.newPage();
    const runStarted = Date.now();
    report.run = await runSmoke(page, { baseUrl, timeoutMs: opts.timeoutMs, targetFile });
    report.run.elapsed_ms = Date.now() - runStarted;
    report.ok =
      !!report.run.afterRun.workspaceVisible &&
      Number.parseInt(report.run.afterRun.totalIssues || "0", 10) > 0 &&
      Number(report.run.afterRun.rows || 0) > 0 &&
      report.run.beforeClick.interceptingNode &&
      report.run.beforeClick.interceptingNode.id === "btn-analyze";
    if (!report.ok) {
      throw new Error("Real-server UI smoke assertions failed");
    }
  } catch (err) {
    report.ok = false;
    report.error = String(err && err.stack ? err.stack : err);
    throw err;
  } finally {
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
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), "utf-8");
    console.log(`report: ${outputPath}`);
  }
}

main().catch((err) => {
  console.error(`UI smoke failed: ${String(err && err.message ? err.message : err)}`);
  process.exit(1);
});
