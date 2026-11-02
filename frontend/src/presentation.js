export function formatRate(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "Unavailable";
  }
  return Number(Number(value).toFixed(2)).toString();
}

export function formatInningsLabel(score, index = 0) {
  const rawLabel = typeof score?.inning === "string" ? score.inning.trim() : "";
  const match = rawLabel.match(/^(.+?)\s+Inning\s+(\d+)$/i);
  const team = match?.[1]?.trim() || "Team unavailable";
  const inningsNumber = match?.[2] || String(index + 1);
  const runs = score?.r ?? "—";
  const wickets = score?.w ?? "—";
  const overs = score?.o ?? "—";
  return `${team} · Innings ${inningsNumber} · ${runs}/${wickets} (${overs} ov)`;
}

export function formatPlayerStat(field, value) {
  if (value === null || value === undefined) return "Unavailable";
  if (field === "economy" || field === "strike_rate" || field === "run_rate") {
    return formatRate(value);
  }
  return value;
}
