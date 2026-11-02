import test from "node:test";
import assert from "node:assert/strict";
import {
  buildComparisonChartData,
  comparisonCanCalculate,
  formatComparisonValue
} from "../src/comparison.js";

test("keeps missing values unavailable while preserving known zero", () => {
  assert.equal(formatComparisonValue(null), "Unavailable");
  assert.equal(formatComparisonValue(0), "0");
  assert.deepEqual(buildComparisonChartData([
    { player_name: "Known", batting: { runs: 0 } },
    { player_name: "Unknown", batting: { runs: null } }
  ], "batting", "runs"), [
    { name: "Known", value: 0 },
    { name: "Unknown", value: null }
  ]);
});

test("requires an explicit role before scoring a comparison player", () => {
  assert.equal(comparisonCanCalculate(null, "batter"), false);
  assert.equal(comparisonCanCalculate({ player_id: "1" }, null), false);
  assert.equal(comparisonCanCalculate({ player_id: "1" }, "batter"), true);
});
