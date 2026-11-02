import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("My Fantasy Team uses shared header and composition primitives", () => {
  assert.match(appSource, /function TeamBuilder/);
  assert.match(appSource, /<PageHeader[\s\S]*title="My Fantasy Team"/);
  assert.match(appSource, /<MetricCard label="Players"/);
  assert.match(appSource, /Selected XI/);
  assert.match(appSource, /Captaincy multipliers/);
});

test("team builder preserves selection, leadership, and incomplete scoring states", () => {
  assert.match(appSource, /onTogglePlayer\(player\.player_id\)/);
  assert.match(appSource, /value=\{teamSelection\.captainId \|\| ""\}/);
  assert.match(appSource, /value=\{teamSelection\.viceCaptainId \|\| ""\}/);
  assert.match(appSource, /Unknown statistics:/);
  assert.match(appSource, /status=\{calculation\.complete \? "complete" : "incomplete"\}/);
});

test("team builder layout supports mobile player selection", () => {
  assert.match(cssSource, /\.team-layout\s*\{[\s\S]*grid-template-columns: minmax\(0, 1\.15fr\)/);
  assert.match(cssSource, /\.team-player-grid\s*\{[\s\S]*grid-template-columns: repeat\(2/);
  assert.match(cssSource, /\.team-player-grid,\s*\.team-leadership-grid\s*\{[\s\S]*grid-template-columns: 1fr/);
  assert.match(cssSource, /\.team-selected-card\s*\{[\s\S]*justify-content: space-between/);
});
