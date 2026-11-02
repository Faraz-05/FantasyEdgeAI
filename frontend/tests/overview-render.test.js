import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(new URL("../src/App.jsx", import.meta.url), "utf8");
const cssSource = await readFile(new URL("../src/index.css", import.meta.url), "utf8");

test("Overview uses the shared page header and scorecard presentation", () => {
  assert.match(appSource, /activeTab === "overview" && <OverviewDashboard/);
  assert.match(appSource, /<PageHeader[\s\S]*title="Cricket Overview"/);
  assert.match(appSource, /function OverviewScoreBlock/);
  assert.match(appSource, /formatRate\(score\?\.rr\)/);
});

test("Overview preserves verified metrics and contribution states", () => {
  assert.match(appSource, /<MetricCard label="Innings recorded"/);
  assert.match(appSource, /<MetricCard label="Result"/);
  assert.match(appSource, /No verified contribution data available/);
  assert.match(appSource, /Top batting/);
  assert.match(appSource, /Top bowling/);
});

test("Overview score layout remains responsive", () => {
  assert.match(cssSource, /\.overview-score-grid\s*\{[\s\S]*grid-template-columns: repeat\(2/);
  assert.match(cssSource, /\.overview-score-grid,\s*\.overview-metrics\s*\{[\s\S]*grid-template-columns: 1fr/);
  assert.match(cssSource, /\.overview-score-team\s*\{[\s\S]*text-overflow: ellipsis/);
});
