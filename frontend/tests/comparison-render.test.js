import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");

test("comparison navigation mounts the comparison panel", () => {
  assert.match(appSource, /data-testid=\{`nav-\$\{id\}`\}/);
  assert.match(appSource, /role="tablist"/);
  assert.match(appSource, /role="tab"/);
  assert.match(appSource, /activeTab === "comparison" && <PlayerComparison/);
  assert.match(appSource, /data-testid="player-comparison-panel"/);
  assert.match(appSource, /<h1[^>]*>Compare players\.<\/h1>/);
});

test("comparison panel has an initial empty state", () => {
  assert.match(appSource, /Select a match before comparing players\./);
  assert.match(appSource, /At least two players are needed for a comparison\./);
});

test("comparison panel renders selectors for two players", () => {
  assert.match(appSource, /\[0, 1\]\.map\(\(index\)/);
  assert.match(appSource, /Player \{index \+ 1\}/);
});

test("comparison selection handler is in App scope and rejects duplicate players", () => {
  assert.match(appSource, /function chooseComparisonPlayer\(index, playerId\)/);
  assert.match(appSource, /comparisonPlayers\[1 - index\]\?\.player_id === player\.player_id/);
  assert.match(appSource, /onSelect=\{chooseComparisonPlayer\}/);
});
