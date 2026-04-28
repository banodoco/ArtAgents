import { test } from "node:test";
import assert from "node:assert/strict";
import {
  addClip,
  moveClip,
  removeClip,
  setClipProperty,
  setClipTime,
  setTimelineProperty,
} from "../src/ops.js";
import type { TimelineConfigT, TimelineClipT } from "@banodoco/timeline-schema";

function makeClip(overrides: Partial<TimelineClipT> = {}): TimelineClipT {
  return {
    id: "clip-a",
    at: 0,
    track: "V1",
    clipType: "media",
    asset: "asset-a",
    from: 0,
    to: 5,
    ...overrides,
  } as TimelineClipT;
}

function makeTimeline(clips: TimelineClipT[] = []): TimelineConfigT {
  return {
    theme: "2rp",
    clips,
  } as TimelineConfigT;
}

test("addClip appends when position is omitted", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = addClip(tl, makeClip({ id: "b" }));
  assert.equal(result.changed, true);
  assert.deepEqual(result.config.clips.map((c) => c.id), ["a", "b"]);
});

test("addClip inserts at given position", () => {
  const tl = makeTimeline([makeClip({ id: "a" }), makeClip({ id: "c" })]);
  const result = addClip(tl, makeClip({ id: "b" }), 1);
  assert.deepEqual(result.config.clips.map((c) => c.id), ["a", "b", "c"]);
});

test("addClip clamps position out of range", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const high = addClip(tl, makeClip({ id: "b" }), 99);
  assert.deepEqual(high.config.clips.map((c) => c.id), ["a", "b"]);
  const low = addClip(tl, makeClip({ id: "z" }), -5);
  assert.deepEqual(low.config.clips.map((c) => c.id), ["z", "a"]);
});

test("addClip does not mutate the input timeline", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  addClip(tl, makeClip({ id: "b" }));
  assert.deepEqual(tl.clips.map((c) => c.id), ["a"]);
});

test("removeClip deletes the matching clip", () => {
  const tl = makeTimeline([makeClip({ id: "a" }), makeClip({ id: "b" })]);
  const result = removeClip(tl, "a");
  assert.equal(result.changed, true);
  assert.deepEqual(result.config.clips.map((c) => c.id), ["b"]);
});

test("removeClip is a no-op when clipId missing", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = removeClip(tl, "missing");
  assert.equal(result.changed, false);
  assert.deepEqual(result.config.clips.map((c) => c.id), ["a"]);
  assert.equal(result.detail?.reason, "not_found");
});

test("moveClip updates `at` and reports previous", () => {
  const tl = makeTimeline([makeClip({ id: "a", at: 1 })]);
  const result = moveClip(tl, "a", 5.5);
  assert.equal(result.changed, true);
  assert.equal(result.config.clips[0].at, 5.5);
  assert.equal(result.detail?.previousAt, 1);
});

test("moveClip rounds to ms precision", () => {
  const tl = makeTimeline([makeClip({ id: "a", at: 0 })]);
  const result = moveClip(tl, "a", 1.234567);
  assert.equal(result.config.clips[0].at, 1.235);
});

test("moveClip is a no-op for missing clip", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = moveClip(tl, "missing", 5);
  assert.equal(result.changed, false);
});

test("setClipProperty sets allowed numeric property", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipProperty(tl, "a", "opacity", 0.5);
  assert.equal(result.changed, true);
  assert.equal(result.config.clips[0].opacity, 0.5);
});

test("setClipProperty rejects disallowed property", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipProperty(tl, "a", "id", 1);
  assert.equal(result.changed, false);
  assert.equal(result.detail?.reason, "property_not_allowed");
});

test("setClipProperty rejects non-finite value", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipProperty(tl, "a", "opacity", Number.NaN);
  assert.equal(result.changed, false);
  assert.equal(result.detail?.reason, "invalid_value");
});

test("setClipProperty no-op when clipId missing", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipProperty(tl, "missing", "opacity", 0.5);
  assert.equal(result.changed, false);
});

test("setClipTime updates start time and asset duration via to", () => {
  const tl = makeTimeline([makeClip({ id: "a", at: 0, from: 0, to: 5 })]);
  const result = setClipTime(tl, "a", 2, 3);
  assert.equal(result.changed, true);
  const clip = result.config.clips[0];
  assert.equal(clip.at, 2);
  assert.equal(clip.from, 0);
  assert.equal(clip.to, 3);
});

test("setClipTime updates hold for hold-style clip", () => {
  const tl = makeTimeline([
    { id: "a", at: 0, track: "V1", clipType: "hold", hold: 2 } as unknown as TimelineClipT,
  ]);
  const result = setClipTime(tl, "a", 1, 4);
  const clip = result.config.clips[0] as unknown as { at: number; hold: number };
  assert.equal(clip.at, 1);
  assert.equal(clip.hold, 4);
});

test("setClipTime sets hold when clip has neither from/to nor hold", () => {
  const tl = makeTimeline([
    { id: "a", at: 0, track: "V1", clipType: "text" } as unknown as TimelineClipT,
  ]);
  const result = setClipTime(tl, "a", 0, 2);
  const clip = result.config.clips[0] as unknown as { hold: number };
  assert.equal(clip.hold, 2);
});

test("setClipTime rejects non-positive duration", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipTime(tl, "a", 0, 0);
  assert.equal(result.changed, false);
  assert.equal(result.detail?.reason, "invalid_duration");
});

test("setClipTime no-op when clipId missing", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setClipTime(tl, "missing", 0);
  assert.equal(result.changed, false);
});

test("setTimelineProperty sets theme slug", () => {
  const tl = makeTimeline();
  const result = setTimelineProperty(tl, "theme", "cinema-noir");
  assert.equal(result.changed, true);
  assert.equal(result.config.theme, "cinema-noir");
});

test("setTimelineProperty sets theme_overrides", () => {
  const tl = makeTimeline();
  const overrides = { visual: { canvas: { fps: 60 } } };
  const result = setTimelineProperty(tl, "theme_overrides", overrides);
  assert.equal(result.changed, true);
  assert.deepEqual(result.config.theme_overrides, overrides);
  // Ensure deep clone
  assert.notEqual(result.config.theme_overrides, overrides);
});

test("setTimelineProperty rejects unknown property", () => {
  const tl = makeTimeline();
  const result = setTimelineProperty(tl, "clips", []);
  assert.equal(result.changed, false);
  assert.equal(result.detail?.reason, "property_not_allowed");
});

test("setTimelineProperty rejects clip-list mutation via name", () => {
  const tl = makeTimeline([makeClip({ id: "a" })]);
  const result = setTimelineProperty(tl, "clips", []);
  assert.equal(result.changed, false);
  // Original clips preserved.
  assert.deepEqual(result.config.clips.map((c) => c.id), ["a"]);
});
