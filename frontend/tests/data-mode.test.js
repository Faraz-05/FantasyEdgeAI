import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");

test("data mode defaults to live and persists valid selections", () => {
  assert.match(appSource, /const DATA_MODE_STORAGE_KEY = "fantasyedge-cricket-data-mode"/);
  assert.match(appSource, /return Object\.values\(DATA_MODES\)\.includes\(stored\) \? stored : DATA_MODES\.LIVE/);
  assert.match(appSource, /useState\(loadDataMode\)/);
  assert.match(appSource, /localStorage\.setItem\(DATA_MODE_STORAGE_KEY, mode\)/);
});

test("all frontend cricket reads propagate the selected mode", () => {
  assert.match(appSource, /cricketGet\("\/matches\/live", requestMode\)/);
  assert.match(appSource, /cricketGet\("\/matches\/recent", requestMode\)/);
  assert.match(appSource, /cricketGet\(`\/matches\/\$\{match\.id\}\/players`, dataMode\)/);
  assert.match(appSource, /cricketGet\(`\/matches\/\$\{match\.id\}\/momentum`, dataMode\)/);
  assert.match(appSource, /return api\.get\(path, \{ params: \{ mode \} \}\)/);
});

test("switching modes resets match state and guards stale responses", () => {
  assert.match(appSource, /requestGeneration\.current \+= 1/);
  assert.match(appSource, /resetMatchState\(\)/);
  assert.match(appSource, /if \(generation !== requestGeneration\.current\) return/);
  assert.match(appSource, /setSelectedMatch\(null\)/);
  assert.match(appSource, /setComparisonPlayers\(\[null, null\]\)/);
  assert.match(appSource, /setMomentumData\(null\)/);
});

test("quota exhaustion offers demo mode without automatic fallback", () => {
  assert.match(appSource, /CRICKET_QUOTA_EXHAUSTED/);
  assert.match(appSource, /Cricket Data API quota exhausted/);
  assert.match(appSource, /Switch to Demo Mode/);
  assert.match(appSource, /onClick=\{onUseDemo\}/);
  assert.match(appSource, /onUseDemo=\{\(\) => changeDataMode\(DATA_MODES\.DEMO\)\}/);
});
