import test from "node:test";
import assert from "node:assert/strict";
import { buildTeamSummary, validateTeamSelection } from "../src/teamBuilder.js";

test("rejects more than eleven selected players", () => {
  const ids = Array.from({ length: 12 }, (_, index) => String(index));
  assert.match(validateTeamSelection(ids, "0", "1")[0], /at most 11/);
});

test("requires distinct captain and vice-captain from the XI", () => {
  assert.deepEqual(validateTeamSelection(["a", "b"], "a", "a"), [
    "Captain and vice-captain must be different players."
  ]);
  assert.match(validateTeamSelection(["a"], "a", "b")[0], /vice-captain/);
});

test("marks a team incomplete when any player score is incomplete", () => {
  const summary = buildTeamSummary([
    { complete: true, total_points: 10 },
    { complete: false, total_points: 5 }
  ]);
  assert.equal(summary.complete, false);
  assert.equal(summary.incompletePlayers, 1);
});

test("preserves captain and vice-captain multipliers in score results", () => {
  const results = [
    { complete: true, subtotal: 10, multiplier: 2, total_points: 20 },
    { complete: true, subtotal: 10, multiplier: 1.5, total_points: 15 }
  ];
  assert.equal(results[0].total_points, results[0].subtotal * results[0].multiplier);
  assert.equal(results[1].total_points, results[1].subtotal * results[1].multiplier);
});
