import test from "node:test";
import assert from "node:assert/strict";
import { formatInningsLabel, formatPlayerStat, formatRate } from "../src/presentation.js";

test("formats innings labels without concatenating team, innings, and score", () => {
  assert.equal(
    formatInningsLabel({ inning: "Durham Inning 1", r: 141, w: 7, o: 20 }, 0),
    "Durham · Innings 1 · 141/7 (20 ov)"
  );
});

test("formats calculated rates to two decimals without trailing zeros", () => {
  assert.equal(formatRate(7.891), "7.89");
  assert.equal(formatRate(7), "7");
  assert.equal(formatPlayerStat("economy", 5.5), "5.5");
  assert.equal(formatPlayerStat("run_rate", 6.0), "6");
});
