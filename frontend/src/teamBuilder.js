export const TEAM_STORAGE_KEY = "fantasyedge-manual-xi";

export function validateTeamSelection(selectedPlayerIds, captainId, viceCaptainId) {
  const errors = [];
  if (selectedPlayerIds.length > 11) errors.push("A manual fantasy XI can contain at most 11 players.");
  if (selectedPlayerIds.length === 0) errors.push("Select at least one player.");
  if (!captainId || !selectedPlayerIds.includes(captainId)) errors.push("Choose a captain from the selected XI.");
  if (!viceCaptainId || !selectedPlayerIds.includes(viceCaptainId)) errors.push("Choose a vice-captain from the selected XI.");
  if (captainId && captainId === viceCaptainId) errors.push("Captain and vice-captain must be different players.");
  return errors;
}

export function buildTeamSummary(results) {
  const incompletePlayers = results.filter((result) => !result.complete).length;
  return {
    results,
    incompletePlayers,
    complete: results.length > 0 && incompletePlayers === 0
  };
}

export function loadSavedTeam() {
  try {
    const saved = window.localStorage.getItem(TEAM_STORAGE_KEY);
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

export function saveTeam(team) {
  try {
    window.localStorage.setItem(TEAM_STORAGE_KEY, JSON.stringify(team));
  } catch {
    // Persistence is optional when browser storage is unavailable or full.
  }
}
