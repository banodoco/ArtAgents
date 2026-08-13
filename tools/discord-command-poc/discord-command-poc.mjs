#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import {
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline/promises";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "../..");

function usage() {
  return `Usage:
  npm start -- --channel-url <discord channel URL> \\
    (--command <text> | --command-file <path>) [options]

Options:
  --submit                 Press Enter after filling the command.
  --no-watch               After a validated submission, record it and return
                           without waiting for its generated attachment.
  --idle                   Open the channel without running an initial command.
                           Requires --keep-open.
  --fetch-only             Do not type or submit; download a matching completed
                           attachment already visible in the channel.
  --match <text>           Require this text in the response message or URL.
  --link-match <text>      Additionally require this text in an attachment URL.
  --exclude-filename <name>
                           Ignore attachment links with this basename. Repeatable.
  --after <ISO timestamp>  Ignore Discord messages at or before this time.
  --message-id <snowflake> In fetch mode, deep-link to this known Discord
                           response before polling.
  --keep-open              Keep Chrome open and accept more commands on stdin.
                           Enter :file <path> or paste one command per line.
                           Enter :quit to close the browser.
  --no-settle              Skip the randomized pre-action settle pause
                           before action. Useful for bounded executor runs.
  --profile-dir <path>     Persistent Chrome profile directory.
                           Default: .tmp/discord-command-poc-profile
  --cdp-port <n>           Local controller port for durable Chrome.
                           Default: 9333
  --output-dir <path>      Download/log directory.
                           Default: runs/discord-command-poc
  --timeout-seconds <n>    Login/response timeout. Default: 1800
  --expected-author <text> Only accept attachments inside a message whose
                           visible text contains this author label.
  --help                   Show this help.

Attachment-valued slash options use a local path prefixed with @:
  input_media:@/path/to/reference.png
  input_media_2:@/path/to/second-reference.png

The tool launches a visible, dedicated Chrome profile. On the first run, sign
in to Discord in that window. It submits at most once and downloads the first
new attachment observed after submission.`;
}

