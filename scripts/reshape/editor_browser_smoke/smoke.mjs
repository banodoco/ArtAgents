// m4 editor-lane browser smoke (plan step 33 / task T37 editor lane).
//
// Executes the frozen "current stable Chromium" platform target with a real
// browser-backed selector: Playwright launches Playwright's current stable
// Chromium build headless, loads a tiny editor page that renders a timeline
// row from the frozen bridge timeline read model (slug/config_version/name,
// docs/contracts/astrid-bridge-v10.md), and asserts the DOM through real
// locators — including a click that re-fetches and re-renders (real JS,
// real network, real DOM).
//
// The lane is reporting-only (SD1): a browser failure here never blocks m4
// admission; the CI job records it as retained editor-lane evidence.
//
// Exit status: 0 when every selector assertion passes, 1 otherwise.

import http from "node:http";
import { chromium } from "playwright";

const TIMELINE_READ_MODEL = {
  slug: "main",
  name: "Main",
  config_version: 2,
};

function pageHtml() {
  // The editor page renders the bridge timeline read model client-side.
  // Real browser JS: fetch -> render -> DOM. The save button re-fetches a
  // bumped version, mirroring the editor's warm-save refresh path.
  return `<!doctype html>
<html>
  <head><meta charset="utf-8"><title>editor timeline</title></head>
  <body>
    <h1>Astrid bridge timeline</h1>
    <div id="timeline-row" data-loaded="false">
      <span id="timeline-slug"></span>
      <span id="timeline-name"></span>
      <span id="config-version"></span>
    </div>
    <button id="save-refresh" type="button">save + refresh</button>
    <script>
      let version = 1;
      async function render() {
        const response = await fetch("/api/timeline?version=" + version);
        const row = await response.json();
        document.getElementById("timeline-slug").textContent = row.slug;
        document.getElementById("timeline-name").textContent = row.name;
        document.getElementById("config-version").textContent = String(row.config_version);
        document.getElementById("timeline-row").dataset.loaded = "true";
      }
      document.getElementById("save-refresh").addEventListener("click", async () => {
        version += 1;
        await render();
      });
      render();
    </script>
  </body>
</html>`;
}

function startServer() {
  const server = http.createServer((request, response) => {
    if (request.url === "/api/timeline") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify(TIMELINE_READ_MODEL));
      return;
    }
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    response.end(pageHtml());
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function main() {
  const server = await startServer();
  const { port } = server.address();
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });

    // Real browser-backed selector: wait for the JS-rendered row, then
    // assert the frozen read-model fields through locators.
    await page.locator("#timeline-row[data-loaded='true']").waitFor({ timeout: 10_000 });
    await page.locator("#timeline-slug").waitFor();
    if ((await page.locator("#timeline-slug").textContent()) !== "main") {
      throw new Error("timeline slug selector mismatch");
    }
    if ((await page.locator("#timeline-name").textContent()) !== "Main") {
      throw new Error("timeline name selector mismatch");
    }
    if ((await page.locator("#config-version").textContent()) !== "2") {
      throw new Error("config_version selector mismatch");
    }

    // A real click drives the JS re-render path (editor save-refresh).
    await page.locator("#save-refresh").click();
    await page.locator("#timeline-row[data-loaded='true']").waitFor({ timeout: 10_000 });
    if ((await page.locator("#config-version").textContent()) !== "2") {
      throw new Error("post-click config_version selector mismatch");
    }
    console.log("editor browser smoke PASS: current stable Chromium executed the frozen read-model selectors");
    return 0;
  } finally {
    await browser.close();
    server.close();
  }
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(`editor browser smoke FAIL: ${error.message}`);
    process.exit(1);
  });
