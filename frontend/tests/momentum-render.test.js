import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");

test("momentum tab mounts the scorecard dashboard", () => {
  assert.match(appSource, /activeTab === "momentum" && <MatchMomentum/);
  assert.match(appSource, /data-testid="match-momentum-panel"/);
  assert.match(appSource, /<h1[^>]*>Match Momentum\.<\/h1>/);
});

test("momentum dashboard exposes unsupported timeline states", () => {
  assert.match(appSource, /Ball-by-ball progression/);
  assert.match(appSource, /Partnerships/);
  assert.match(appSource, /Fall-of-wicket timeline/);
  assert.match(appSource, /Scorecard momentum/);
});
