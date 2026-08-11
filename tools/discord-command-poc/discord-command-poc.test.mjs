import assert from "node:assert/strict";
import test from "node:test";

import {
  inputAttachmentFilenames,
  newAttachmentMessage,
  parseArgs,
  parseSlashCommand,
} from "./discord-command-poc.mjs";

function fakeMessage(id, text, links) {
  return {
    id: `chat-messages-${id}`,
    textContent: text,
    querySelectorAll: () => links.map((href) => ({ href })),
  };
}

function fakePage(messages) {
  return {
    locator: () => ({
      evaluateAll: (callback, filter) => callback(messages, filter),
    }),
  };
}

test("repeatable --exclude-filename values are retained", () => {
  const options = parseArgs([
    "--exclude-filename",
    "source-one.mp4",
    "--exclude-filename",
    "source-two.png",
  ]);
  assert.deepEqual(options.excludeFilenames, [
    "source-one.mp4",
    "source-two.png",
  ]);
});

test("input attachment basenames are derived from slash-command options", () => {
  const parsed = parseSlashCommand(
    "/gen prompt:Grow left input_media:@/tmp/Source.MP4 input_media_2:./grid.png seed:7",
  );
  assert.deepEqual(inputAttachmentFilenames(parsed), ["Source.MP4", "grid.png"]);
});

test("source input links are excluded before response matching", async () => {
  const sourceUrl =
    "https://cdn.discordapp.com/attachments/1/2/Desert%20Motion.MP4?token=x";
  const outputUrl =
    "https://cdn.discordapp.com/attachments/1/3/generated-result.mp4?token=y";
  const page = fakePage([
    fakeMessage("101", "seed 35635343 submitted", [sourceUrl]),
    fakeMessage("102", "seed 35635343 completed", [outputUrl]),
  ]);

  const result = await newAttachmentMessage(
    page,
    "100",
    null,
    "35635343",
    ".mp4",
    ["desert motion.mp4"],
  );

  assert.equal(result.messageId, "102");
  assert.deepEqual(result.links, [outputUrl]);
});

test("a message containing only an excluded input is not a match", async () => {
  const sourceUrl =
    "https://media.discordapp.net/attachments/1/2/source-video.mp4?token=x";
  const page = fakePage([
    fakeMessage("101", "seed 35635343 submitted", [sourceUrl]),
  ]);

  const result = await newAttachmentMessage(
    page,
    "100",
    null,
    "35635343",
    ".mp4",
    ["SOURCE-VIDEO.MP4"],
  );

  assert.equal(result, null);
});
