import { test } from "node:test";
import assert from "node:assert/strict";
import { TimelineConfig } from "../src/generated.js";
import { deepMergeTheme, mergeGeneration, resolveTheme } from "../src/resolveTheme.js";

test("deepMergeTheme merges nested visual.canvas key-by-key", () => {
  const base = { visual: { canvas: { width: 1920, height: 1080, fps: 30 } } };
  const overlay = { visual: { canvas: { fps: 60 } } };
  const out = deepMergeTheme(base, overlay) as any;
  assert.equal(out.visual.canvas.width, 1920);
  assert.equal(out.visual.canvas.fps, 60);
});

test("deepMergeTheme replaces lists wholesale", () => {
  const base = { generation: { references: [{ id: "a" }] } };
  const overlay = { generation: { references: [{ id: "b" }] } };
  const out = deepMergeTheme(base, overlay) as any;
  assert.deepEqual(out.generation.references, [{ id: "b" }]);
});

test("mergeGeneration: per-clip wins on conflict", () => {
  const out = mergeGeneration({ image_model: "a", aspect: "16:9" }, { image_model: "b" });
  assert.equal(out.image_model, "b");
  assert.equal(out.aspect, "16:9");
});

test("resolveTheme returns base when no overrides", () => {
  const registry = { "2rp": { id: "2rp", visual: { canvas: { fps: 30 } } } };
  const out = resolveTheme({ theme: "2rp" }, registry) as any;
  assert.equal(out.visual.canvas.fps, 30);
});

test("resolveTheme deep-merges overrides", () => {
  const registry = { "2rp": { id: "2rp", visual: { canvas: { width: 1920, fps: 30 } } } };
  const out = resolveTheme(
    { theme: "2rp", theme_overrides: { visual: { canvas: { fps: 60 } } } },
    registry,
  ) as any;
  assert.equal(out.visual.canvas.width, 1920);
  assert.equal(out.visual.canvas.fps, 60);
});

test("resolveTheme throws when theme missing", () => {
  assert.throws(() => resolveTheme({ theme: "missing" }, {}));
});

test("TimelineConfig type accepts persisted no-theme timelines", () => {
  const out: TimelineConfig = { clips: [] };
  assert.deepEqual(out, { clips: [] });
});

// Runtime validation of the document shape lives in the Python jsonschema
// validator (see test_validate.py). In TypeScript, TimelineConfig is a type
// derived from the canonical JSON Schema — this is a compile-time shape check
// that open generation_defaults objects are permitted.
test("TimelineConfig type permits open generation_defaults objects", () => {
  const payload: TimelineConfig = {
    theme: "2rp",
    clips: [],
    generation_defaults: {
      model: "sequence-v1",
      image: { quality: "high", provider: "reigh" },
      provider_settings: { seed: 1234, flags: ["keep", "open"] },
    },
  };
  assert.deepEqual(payload.generation_defaults, payload.generation_defaults);
});

test("resolveTheme throws when theme is absent or empty", () => {
  assert.throws(
    () => resolveTheme({} as any, {}),
    /Timeline\.theme must be a non-empty slug/,
  );
  assert.throws(
    () => resolveTheme({ theme: "" }, {}),
    /Timeline\.theme must be a non-empty slug/,
  );
});
