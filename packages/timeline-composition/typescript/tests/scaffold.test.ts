import { test } from "node:test";
import assert from "node:assert/strict";
import { TIMELINE_COMPOSITION_SCAFFOLD } from "../src/index.js";

test("scaffold exports its sprint tag", () => {
  assert.equal(TIMELINE_COMPOSITION_SCAFFOLD, "sprint-4");
});
