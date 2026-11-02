export const COMPARISON_STAT_GROUPS = [
  {
    key: "batting",
    label: "Batting",
    fields: [
      ["runs", "Runs", ""],
      ["balls_faced", "Balls faced", ""],
      ["strike_rate", "Strike rate", ""],
      ["fours", "Fours", ""],
      ["sixes", "Sixes", ""]
    ]
  },
  {
    key: "bowling",
    label: "Bowling",
    fields: [
      ["overs_bowled", "Overs", " ov"],
      ["maiden_overs", "Maidens", ""],
      ["runs_conceded", "Runs conceded", ""],
      ["wickets", "Wickets", ""],
      ["economy", "Economy", ""]
    ]
  },
  {
    key: "fielding",
    label: "Fielding",
    fields: [
      ["catches", "Catches", ""],
      ["stumpings", "Stumpings", ""],
      ["runouts", "Run-outs", ""],
      ["direct_hit_run_outs", "Direct-hit run-outs", ""],
      ["other_run_outs", "Other run-outs", ""]
    ]
  }
];

export function comparisonValue(player, group, field) {
  return player?.[group]?.[field] ?? null;
}

export function formatComparisonValue(value, suffix = "") {
  if (value === null || value === undefined) return "Unavailable";
  if (typeof value === "number") {
    return `${Number.isInteger(value) ? value : value.toFixed(2)}${suffix}`;
  }
  return `${value}${suffix}`;
}

export function buildComparisonChartData(players, group, field) {
  return players.map((player) => ({
    name: player?.player_name?.trim() || "Player",
    value: comparisonValue(player, group, field)
  }));
}

export function comparisonCanCalculate(player, role) {
  return Boolean(player && role);
}