function parseArgs(argv) {
  const options = {
    submit: false,
    idle: false,
    fetchOnly: false,
    match: null,
    linkMatch: null,
    excludeFilenames: [],
    after: null,
    keepOpen: false,
    profileDir: path.join(REPO_ROOT, ".tmp/discord-command-poc-profile"),
    cdpPort: 9333,
    outputDir: path.join(REPO_ROOT, "runs/discord-command-poc"),
    timeoutSeconds: 1800,
    expectedAuthor: null,
    messageId: null,
    noSettle: false,
    noWatch: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`Missing value after ${argument}`);
      }
      return argv[index];
    };

    switch (argument) {
      case "--channel-url":
        options.channelUrl = next();
        break;
      case "--command":
        options.command = next();
        break;
      case "--command-file":
        options.commandFile = next();
        break;
      case "--profile-dir":
        options.profileDir = path.resolve(next());
        break;
      case "--cdp-port":
        options.cdpPort = Number(next());
        break;
      case "--output-dir":
        options.outputDir = path.resolve(next());
        break;
      case "--timeout-seconds":
        options.timeoutSeconds = Number(next());
        break;
      case "--expected-author":
        options.expectedAuthor = next();
        break;
      case "--submit":
        options.submit = true;
        break;
      case "--no-watch":
        options.noWatch = true;
        break;
      case "--idle":
        options.idle = true;
        break;
      case "--fetch-only":
        options.fetchOnly = true;
        break;
      case "--match":
        options.match = next();
        break;
      case "--link-match":
        options.linkMatch = next();
        break;
      case "--exclude-filename":
        options.excludeFilenames.push(next());
        break;
      case "--after":
        options.after = next();
        break;
      case "--message-id":
        options.messageId = next();
        break;
      case "--keep-open":
        options.keepOpen = true;
        break;
      case "--no-settle":
        options.noSettle = true;
        break;
      case "--help":
      case "-h":
        options.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${argument}`);
    }
  }

  return options;
}

function validateOptions(options) {
  if (options.help) {
    return;
  }
  if (!options.channelUrl) {
    throw new Error("--channel-url is required");
  }
  const channelUrl = new URL(options.channelUrl);
  if (
    channelUrl.protocol !== "https:" ||
    channelUrl.hostname !== "discord.com" ||
    !/^\/channels\/\d+\/\d+\/?$/.test(channelUrl.pathname)
  ) {
    throw new Error(
      "--channel-url must be an https://discord.com/channels/<guild>/<channel> URL",
    );
  }
  if (options.idle && options.fetchOnly) {
    throw new Error("--idle and --fetch-only cannot be combined");
  }
  if (options.noWatch && !options.submit) {
    throw new Error("--no-watch requires --submit");
  }
  if (options.noWatch && (options.idle || options.fetchOnly || options.keepOpen)) {
    throw new Error("--no-watch cannot be combined with idle, fetch, or keep-open");
  }
  if (options.after && Number.isNaN(Date.parse(options.after))) {
    throw new Error("--after must be a valid ISO timestamp");
  }
  if (options.messageId && !/^\d+$/.test(options.messageId)) {
    throw new Error("--message-id must be a Discord snowflake");
  }
  for (const filename of options.excludeFilenames) {
    if (!filename || /[/\\]/.test(filename)) {
      throw new Error("--exclude-filename requires a basename, not a path");
    }
  }
  if (options.fetchOnly) {
    if (options.command || options.commandFile) {
      throw new Error(
        "--fetch-only cannot be combined with --command or --command-file",
      );
    }
  } else if (options.idle) {
    if (!options.keepOpen) {
      throw new Error("--idle requires --keep-open");
    }
    if (options.command || options.commandFile) {
      throw new Error("--idle cannot be combined with --command or --command-file");
    }
  } else if (Boolean(options.command) === Boolean(options.commandFile)) {
    throw new Error("Provide exactly one of --command or --command-file");
  }
  if (
    !Number.isFinite(options.timeoutSeconds) ||
    options.timeoutSeconds < 30 ||
    options.timeoutSeconds > 7200
  ) {
    throw new Error("--timeout-seconds must be between 30 and 7200");
  }
  if (
    !Number.isInteger(options.cdpPort) ||
    options.cdpPort < 1024 ||
    options.cdpPort > 65535
  ) {
    throw new Error("--cdp-port must be an integer between 1024 and 65535");
  }
}

async function loadCommand(options) {
  const command = options.commandFile
    ? await readFile(path.resolve(options.commandFile), "utf8")
    : options.command;
  const trimmed = command.trim();
  if (!trimmed.startsWith("/")) {
    throw new Error("The command must start with /");
  }
  if (trimmed.length > 6000) {
    throw new Error("The command is unexpectedly long (maximum 6000 characters)");
  }
  return trimmed;
}

function timestampSlug() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function attachmentName(rawUrl, index) {
  const url = new URL(rawUrl);
  const candidate = decodeURIComponent(path.basename(url.pathname));
  const safe = candidate
    .replace(/[^a-zA-Z0-9._-]+/g, "_")
    .replace(/^[_\.]+/, "")
    .slice(0, 180);
  return safe || `attachment-${index}`;
}

function randomBetween(minMs, maxMs) {
  return minMs + Math.floor((maxMs - minMs + 1) * Math.random());
}

// Jittered wait for the polling loops only. The typing, clicking, and
// submission steps keep their fixed waits so Discord's UI stays reliable.
async function jitteredWait(page, minMs, maxMs) {
  await page.waitForTimeout(randomBetween(minMs, maxMs));
}

// Bounded UI timing constants. These are for page readiness, not concealment.
const SETTLE_MIN_MS = 3_000;
const SETTLE_MAX_MS = 14_000;
const GAP_MIN_MS = 2_000;
const GAP_MAX_MS = 8_000;

async function humanClick(page, locator) {
  await locator.click();
}

async function humanSettle(page, minMs, maxMs) {
  const total = randomBetween(minMs, maxMs);
  if (total > 0) {
    await page.waitForTimeout(total);
  }
}

async function humanWait(page) {
  // Poll with jitter so concurrent responses do not synchronize reload work.
  await jitteredWait(page, 3_000, 8_000);
}

async function visibleComposer(page, timeoutMs) {
  const selectors = [
    '[data-slate-editor="true"][contenteditable="true"]',
    '[role="textbox"][contenteditable="true"]',
  ];
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    for (const selector of selectors) {
      const candidates = page.locator(selector);
      const count = await candidates.count();
      for (let index = count - 1; index >= 0; index -= 1) {
        const candidate = candidates.nth(index);
        if (await candidate.isVisible().catch(() => false)) {
          return candidate;
        }
      }
    }
    await jitteredWait(page, 600, 1400);
  }

  throw new Error(
    "Discord's message composer did not appear before the timeout. " +
      "Check that you signed in and can send messages in the channel.",
  );
}

async function newAttachmentMessage(
  page,
  afterMessageId,
  expectedAuthor,
  matchText = null,
  linkMatch = null,
  excludeFilenames = [],
) {
  const normalizedExcludeFilenames = [
    ...new Set(
      excludeFilenames.map((filename) =>
        filename.normalize("NFC").toLowerCase(),
      ),
    ),
  ];
  const messages = await page
    .locator('li[id^="chat-messages-"]')
    .evaluateAll(
      (elements, filter) => {
        const isNewer = (candidate, baseline) =>
          candidate.length > baseline.length ||
          (candidate.length === baseline.length && candidate > baseline);
        const excludedFilenames = new Set(filter.excludeFilenames);
        const filenameFromLink = (link) => {
          try {
            const pathname = new URL(link).pathname;
            const encoded = pathname.slice(pathname.lastIndexOf("/") + 1);
            let decoded = encoded;
            try {
              decoded = decodeURIComponent(encoded);
            } catch {
              // Keep the encoded basename if Discord supplied malformed escaping.
            }
            return decoded.normalize("NFC").toLowerCase();
          } catch {
            return "";
          }
        };

        return elements.flatMap((message) => {
          const messageId = message.id.match(/(\d+)$/)?.[1];
          if (!messageId || !isNewer(messageId, filter.afterMessageId)) {
            return [];
          }
          const text = message.textContent ?? "";
          if (
            filter.expectedAuthor &&
            !text.toLowerCase().includes(filter.expectedAuthor.toLowerCase())
          ) {
            return [];
          }
          const links = [
            ...message.querySelectorAll(
              'a[href*="cdn.discordapp.com/attachments/"], ' +
                'a[href*="media.discordapp.net/attachments/"]',
            ),
          ]
            .map((anchor) => anchor.href)
            .filter(Boolean)
            .filter(
              (link) => !excludedFilenames.has(filenameFromLink(link)),
            )
            .filter(
              (link) =>
                !filter.linkMatch ||
                link.toLowerCase().includes(filter.linkMatch.toLowerCase()),
            );
          if (
            filter.matchText &&
            !text.toLowerCase().includes(filter.matchText.toLowerCase()) &&
            !links.some((link) =>
              link.toLowerCase().includes(filter.matchText.toLowerCase()),
            )
          ) {
            return [];
          }
          return links.length
            ? [{ messageId, text: text.slice(0, 500), links: [...new Set(links)] }]
            : [];
        });
      },
      {
        afterMessageId,
        expectedAuthor,
        matchText,
        linkMatch,
        excludeFilenames: normalizedExcludeFilenames,
      },
    );
  return messages.at(-1) ?? null;
}

async function pasteText(page, text) {
  await page
    .evaluate((value) => navigator.clipboard.writeText(value), text)
    .then(() =>
      page.keyboard.press(process.platform === "darwin" ? "Meta+V" : "Control+V"),
    )
    .catch(() => page.keyboard.insertText(text));
}

function parseSlashCommand(command) {
  const match = command.match(/^(\/\S+)\s+prompt\s*:(.*)$/is);
  if (!match) {
    throw new Error(
      "Commands must use '/command prompt:<text> [named options]' format",
    );
  }

  const slashName = match[1];
  const body = match[2];
  const optionPattern =
    /\s+(resolution|duration|seed|aspect_ratio|input_media(?:_(?:[2-9]|10))?):([^\s]+)/gi;
  const matches = [...body.matchAll(optionPattern)];
  const promptEnd = matches[0]?.index ?? body.length;
  const prompt = body.slice(0, promptEnd).trim();
  const options = matches.map((option) => ({
    key: option[1].toLowerCase(),
    value: option[2],
  }));
  if (!prompt) {
    throw new Error("The prompt option cannot be empty");
  }
  return { slashName, prompt, options };
}

function isAttachmentOption(option) {
  return /^input_media(?:_(?:[2-9]|10))?$/.test(option.key);
}

function attachmentPath(option) {
  const rawPath = option.value.startsWith("@")
    ? option.value.slice(1)
    : option.value;
  return path.resolve(rawPath);
}

function inputAttachmentFilenames(parsedCommand) {
  return parsedCommand.options
    .filter(isAttachmentOption)
    .map((option) => path.basename(attachmentPath(option)));
}

async function slashOptionState(page) {
  const editor = await visibleComposer(page, 10_000);
  return editor.evaluate((editor) =>
    [...editor.querySelectorAll("[data-slate-inline=true]")].map((option) => ({
      key:
        option
          .querySelector("[contenteditable=false]")
          ?.textContent?.replace(/\u200b/g, "")
          .trim()
          .toLowerCase() ?? "",
      value:
        option
          .querySelector('[class*="optionPillValue"]')
          ?.textContent?.replace(/[\u200b\ufeff]/g, "")
          .trim() ?? "",
      invalid: option.className.includes("erroredPill"),
    })),
  );
}

async function assertSlashForm(page, parsed) {
  const state = await slashOptionState(page);
  const values = new Map(state.map((option) => [option.key, option.value]));
  const expected = [
    { key: "prompt", value: parsed.prompt },
    ...parsed.options.map((option) => ({
      key: option.key,
      value: isAttachmentOption(option)
        ? path.basename(attachmentPath(option))
        : option.value,
    })),
  ];
  const mismatches = expected.filter(
    (option) => values.get(option.key) !== option.value,
  );
  const invalid = state.filter((option) => option.invalid);
  if (mismatches.length > 0 || invalid.length > 0) {
    throw new Error(
      `Discord option fields were not populated correctly: ${JSON.stringify({
        expected,
        actual: state,
      })}`,
    );
  }
}

async function moveComposerCaretToEnd(page) {
  const activeComposer = await visibleComposer(page, 10_000);
  await activeComposer.evaluate((editor) => {
    editor.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    selection?.removeAllRanges();
    selection?.addRange(range);
  });
  await page.keyboard.press("ArrowRight").catch(() => {});
}

async function fillAttachmentOption(page, option) {
  const filePath = attachmentPath(option);
  const fileInfo = await stat(filePath).catch(() => null);
  if (!fileInfo?.isFile()) {
    throw new Error(
      `Attachment for ${option.key} is not a readable file: ${filePath}`,
    );
  }

  await moveComposerCaretToEnd(page);
  await page.keyboard.insertText(" ");
  await pasteText(page, `${option.key}:`);
  await page.waitForTimeout(700);

  const expectedFilename = path.basename(filePath);
  const currentState = new Map(
    (await slashOptionState(page)).map((item) => [item.key, item.value]),
  );
  if (currentState.get(option.key) === expectedFilename) {
    return;
  }

  const attachmentDeadline = Date.now() + 10_000;
  let attached = false;
  while (Date.now() < attachmentDeadline && !attached) {
    const uploadChoice = page
      .locator('[role="option"], [role="menuitem"]')
      .filter({ hasText: /upload (?:a )?file|choose (?:a )?file/i })
      .first();
    if (await uploadChoice.isVisible().catch(() => false)) {
      const chooserPromise = page.waitForEvent("filechooser", {
        timeout: 10_000,
      });
      await humanClick(page, uploadChoice);
      const chooser = await chooserPromise;
      await chooser.setFiles(filePath);
      attached = true;
      break;
    }

    const fileInput = page.locator('input[type="file"]').last();
    if ((await fileInput.count()) > 0) {
      await fileInput.setInputFiles(filePath);
      attached = true;
      break;
    }
    await page.waitForTimeout(500);
  }
  if (!attached) {
    throw new Error(
      `Discord did not expose an attachment picker for ${option.key} within 10s`,
    );
  }
  await page.waitForTimeout(1200);
}

async function fillSlashCommand(page, composer, command) {
  await humanClick(page, composer);
  await composer.press("Escape").catch(() => {});
  await composer.press("ControlOrMeta+A").catch(() => {});
  await composer.press("Backspace").catch(() => {});

  const parsed = parseSlashCommand(command);

  await page.keyboard.insertText(parsed.slashName);
  await page.waitForTimeout(1500);

  const commandOption = page
    .locator('[role="option"], [role="menuitem"]')
    .filter({ hasText: parsed.slashName })
    .first();
  if (!(await commandOption.isVisible().catch(() => false))) {
    throw new Error(`Discord did not offer the ${parsed.slashName} command`);
  }
  await humanClick(page, commandOption);
  await page.waitForTimeout(500);

  const promptPill = page
    .locator("[data-slate-inline=true]")
    .filter({ hasText: "prompt" })
    .first();
  await humanClick(page, promptPill);
  await pasteText(page, parsed.prompt);

  for (const option of parsed.options) {
    if (isAttachmentOption(option)) {
      await fillAttachmentOption(page, option);
      continue;
    }

    await moveComposerCaretToEnd(page);
    await page.keyboard.insertText(" ");
    await pasteText(page, `${option.key}:${option.value}`);
    await page.waitForTimeout(600);

    if (
      option.key === "resolution" ||
      option.key === "duration" ||
      option.key === "aspect_ratio"
    ) {
      const escaped = option.value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const choice = page
        .locator('[role="option"], [role="menuitem"]')
        .filter({ hasText: new RegExp(`^\\s*${escaped}\\s*$`, "i") })
        .first();
      if (!(await choice.isVisible().catch(() => false))) {
        throw new Error(
          `Discord did not offer ${option.value} for ${option.key}`,
        );
      }
      await humanClick(page, choice);
      await page.waitForTimeout(400);
    }
  }

  await page.waitForTimeout(500);
  await assertSlashForm(page, parsed);
}

async function assertSubmissionAccepted(page, command) {
  const validationError = page
    .getByText(/This option is required|Specify a value|Not a valid choice/i)
    .first();
  if (await validationError.isVisible().catch(() => false)) {
    throw new Error(
      `Discord rejected the slash command: ${await validationError.textContent()}`,
    );
  }

  const composer = await visibleComposer(page, 10_000);
  const composerText = (await composer.textContent().catch(() => "")) ?? "";
  const correlationText = correlationTextForCommand(command).slice(0, 40);
  if (
    correlationText &&
    composerText.toLowerCase().includes(correlationText.toLowerCase())
  ) {
    throw new Error(
      "Discord kept the command in the composer instead of submitting it",
    );
  }
}

async function downloadAttachment(rawUrl, outputDir, index) {
  const response = await fetch(rawUrl, { redirect: "follow" });
  if (!response.ok || !response.body) {
    throw new Error(
      `Attachment download failed with HTTP ${response.status}: ${rawUrl}`,
    );
  }

  const contentLength = Number(response.headers.get("content-length") ?? "0");
  const maximumBytes = 500 * 1024 * 1024;
  if (contentLength > maximumBytes) {
    throw new Error(
      `Attachment is larger than the 500 MiB safety limit: ${contentLength} bytes`,
    );
  }

  const filename = `${String(index).padStart(2, "0")}-${attachmentName(rawUrl, index)}`;
  const finalPath = path.join(outputDir, filename);
  const temporaryPath = `${finalPath}.partial`;
  await rm(temporaryPath, { force: true });
  let downloadedBytes = 0;
  const byteLimit = new Transform({
    transform(chunk, _encoding, callback) {
      downloadedBytes += chunk.length;
      if (downloadedBytes > maximumBytes) {
        callback(new Error("Attachment exceeded the 500 MiB streaming safety limit"));
        return;
      }
      callback(null, chunk);
    },
  });
  try {
    await pipeline(
      Readable.fromWeb(response.body),
      byteLimit,
      createWriteStream(temporaryPath),
    );
    await rename(temporaryPath, finalPath);
  } catch (error) {
    await rm(temporaryPath, { force: true });
    throw error;
  }
  return {
    path: finalPath,
    sourceUrlPresent: true,
    contentType: response.headers.get("content-type"),
    contentLength: contentLength || downloadedBytes,
  };
}

function snowflakeBeforeOrAt(timestamp) {
  const discordEpoch = 1420070400000n;
  const milliseconds = BigInt(Date.parse(timestamp));
  return ((milliseconds - discordEpoch) << 22n).toString();
}

function correlationTextForCommand(command) {
  const promptStart = command.toLowerCase().indexOf("prompt:");
  const source =
    promptStart >= 0 ? command.slice(promptStart + "prompt:".length) : command;
  const normalized = source.replace(/\s+/g, " ").trim();
  const firstSentence = normalized.split(/[.!?]/, 1)[0]?.trim();
  const candidate =
    firstSentence && firstSentence.length >= 16
      ? firstSentence
      : normalized.slice(0, 80).trim();
  return candidate.slice(0, 120);
}

async function fetchCompletedAttachment(page, options) {
  const runDir = path.join(options.outputDir, timestampSlug());
  await mkdir(runDir, { recursive: true });
  const afterMessageId = options.after ? snowflakeBeforeOrAt(options.after) : "0";
  const timeoutMs = options.timeoutSeconds * 1000;
  const deadline = Date.now() + timeoutMs;
  let responseMessage = null;

  console.log(
    `Looking for a completed attachment${options.match ? ` matching "${options.match}"` : ""}.`,
  );
  while (Date.now() < deadline) {
    responseMessage = await newAttachmentMessage(
      page,
      afterMessageId,
      options.expectedAuthor,
      options.match,
      options.linkMatch,
      options.excludeFilenames,
    );
    if (responseMessage) {
      break;
    }
    await humanWait(page);
  }

  if (!responseMessage) {
    await page.screenshot({
      path: path.join(runDir, "fetch-timeout.png"),
      fullPage: false,
    });
    throw new Error(
      `No matching completed attachment appeared within ${options.timeoutSeconds}s`,
    );
  }

  const downloads = [];
  for (let index = 0; index < responseMessage.links.length; index += 1) {
    downloads.push(
      await downloadAttachment(responseMessage.links[index], runDir, index + 1),
    );
  }
  const result = {
    channelUrl: options.channelUrl,
    fetchedAt: new Date().toISOString(),
    after: options.after,
    match: options.match,
    linkMatch: options.linkMatch,
    excludeFilenames: options.excludeFilenames,
    expectedAuthor: options.expectedAuthor,
    responseMessageId: responseMessage.messageId,
    responsePreview: responseMessage.text,
    downloads,
  };
  await writeFile(
    path.join(runDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  console.log(`Fetched ${downloads.length} attachment(s) to ${runDir}`);
}

async function runGeneration(page, context, options, command, settleBounds) {
  const runDir = path.join(options.outputDir, timestampSlug());
  await mkdir(runDir, { recursive: true });
  const timeoutMs = options.timeoutSeconds * 1000;
  const parsedCommand = parseSlashCommand(command);
  const hasInputAttachments = parsedCommand.options.some(isAttachmentOption);
  const excludeFilenames = [
    ...new Set([
      ...options.excludeFilenames,
      ...inputAttachmentFilenames(parsedCommand),
    ]),
  ];
  const responseMatch = options.match ?? correlationTextForCommand(command);
  const linkMatch =
    options.linkMatch ?? (hasInputAttachments ? ".mp4" : null);

  if (!page.url().startsWith(options.channelUrl)) {
    console.log(`Navigating to ${options.channelUrl}`);
    await page.goto(options.channelUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });
    console.log(
      "If Discord asks you to sign in, complete that in the opened Chrome window.",
    );
  }

  if (settleBounds && !options.noSettle) {
    console.log("Looking the channel over before typing…");
    await humanSettle(page, settleBounds[0], settleBounds[1]);
  }

  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: "https://discord.com",
  });
  const composer = await visibleComposer(page, timeoutMs);
  await fillSlashCommand(page, composer, command);
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(runDir, "before-submit.png"),
    fullPage: false,
  });

  if (!options.submit) {
    console.log(
      "Command filled but not submitted. Re-run with --submit to press Enter once.",
    );
    console.log(`Preview: ${path.join(runDir, "before-submit.png")}`);
    return;
  }

  console.log("Submitting command once.");
  const activeComposer = await visibleComposer(page, 10_000);
  const baselineMessageId = snowflakeBeforeOrAt(new Date().toISOString());
  await activeComposer.press("Enter");
  const submittedAt = new Date().toISOString();
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(runDir, "after-submit.png"),
    fullPage: false,
  });
  await assertSubmissionAccepted(page, command);

  if (options.noWatch) {
    const queued = {
      submittedAt,
      after: new Date(Number(BigInt(baselineMessageId) >> 22n) + 1420070400000).toISOString(),
      match: responseMatch,
      linkMatch,
      excludeFilenames,
      expectedAuthor: options.expectedAuthor,
      responseMessageId: null,
      responsePreview: null,
      downloads: [],
      queuedOnly: true,
    };
    await writeFile(
      path.join(runDir, "result.json"),
      `${JSON.stringify(queued, null, 2)}\n`,
      "utf8",
    );
    console.log("Command submitted once; watcher intentionally deferred.");
    return;
  }

  console.log(
    `Waiting up to ${options.timeoutSeconds}s for a new Discord attachment matching "${responseMatch}"${linkMatch ? ` with a link matching "${linkMatch}"` : ""}.`,
  );
  const deadline = Date.now() + timeoutMs;
  let responseMessage = null;
  while (Date.now() < deadline) {
    responseMessage = await newAttachmentMessage(
      page,
      baselineMessageId,
      options.expectedAuthor,
      responseMatch,
      linkMatch,
      excludeFilenames,
    );
    if (responseMessage) {
      break;
    }
    await humanWait(page);
  }

  if (!responseMessage) {
    await page.screenshot({
      path: path.join(runDir, "timeout.png"),
      fullPage: false,
    });
    throw new Error(
      `No new attachment appeared within ${options.timeoutSeconds}s`,
    );
  }

  const downloads = [];
  for (let index = 0; index < responseMessage.links.length; index += 1) {
    downloads.push(
      await downloadAttachment(responseMessage.links[index], runDir, index + 1),
    );
  }

  const result = {
    channelUrl: options.channelUrl,
    submittedAt,
    completedAt: new Date().toISOString(),
    expectedAuthor: options.expectedAuthor,
    match: responseMatch,
    linkMatch,
    excludeFilenames,
    responseMessageId: responseMessage.messageId,
    responsePreview: responseMessage.text,
    downloads,
  };
  await writeFile(
    path.join(runDir, "result.json"),
    `${JSON.stringify(result, null, 2)}\n`,
    "utf8",
  );
  console.log(`Downloaded ${downloads.length} attachment(s) to ${runDir}`);
}

async function commandFromInteractiveInput(value) {
  const trimmed = value.trim();
  if (trimmed.startsWith(":file ")) {
    const filePath = trimmed.slice(":file ".length).trim();
    return (await readFile(path.resolve(filePath), "utf8")).trim();
  }
  return trimmed;
}

async function cdpAvailable(endpoint) {
  try {
    const response = await fetch(`${endpoint}/json/version`);
    return response.ok;
  } catch {
    return false;
  }
}

async function ensureDurableChrome(profileDir, cdpPort) {
  const endpoint = `http://127.0.0.1:${cdpPort}`;
  if (await cdpAvailable(endpoint)) {
    return { endpoint, started: false };
  }

  const candidates =
    process.platform === "darwin"
      ? ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
      : process.platform === "win32"
        ? [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
          ]
        : ["google-chrome", "google-chrome-stable"];

  let launchError = null;
  for (const executable of candidates) {
    try {
      const child = spawn(
        executable,
        [
          `--remote-debugging-port=${cdpPort}`,
          "--remote-debugging-address=127.0.0.1",
          `--user-data-dir=${profileDir}`,
          "--no-first-run",
          "--no-default-browser-check",
          "about:blank",
        ],
        { detached: true, stdio: "ignore" },
      );
      child.unref();
      launchError = null;
      break;
    } catch (error) {
      launchError = error;
    }
  }
  if (launchError) {
    throw new Error(`Could not launch Google Chrome: ${launchError.message}`);
  }

  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    if (await cdpAvailable(endpoint)) {
      return { endpoint, started: true };
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Chrome did not expose its local controller at ${endpoint}`);
}

async function disconnectController(browser) {
  const connection = browser?._connection;
  if (connection && typeof connection.close === "function") {
    await Promise.race([
      Promise.resolve(connection.close()),
      new Promise((resolve) => setTimeout(resolve, 2_000)),
    ]);
  }
}

async function run() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
    validateOptions(options);
  } catch (error) {
    console.error(`Error: ${error.message}\n\n${usage()}`);
    process.exitCode = 2;
    return;
  }

  if (options.help) {
    console.log(usage());
    return;
  }

  const command =
    options.idle || options.fetchOnly ? null : await loadCommand(options);
  await mkdir(options.profileDir, { recursive: true });

  const durableChrome = await ensureDurableChrome(
    options.profileDir,
    options.cdpPort,
  );
  console.log(
    `${durableChrome.started ? "Opened" : "Reusing"} durable Chrome profile: ${options.profileDir}`,
  );
  const browser = await chromium.connectOverCDP(durableChrome.endpoint);
  const context = browser.contexts()[0];
  if (!context) {
    throw new Error("Durable Chrome did not expose a browser context");
  }
  const page = context.pages()[0] ?? (await context.newPage());
  let closing = false;
  const close = async () => {
    if (closing) {
      return;
    }
    closing = true;
    await disconnectController(browser).catch(() => {});
  };
  process.once("SIGINT", () => {
    void close().finally(() => process.exit(130));
  });
  process.once("SIGTERM", () => {
    void close().finally(() => process.exit(143));
  });

  try {
    if (options.idle || options.fetchOnly) {
      const targetUrl =
        options.fetchOnly && options.messageId
          ? `${options.channelUrl.replace(/\/$/, "")}/${options.messageId}`
          : options.channelUrl;
      console.log(`Navigating to ${targetUrl}`);
      await page.goto(targetUrl, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });
      console.log(
        "If Discord asks you to sign in, complete that in the opened Chrome window.",
      );
      if (!options.noSettle) {
        console.log("Looking the channel over…");
        await humanSettle(page, SETTLE_MIN_MS, SETTLE_MAX_MS);
      }
      await visibleComposer(page, options.timeoutSeconds * 1000);
      if (options.fetchOnly) {
        await fetchCompletedAttachment(page, options);
      } else {
        console.log("Discord is ready; no command was submitted.");
      }
    } else {
      await runGeneration(page, context, options, command, [
        SETTLE_MIN_MS,
        SETTLE_MAX_MS,
      ]);
    }
    if (!options.keepOpen) {
      return;
    }

    const input = createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: true,
    });
    try {
      while (true) {
        const value = await input.question(
          "\nBrowser remains open. Paste the next command, use :file <path>, or :quit.\nnext> ",
        );
        if (value.trim() === ":quit") {
          break;
        }
        const nextCommand = await commandFromInteractiveInput(value);
        if (!nextCommand) {
          continue;
        }
        if (!nextCommand.startsWith("/")) {
          console.error("Commands must start with /");
          continue;
        }
        try {
          await runGeneration(page, context, options, nextCommand, [
            GAP_MIN_MS,
            GAP_MAX_MS,
          ]);
        } catch (error) {
          console.error(`Generation failed: ${error.stack ?? error.message}`);
        }
      }
    } finally {
      input.close();
    }
  } finally {
    await close();
  }
}

if (path.resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) {
  run().then(
    () => setImmediate(() => process.exit(0)),
    (error) => {
      console.error(`Fatal: ${error.stack ?? error.message}`);
      setImmediate(() => process.exit(1));
    },
  );
}

export {
  inputAttachmentFilenames,
  newAttachmentMessage,
  parseArgs,
  parseSlashCommand,
  validateOptions,
};
