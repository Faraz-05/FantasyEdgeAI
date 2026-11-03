import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  Calculator,
  CircleHelp,
  Gauge,
  LoaderCircle,
  Radio,
  Search,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trophy,
  Users,
  X,
  BarChart3,
  LayoutDashboard
} from "lucide-react";
import { buildTeamSummary, loadSavedTeam, saveTeam, validateTeamSelection } from "./teamBuilder";
import { BarChart, Bar, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COMPARISON_STAT_GROUPS, buildComparisonChartData, comparisonCanCalculate } from "./comparison";
import { formatInningsLabel, formatPlayerStat, formatRate } from "./presentation";
import {
  EmptyState,
  ErrorState,
  LoadingState as Loading,
  MetricCard,
  PageHeader,
  Panel,
  StatusBadge
} from "./components/ui";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000
});
const ANALYSIS_REQUEST_TIMEOUT_MS = 90000;
const DATA_MODE_STORAGE_KEY = "fantasyedge-cricket-data-mode";
const DATA_MODES = {
  LIVE: "live",
  DEMO: "demo"
};

const EMPTY_FORM = {
  player_name: "Your player",
  role: "batter",
  runs: "",
  fours: "",
  sixes: "",
  balls_faced: "",
  dismissed: false,
  dot_balls: "",
  wickets: "",
  lbw_bowled_wickets: "",
  maiden_overs: "",
  overs_bowled: "",
  runs_conceded: "",
  catches: "",
  stumpings: "",
  direct_hit_run_outs: "",
  other_run_outs: "",
  announced_lineup: "",
  eligible_playing_substitute: "",
  multiplier: "1"
};

function App() {
  const [health, setHealth] = useState({ status: "checking", message: "" });
  const [matchTab, setMatchTab] = useState("live");
  const [matches, setMatches] = useState({ live: [], recent: [] });
  const [dataMode, setDataMode] = useState(loadDataMode);
  const [matchState, setMatchState] = useState("loading");
  const [matchError, setMatchError] = useState("");
  const [quotaError, setQuotaError] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [players, setPlayers] = useState([]);
  const [playerState, setPlayerState] = useState("idle");
  const [playerError, setPlayerError] = useState("");
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [calculation, setCalculation] = useState(null);
  const [calculatorState, setCalculatorState] = useState("idle");
  const [analysis, setAnalysis] = useState(null);
  const [analysisState, setAnalysisState] = useState("idle");
  const [analysisError, setAnalysisError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [teamSelection, setTeamSelection] = useState(() => loadSavedTeam() || {
    matchId: null,
    selectedPlayerIds: [],
    captainId: null,
    viceCaptainId: null,
    playerRoles: {}
  });
  const [teamSearch, setTeamSearch] = useState("");
  const [teamCalculation, setTeamCalculation] = useState(null);
  const [teamCalculationState, setTeamCalculationState] = useState("idle");
  const [teamError, setTeamError] = useState("");
  const [comparisonPlayers, setComparisonPlayers] = useState([null, null]);
  const [comparisonRoles, setComparisonRoles] = useState([null, null]);
  const [comparisonResults, setComparisonResults] = useState([null, null]);
  const [comparisonState, setComparisonState] = useState("idle");
  const [comparisonError, setComparisonError] = useState("");
  const [comparisonAnalysis, setComparisonAnalysis] = useState(null);
  const [comparisonAnalysisState, setComparisonAnalysisState] = useState("idle");
  const [comparisonAnalysisError, setComparisonAnalysisError] = useState("");
  const [momentumData, setMomentumData] = useState(null);
  const [momentumState, setMomentumState] = useState("idle");
  const [momentumError, setMomentumError] = useState("");
  const requestGeneration = useRef(0);

  useEffect(() => {
    api.get("/health")
      .then(({ data }) => setHealth({ status: "online", message: data.message }))
      .catch(() => setHealth({ status: "offline", message: "Backend unavailable. Start FastAPI on port 8000." }));
  }, []);

  useEffect(() => {
    loadMatches(dataMode);
  }, [dataMode]);

  useEffect(() => {
    if (matchState !== "done" || selectedMatch) return;
    const savedMatchId = teamSelection.matchId;
    const savedMatch = [...matches.live, ...matches.recent].find((match) => match.id === savedMatchId);
    if (savedMatch) selectMatch(savedMatch);
  }, [matchState, matches, selectedMatch, teamSelection.matchId]);

  useEffect(() => {
    saveTeam(teamSelection);
  }, [teamSelection]);

  function resetMatchState() {
    setMatches({ live: [], recent: [] });
    setMatchState("loading");
    setMatchError("");
    setQuotaError(false);
    setSelectedMatch(null);
    setPlayers([]);
    setPlayerState("idle");
    setPlayerError("");
    setSelectedPlayer(null);
    setForm(EMPTY_FORM);
    setCalculation(null);
    setCalculatorState("idle");
    setAnalysis(null);
    setAnalysisState("idle");
    setAnalysisError("");
    setTeamSelection({
      matchId: null,
      selectedPlayerIds: [],
      captainId: null,
      viceCaptainId: null,
      playerRoles: {}
    });
    setTeamCalculation(null);
    setTeamCalculationState("idle");
    setTeamError("");
    setComparisonPlayers([null, null]);
    setComparisonRoles([null, null]);
    setComparisonResults([null, null]);
    setComparisonState("idle");
    setComparisonError("");
    setComparisonAnalysis(null);
    setComparisonAnalysisState("idle");
    setComparisonAnalysisError("");
    setMomentumData(null);
    setMomentumState("idle");
    setMomentumError("");
  }

  function changeDataMode(nextMode) {
    if (!Object.values(DATA_MODES).includes(nextMode) || nextMode === dataMode) return;
    requestGeneration.current += 1;
    resetMatchState();
    saveDataMode(nextMode);
    setDataMode(nextMode);
  }

  async function loadMatches(requestMode = dataMode) {
    const generation = ++requestGeneration.current;
    setMatchState("loading");
    setMatchError("");
    setQuotaError(false);
    try {
      const [live, recent] = await Promise.all([
        cricketGet("/matches/live", requestMode),
        cricketGet("/matches/recent", requestMode)
      ]);
      if (generation !== requestGeneration.current) return;
      setMatches({ live: live.data.matches || [], recent: recent.data.matches || [] });
      setMatchState("done");
    } catch (error) {
      if (generation !== requestGeneration.current) return;
      setMatchError(readApiError(error, "Unable to load matches."));
      setQuotaError(getApiErrorCode(error) === "CRICKET_QUOTA_EXHAUSTED");
      setMatchState("error");
    }
  }

  async function selectMatch(match) {
    const generation = ++requestGeneration.current;
    const saved = loadSavedTeam();
    const sameSavedMatch = saved?.matchId === match.id;
    setSelectedMatch({ ...match, demo: dataMode === DATA_MODES.DEMO });
    setTeamSelection(sameSavedMatch ? saved : {
      matchId: match.id,
      selectedPlayerIds: [],
      captainId: null,
      viceCaptainId: null,
      playerRoles: {}
    });
    setTeamCalculation(null);
    setTeamError("");
    setSelectedPlayer(null);
    setComparisonPlayers([null, null]);
    setComparisonRoles([null, null]);
    setComparisonResults([null, null]);
    setComparisonAnalysis(null);
    setComparisonError("");
    setMomentumData(null);
    setMomentumState("loading");
    setMomentumError("");
    setPlayers([]);
    setPlayerState("loading");
    setPlayerError("");
    try {
      const [playersResponse, momentumResponse] = await Promise.all([
        cricketGet(`/matches/${match.id}/players`, dataMode),
        cricketGet(`/matches/${match.id}/momentum`, dataMode)
      ]);
      if (generation !== requestGeneration.current) return;
      setPlayers(playersResponse.data.players || []);
      setPlayerState("done");
      setMomentumData(momentumResponse.data);
      setMomentumState("done");
    } catch (error) {
      if (generation !== requestGeneration.current) return;
      const message = readApiError(error, "Unable to load match data.");
      setQuotaError(getApiErrorCode(error) === "CRICKET_QUOTA_EXHAUSTED");
      setPlayerError(message);
      setPlayerState("error");
      setMomentumError(message);
      setMomentumState("error");
    }

  }

  function chooseComparisonPlayer(index, playerId) {
    const player = players.find((candidate) => candidate.player_id === playerId) || null;
    if (player && comparisonPlayers[1 - index]?.player_id === player.player_id) {
      setComparisonError("Choose two different players to compare.");
      return;
    }
    setComparisonPlayers((current) => current.map((item, itemIndex) => itemIndex === index ? player : item));
    setComparisonRoles((current) => current.map((role, roleIndex) => roleIndex === index ? player?.role || null : role));
    setComparisonResults([null, null]);
    setComparisonAnalysis(null);
    setComparisonError("");
    setComparisonAnalysisError("");
  }

  function updateComparisonRole(index, role) {
    setComparisonRoles((current) => current.map((item, itemIndex) => itemIndex === index ? role || null : item));
    setComparisonResults([null, null]);
  }

  async function calculateComparison() {
    if (!comparisonPlayers[0] || !comparisonPlayers[1]) {
      setComparisonError("Select two different players from the selected match.");
      return;
    }
    if (comparisonPlayers[0].player_id === comparisonPlayers[1].player_id) {
      setComparisonError("Choose two different players to compare.");
      return;
    }
    if (!comparisonCanCalculate(comparisonPlayers[0], comparisonRoles[0]) || !comparisonCanCalculate(comparisonPlayers[1], comparisonRoles[1])) {
      setComparisonError("Choose an explicit role for both players before calculating fantasy points.");
      return;
    }
    setComparisonState("loading");
    setComparisonError("");
    try {
      const results = await Promise.all(comparisonPlayers.map((player, index) => api.post("/fantasy/calculate", {
        player_name: player.player_name.trim(),
        role: comparisonRoles[index],
        ...player.fantasy_inputs,
        multiplier: 1
      }).then(({ data }) => ({ ...data, player_id: player.player_id }))));
      setComparisonResults(results);
      setComparisonState("done");
    } catch (error) {
      setComparisonError(readApiError(error, "Unable to calculate comparison points."));
      setComparisonState("error");
    }
  }

  async function explainComparison() {
    if (!comparisonPlayers[0] || !comparisonPlayers[1] || !comparisonResults[0] || !comparisonResults[1]) return;
    setComparisonAnalysisState("loading");
    setComparisonAnalysisError("");
    try {
      const { data } = await api.post("/ai/analyze-comparison", {
        match_name: selectedMatch?.name || "Selected match",
        player_a: comparisonAnalysisPayload(comparisonPlayers[0], comparisonRoles[0], comparisonResults[0]),
        player_b: comparisonAnalysisPayload(comparisonPlayers[1], comparisonRoles[1], comparisonResults[1]),
        demo_fixture: selectedMatch?.demo === true
      }, { timeout: ANALYSIS_REQUEST_TIMEOUT_MS });
      setComparisonAnalysis(data);
      setComparisonAnalysisState("done");
    } catch (error) {
      setComparisonAnalysisError(readApiError(error, "Unable to explain this comparison."));
      setComparisonAnalysisState("error");
    }
  }

  function toggleTeamPlayer(playerId) {
    setTeamError("");
    setTeamCalculation(null);
    setTeamSelection((current) => {
      if (current.selectedPlayerIds.includes(playerId)) {
        return {
          ...current,
          selectedPlayerIds: current.selectedPlayerIds.filter((id) => id !== playerId),
          captainId: current.captainId === playerId ? null : current.captainId,
          viceCaptainId: current.viceCaptainId === playerId ? null : current.viceCaptainId
        };
      }
      if (current.selectedPlayerIds.length >= 11) {
        setTeamError("A manual fantasy XI can contain at most 11 players.");
        return current;
      }
      return { ...current, selectedPlayerIds: [...current.selectedPlayerIds, playerId] };
    });
  }

  async function calculateTeam() {
    const validationErrors = validateTeamSelection(
      teamSelection.selectedPlayerIds,
      teamSelection.captainId,
      teamSelection.viceCaptainId
    );
    if (validationErrors.length) {
      setTeamError(validationErrors.join(" "));
      setTeamCalculation(null);
      return;
    }
    setTeamCalculationState("loading");
    setTeamError("");
    try {
      const selected = teamSelection.selectedPlayerIds.map((playerId) => players.find((player) => player.player_id === playerId)).filter(Boolean);
      const results = [];
      for (const player of selected) {
        const role = teamSelection.playerRoles[player.player_id];
        if (!role) {
          throw new Error(`Choose a role for ${player.player_name.trim()} before calculating.`);
        }
        const multiplier = player.player_id === teamSelection.captainId ? 2 : player.player_id === teamSelection.viceCaptainId ? 1.5 : 1;
        const { data } = await api.post("/fantasy/calculate", {
          player_name: player.player_name.trim(),
          role,
          ...player.fantasy_inputs,
          multiplier
        });
        results.push({ ...data, player_id: player.player_id });
      }
      setTeamCalculation(buildTeamSummary(results));
      setTeamCalculationState("done");
    } catch (error) {
      setTeamError(error instanceof Error ? error.message : readApiError(error, "Unable to calculate the manual XI."));
      setTeamCalculationState("error");
    }
  }

  function populatePlayer(player) {
    setSelectedPlayer(player);
    setForm(playerToCalculatorForm(player));
    setCalculation(null);
    setAnalysis(null);
    setAnalysisError("");
    setAnalysisState("idle");
  }

  function updateForm(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  async function calculate(event) {
    event.preventDefault();
    setCalculatorState("loading");
    setCalculation(null);
    setAnalysis(null);
    setAnalysisError("");
    setAnalysisState("idle");
    const payload = {};
    for (const [key, value] of Object.entries(form)) {
      if (key === "player_name" || key === "role") payload[key] = value;
      else if (key === "dismissed") payload[key] = value;
      else if (key === "multiplier") payload[key] = Number(value);
      else if (key === "announced_lineup" || key === "eligible_playing_substitute") payload[key] = value === "" ? null : value === true || value === "true";
      else payload[key] = value === "" ? null : Number(value);
    }
    try {
      const { data } = await api.post("/fantasy/calculate", payload);
      setCalculation(data);
      setCalculatorState("done");
    } catch (error) {
      setCalculation({ error: readApiError(error, "Unable to calculate. Check the entered values.") });
      setCalculatorState("error");
    }
  }

  async function explainPerformance() {
    if (!selectedPlayer || !calculation || calculation.error) return;
    setAnalysisState("loading");
    setAnalysis(null);
    setAnalysisError("");
    try {
      const { data } = await api.post("/ai/analyze-player", {
        match_name: selectedMatch?.name || "Selected match",
        player_name: selectedPlayer.player_name.trim(),
        player_role: form.role,
        batting_statistics: selectedPlayer.batting || {},
        bowling_statistics: selectedPlayer.bowling || {},
        fielding_statistics: selectedPlayer.fielding || {},
        fantasy_points_total: calculation.total_points,
        scoring_breakdown: calculation.breakdown,
        calculation_complete: calculation.complete,
        missing_statistics: calculation.missing_statistics || [],
        demo_fixture: selectedMatch?.demo === true
      }, { timeout: ANALYSIS_REQUEST_TIMEOUT_MS });
      setAnalysis(data);
      setAnalysisState("done");
    } catch (error) {
      setAnalysisError(readApiError(error, "Unable to generate the player analysis."));
      setAnalysisState("error");
    }
  }

  const visibleMatches = matches[matchTab];
  return (
    <main className="min-h-screen overflow-hidden bg-ink text-slate-100">
      <div className="relative mx-auto w-full max-w-[90rem] px-4 py-4 sm:px-6 sm:py-6 lg:px-10 lg:py-8">
        <Header health={health} activeTab={activeTab} onTabChange={setActiveTab} selectedMatch={selectedMatch} onChangeMatch={() => setActiveTab("overview")} />
        <div className="mt-5">
          <MatchContextBar match={selectedMatch} demo={dataMode === DATA_MODES.DEMO} onChangeMatch={() => setActiveTab("overview")} />
        </div>
        {activeTab === "overview" && <OverviewDashboard
          match={selectedMatch}
          dataMode={dataMode}
          data={momentumData}
          onRefresh={loadMatches}
          onModeChange={changeDataMode}
          matchTab={matchTab}
          onMatchTabChange={setMatchTab}
          matchState={matchState}
          matchError={matchError}
          quotaError={quotaError}
          onUseDemo={() => changeDataMode(DATA_MODES.DEMO)}
          matches={visibleMatches}
          onSelectMatch={selectMatch}
          selectedPlayer={selectedPlayer}
          players={players}
          playerState={playerState}
          playerError={playerError}
          onSelectPlayer={populatePlayer}
          form={form}
          updateForm={updateForm}
          calculate={calculate}
          calculation={calculation}
          calculatorState={calculatorState}
          analysis={analysis}
          analysisState={analysisState}
          analysisError={analysisError}
          canAnalyze={Boolean(selectedPlayer && calculation && !calculation.error)}
          onAnalyze={explainPerformance}
        />}
        {activeTab === "team" && <TeamBuilder
          match={selectedMatch}
          matches={matches}
          matchState={matchState}
          players={players}
          playerState={playerState}
          playerError={playerError}
          onSelectMatch={selectMatch}
          teamSelection={teamSelection}
          onTogglePlayer={toggleTeamPlayer}
          onChangeSelection={setTeamSelection}
          search={teamSearch}
          onSearch={setTeamSearch}
          calculation={teamCalculation}
          calculationState={teamCalculationState}
          error={teamError}
          onCalculate={calculateTeam}
        />}
        {activeTab === "comparison" && <PlayerComparison
          match={selectedMatch}
          players={players}
          playerState={playerState}
          playerError={playerError}
          selectedPlayers={comparisonPlayers}
          roles={comparisonRoles}
          results={comparisonResults}
          state={comparisonState}
          error={comparisonError}
          analysis={comparisonAnalysis}
          analysisState={comparisonAnalysisState}
          analysisError={comparisonAnalysisError}
          onSelect={chooseComparisonPlayer}
          onRoleChange={updateComparisonRole}
          onCalculate={calculateComparison}
          onExplain={explainComparison}
        />}
        {activeTab === "momentum" && <MatchMomentum
          match={selectedMatch}
          data={momentumData}
          state={momentumState}
          error={momentumError}
        />}
      </div>
    </main>
  );
}

function OverviewDashboard({
  match,
  dataMode,
  data,
  onRefresh,
  onModeChange,
  matchTab,
  onMatchTabChange,
  matchState,
  matchError,
  quotaError,
  onUseDemo,
  matches,
  onSelectMatch,
  selectedPlayer,
  players,
  playerState,
  playerError,
  onSelectPlayer,
  form,
  updateForm,
  calculate,
  calculation,
  calculatorState,
  analysis,
  analysisState,
  analysisError,
  canAnalyze,
  onAnalyze
}) {
  const innings = Array.isArray(match?.scores) ? match.scores : [];
  const momentumInnings = Array.isArray(data?.innings) ? data.innings : [];
  const winner = data?.result?.winner;
  const batting = Array.isArray(data?.batting_contributions)
    ? [...data.batting_contributions].filter((player) => player.runs !== null).sort((a, b) => b.runs - a.runs).slice(0, 3)
    : [];
  const bowling = Array.isArray(data?.bowling_contributions)
    ? [...data.bowling_contributions].filter((player) => player.wickets !== null).sort((a, b) => b.wickets - a.wickets).slice(0, 3)
    : [];
  const selectedStatus = match?.status || data?.result?.status || "Status unavailable";

  return <section className="overview-page pb-12 pt-10 lg:pt-14">
    <PageHeader
      eyebrow="Match intelligence"
      title="Cricket Overview"
      description="A focused summary of the selected match, verified scorecard facts, and player performance."
      actions={<div className="flex flex-wrap items-center justify-end gap-2">
        <DataModeSelector mode={dataMode} onChange={onModeChange} />
        <button onClick={() => onRefresh(dataMode)} className="overview-refresh-button"><RefreshCw size={16} /> Refresh matches</button>
      </div>}
    />

    {dataMode === DATA_MODES.DEMO && <div className="overview-demo-note"><ShieldCheck size={18} aria-hidden="true" /><span><strong>Local demo mode</strong> — Durham vs Warwickshire is saved fixture data, not live or current.</span><StatusBadge status="demo" label="Demo · not live" /></div>}

    {match && <Panel className="overview-score-panel" eyebrow="Selected match" title={match.name || "Unnamed match"} description={`${match.teams?.join(" · ") || "Teams unavailable"} · ${selectedStatus}`}>
      {innings.length > 0
        ? <div className="overview-score-grid">{innings.map((score, index) => <OverviewScoreBlock key={`${score.inning || index}`} score={score} index={index} primary={index === innings.length - 1} />)}</div>
        : <EmptyState icon={Activity} text="Scorecard totals are unavailable for this match." />}
      {(winner || selectedStatus) && <div className="overview-result"><Trophy size={17} aria-hidden="true" /><span>{winner ? `${winner} won` : selectedStatus}</span></div>}
    </Panel>}

    {match && <div className="overview-metrics">
      <MetricCard label="Innings recorded" value={innings.length || "—"} subtitle={innings.length ? "Verified scorecard totals" : "Unavailable"} />
      <MetricCard label="Result" value={winner || "—"} subtitle={winner ? "Verified match winner" : "Winner unavailable"} />
      <MetricCard label="Target" value={momentumInnings[1]?.target ?? "—"} subtitle={momentumInnings[1]?.target != null ? "Second innings target" : "Not available"} />
    </div>}

    <div className="mt-8 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
      <Panel eyebrow="Match center" title="Choose a match" icon={Activity}>
        {quotaError && <div className="mb-4">
          <ErrorState
            title="Cricket Data API quota exhausted"
            message="Live cricket data is temporarily unavailable because the provider confirmed its daily quota is exhausted."
          />
          <button onClick={onUseDemo} className="mt-3 w-full rounded-lg bg-lime px-4 py-3 text-sm font-bold text-ink">
            Switch to Demo Mode
          </button>
        </div>}
        <div className="mb-4 flex gap-2 rounded-lg bg-ink/70 p-1">
          {["live", "recent"].map((tab) => <button key={tab} onClick={() => onMatchTabChange(tab)} className={`flex-1 rounded-md px-3 py-2 text-xs font-bold uppercase tracking-wider ${matchTab === tab ? "bg-lime text-ink" : "text-slate-500 hover:text-slate-300"}`}>{tab}</button>)}
        </div>
        {matchState === "loading" && <Loading text="Loading verified matches..." />}
        {matchState === "error" && <ErrorState message={matchError} />}
        {matchState === "done" && matches.length === 0 && <EmptyState text={`No ${matchTab} matches are available right now.`} />}
        <div className="space-y-3">
          {matchState === "done" && matches.map((item) => <MatchCard key={item.id} match={item} selected={match?.id === item.id} state={matchTab} demo={dataMode === DATA_MODES.DEMO} onSelect={() => onSelectMatch(item)} />)}
        </div>
      </Panel>

      <Panel className="min-h-[360px]" eyebrow="Player performance" title={match ? "Verified match players" : "Select a match"} icon={Users}>
        {!match && <EmptyState icon={Trophy} text="Select a match to inspect player statistics." />}
        {match && <SelectedMatch match={match} players={players} state={playerState} error={playerError} selectedPlayer={selectedPlayer} onSelectPlayer={onSelectPlayer} />}
      </Panel>
    </div>

    {match && <div className="mt-8 grid gap-6 lg:grid-cols-2">
      <OverviewContributionPanel title="Top batting" subtitle="Runs from the verified scorecard" items={batting} valueKey="runs" valueLabel="runs" />
      <OverviewContributionPanel title="Top bowling" subtitle="Wickets from the verified scorecard" items={bowling} valueKey="wickets" valueLabel="wickets" />
    </div>}

    <section className="mt-10 grid gap-6 border-t border-white/10 py-12 lg:grid-cols-[0.75fr_1.25fr]">
      <div>
        <p className="eyebrow text-cyan"><Calculator size={15} /> Fantasy points calculator</p>
        <h2 className="mt-4 font-display text-3xl font-bold tracking-tight sm:text-4xl">Know where every point comes from.</h2>
        <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">Use verified player data when available, or continue entering statistics manually. Unknown values stay blank.</p>
        {selectedPlayer && <div className="mt-5 rounded-lg border border-cyan/20 bg-cyan/5 p-4 text-xs leading-5 text-cyan">Prefilled from {selectedPlayer.player_name.trim()}. Player role is not inferred—choose it before calculating.</div>}
      </div>
      <CalculatorForm form={form} updateForm={updateForm} calculate={calculate} calculation={calculation} calculatorState={calculatorState} />
    </section>
    <AnalystSection analysis={analysis} state={analysisState} error={analysisError} canAnalyze={canAnalyze} onAnalyze={onAnalyze} />
  </section>;
}

function DataModeSelector({ mode, onChange }) {
  return <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-ink/70 p-1" aria-label="Cricket data source">
    <button
      type="button"
      onClick={() => onChange(DATA_MODES.LIVE)}
      aria-pressed={mode === DATA_MODES.LIVE}
      className={`rounded-md px-3 py-2 text-xs font-bold ${mode === DATA_MODES.LIVE ? "bg-lime text-ink" : "text-slate-400 hover:text-slate-200"}`}
    >
      Live Cricket Data
    </button>
    <button
      type="button"
      onClick={() => onChange(DATA_MODES.DEMO)}
      aria-pressed={mode === DATA_MODES.DEMO}
      className={`rounded-md px-3 py-2 text-xs font-bold ${mode === DATA_MODES.DEMO ? "bg-amber-300 text-ink" : "text-slate-400 hover:text-slate-200"}`}
    >
      Demo Mode
    </button>
  </div>;
}

function OverviewScoreBlock({ score, index, primary }) {
  const label = typeof score?.inning === "string" ? score.inning.trim() : "";
  const team = label.replace(/\s+Inning\s+\d+$/i, "").trim() || "Team unavailable";
  const inningsNumber = label.match(/Inning\s+(\d+)$/i)?.[1] || String(index + 1);
  return <div className={`overview-score-block ${primary ? "overview-score-block-primary" : ""}`}>
    <div className="flex items-start justify-between gap-3"><div><p className="overview-score-team">{team}</p><p className="overview-score-innings">Innings {inningsNumber}</p></div><StatusBadge status={primary ? "complete" : "unavailable"} label={primary ? "Latest score" : "Innings 1"} /></div>
    <p className="overview-score-value">{score?.r ?? "—"}<span>/{score?.w ?? "—"}</span></p>
    <div className="overview-score-meta"><span>{score?.o ?? "—"} overs</span><span>RR {formatRate(score?.rr)}</span></div>
  </div>;
}

function OverviewContributionPanel({ title, subtitle, items, valueKey, valueLabel }) {
  return <Panel eyebrow="Player contributions" title={title} description={subtitle} icon={Users}>
    {items.length > 0
      ? <div className="space-y-2">{items.map((item, index) => <div key={`${item.player_name}-${index}`} className="overview-contribution-row"><div className="overview-rank">{index + 1}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-200">{item.player_name}</p><p className="mt-1 text-xs text-slate-500">{item.team || "Team unavailable"}{item.innings_number ? ` · Innings ${item.innings_number}` : ""}</p></div><strong className="font-display text-lg text-cyan">{item[valueKey] ?? "—"} <span className="font-sans text-xs font-medium text-slate-500">{valueLabel}</span></strong></div>)}</div>
      : <EmptyState icon={Users} text="No verified contribution data available." />}
  </Panel>;
}

function Header({ health, activeTab, onTabChange }) {
  const tabs = [
    ["overview", "Overview", LayoutDashboard],
    ["team", "My Fantasy Team", Users],
    ["comparison", "Player Comparison", BarChart3],
    ["momentum", "Match Momentum", Gauge]
  ];
  const handleKeyDown = (event, index) => {
    if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex = event.key === "ArrowRight" || event.key === "ArrowDown"
      ? (index + 1) % tabs.length
      : (index - 1 + tabs.length) % tabs.length;
    onTabChange(tabs[nextIndex][0]);
    document.querySelector(`[data-testid="nav-${tabs[nextIndex][0]}"]`)?.focus();
  };
  return <header className="shell-header">
    <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div className="brand-mark"><Trophy size={21} strokeWidth={2.5} /></div>
        <div><p className="font-display text-xl font-bold tracking-tight text-slate-50">FantasyEdge <span className="text-lime">AI</span></p><p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-400">Cricket intelligence workspace</p></div>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-300">
        <span className="status-chip"><span className={`status-dot ${health.status === "online" ? "status-online" : health.status === "checking" ? "status-checking" : "status-offline"}`} />{health.status === "online" ? "Backend connected" : health.status === "checking" ? "Connecting" : "Backend offline"}</span>
        <span className="scoring-chip"><ShieldCheck size={13} /> Deterministic scoring</span>
      </div>
    </div>
    <div className="shell-nav-wrap">
      <div className="shell-nav" role="tablist" aria-label="Primary navigation">
        {tabs.map(([id, label, Icon], index) => <button key={id} data-testid={`nav-${id}`} role="tab" aria-selected={activeTab === id} tabIndex={activeTab === id ? 0 : -1} onClick={() => onTabChange(id)} onKeyDown={(event) => handleKeyDown(event, index)} className={`shell-tab ${activeTab === id ? "shell-tab-active" : ""}`}><Icon size={16} aria-hidden="true" /><span>{label}</span></button>)}
      </div>
    </div>
  </header>;
}

function MatchContextBar({ match, demo, onChangeMatch }) {
  if (!match) return <div data-testid="match-context-bar" className="match-context match-context-empty"><Activity size={17} /><span>No match selected</span><button onClick={onChangeMatch} className="context-action">Choose a match</button></div>;
  return <div data-testid="match-context-bar" className="match-context"><div className="flex min-w-0 items-center gap-3"><div className="context-icon"><Activity size={16} /></div><div className="min-w-0"><p className="context-label">Selected match</p><p className="truncate text-sm font-semibold text-slate-100">{match.name || "Unnamed match"}</p><p className="truncate text-xs text-slate-400">{match.teams?.join(" · ") || "Teams unavailable"} · {match.status || "Status unavailable"}</p></div></div><div className="flex shrink-0 items-center gap-2"><StatusBadge status={demo ? "demo" : "live"} label={demo ? "Demo fixture · not live" : "Provider data"} /><button onClick={onChangeMatch} className="context-action">Change match</button></div></div>;
}

function comparisonAnalysisPayload(player, role, result) {
  return {
    player_name: player.player_name.trim(),
    player_role: role,
    batting_statistics: player.batting || {},
    bowling_statistics: player.bowling || {},
    fielding_statistics: player.fielding || {},
    fantasy_points_total: result.total_points,
    scoring_breakdown: result.breakdown,
    calculation_complete: result.complete,
    missing_statistics: result.missing_statistics || []
  };
}

export function PlayerComparison({ match, players = [], playerState, playerError, selectedPlayers = [null, null], roles = [null, null], results = [null, null], state, error, analysis, analysisState, analysisError, onSelect, onRoleChange, onCalculate, onExplain }) {
  const availablePlayers = Array.isArray(players) ? players : [];
  const canCompare = Boolean(match && availablePlayers.length >= 2);
  return <section data-testid="player-comparison-panel" className="pb-12 pt-10 lg:pt-14">
    <div className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
      <div><p className="eyebrow text-cyan"><BarChart3 size={15} /> Match intelligence</p><h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">Compare players.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Compare verified match statistics and deterministic fantasy scoring side by side. Unknown values remain unavailable.</p></div>
      <div className="rounded-xl border border-amber-300/25 bg-amber-300/10 px-4 py-3 text-xs text-amber-100">{match ? <><strong>{match.name || "Selected match"}</strong> · {match.demo ? "Demo fixture — not live" : "Provider match"}</> : "Select a match from Overview or My Fantasy Team"}</div>
    </div>
    {!match && <div className="panel"><EmptyState icon={Trophy} text="Select a match before comparing players." /></div>}
    {match && <><div className="panel mb-6">
      <div className="mb-5 flex items-center justify-between"><div><p className="eyebrow">Player selectors</p><h2 className="panel-title">Choose two players</h2></div><Users className="text-cyan" size={20} /></div>
      {playerState === "loading" && <Loading text="Loading player statistics..." />}{playerState === "error" && <ErrorState message={playerError} />}{playerState === "done" && availablePlayers.length < 2 && <EmptyState icon={Users} text="At least two players are needed for a comparison." />}
      <div className="grid gap-4 md:grid-cols-2">{[0, 1].map((index) => <div key={index} className="rounded-xl border border-white/10 bg-ink/40 p-4"><label className="text-xs font-semibold text-slate-400">Player {index + 1}<select className="field mt-2" value={selectedPlayers[index]?.player_id || ""} onChange={(event) => onSelect(index, event.target.value)} disabled={!canCompare}><option value="">Select a player</option>{availablePlayers.map((player) => <option key={player.player_id} value={player.player_id} disabled={selectedPlayers[1 - index]?.player_id === player.player_id}>{player.player_name.trim()}{player.role ? ` · ${player.role}` : ""}</option>)}</select></label>{selectedPlayers[index] && <><p className="mt-3 text-sm font-semibold text-slate-200">{selectedPlayers[index].player_name.trim()}</p><p className="mt-1 text-xs text-slate-500">{selectedPlayers[index].role ? `Source role: ${selectedPlayers[index].role}` : "Role unavailable from source data"}</p><label className="mt-4 block text-xs font-semibold text-slate-400">Scoring role {selectedPlayers[index].role ? "(source role)" : "(required — not inferred)"}<select className="field mt-2" value={roles[index] || ""} onChange={(event) => onRoleChange(index, event.target.value)}><option value="">Choose explicit role</option><option value="batter">Batter</option><option value="bowler">Bowler</option><option value="all_rounder">All-rounder</option><option value="wicketkeeper">Wicketkeeper</option></select></label></>}</div>)}</div>
      {error && <div className="mt-4"><ErrorState message={error} /></div>}<button onClick={onCalculate} disabled={state === "loading" || !canCompare} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-lime px-4 py-3 text-sm font-bold text-ink disabled:cursor-not-allowed disabled:opacity-50">{state === "loading" && <LoaderCircle size={16} className="animate-spin" />}Calculate comparison points</button>
    </div>
    {selectedPlayers[0] && selectedPlayers[1] && <ComparisonStats players={selectedPlayers} results={results} />}
    {results[0] && results[1] && <section className="panel mt-6"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><p className="eyebrow text-cyan"><BrainCircuit size={15} /> Optional AI explanation</p><h2 className="panel-title mt-1">Explain the comparison</h2><p className="mt-2 text-sm text-slate-400">Gemini receives only these verified statistics and Python-generated totals. No predictions or recommendations.</p></div><button onClick={onExplain} disabled={analysisState === "loading"} className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-cyan px-4 py-3 text-sm font-bold text-ink disabled:opacity-50">{analysisState === "loading" ? <LoaderCircle size={16} className="animate-spin" /> : <BrainCircuit size={16} />}Explain Comparison</button></div>{analysisError && <div className="mt-4"><ErrorState message={analysisError} /></div>}{analysis && <div className="mt-6 grid gap-3 sm:grid-cols-2"><AnalysisCard title="Summary" text={analysis.summary} /><AnalysisCard title="Batting" text={analysis.batting_analysis} /><AnalysisCard title="Bowling" text={analysis.bowling_analysis} /><AnalysisCard title="Fielding" text={analysis.fielding_analysis} /><AnalysisCard title="Fantasy points" text={analysis.fantasy_points_explanation} /><div className="rounded-lg border border-amber-300/20 bg-amber-300/5 p-4"><p className="text-xs font-bold uppercase tracking-wider text-amber-200">Data limitations</p><ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6 text-amber-100">{analysis.data_limitations?.length ? analysis.data_limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>) : <li>No additional limitations reported.</li>}</ul></div></div>}</section>}</>}
  </section>;
}

function ComparisonStats({ players, results }) {
  return <div className="space-y-6"><div className="grid gap-6 lg:grid-cols-2">{COMPARISON_STAT_GROUPS.map((group) => <div className="panel" key={group.key}><div className="mb-5 flex items-center justify-between"><div><p className="eyebrow">{group.label}</p><h2 className="panel-title">Verified statistics</h2></div><BarChart3 className="text-cyan" size={18} /></div><div className="space-y-2">{group.fields.map(([field, label, suffix]) => { const values = players.map((player) => player[group.key]?.[field] ?? null); return <div key={field} className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-lg bg-ink/50 px-3 py-2 text-sm"><span className="text-slate-400">{label}</span><span className={values[0] === null ? "text-slate-600" : "font-semibold text-slate-200"}>{values[0] === null ? "Unavailable" : `${formatPlayerStat(field, values[0])}${suffix}`}</span><span className={values[1] === null ? "text-slate-600" : "font-semibold text-slate-200"}>{values[1] === null ? "Unavailable" : `${formatPlayerStat(field, values[1])}${suffix}`}</span></div>; })}</div><ComparisonChart players={players} group={group.key} field={group.fields[0][0]} label={group.fields[0][1]} /></div>)}</div><div className="panel"><div className="mb-5"><p className="eyebrow text-lime">Fantasy points</p><h2 className="panel-title">Deterministic scoring comparison</h2></div>{results?.[0] && results?.[1] ? <><div className="grid gap-3 sm:grid-cols-2">{results.map((result) => <div className="rounded-lg border border-white/10 bg-ink/50 p-4" key={result.player_id}><p className="text-sm font-semibold text-slate-200">{result.player_name}</p><p className="mt-2 font-display text-3xl font-bold text-lime">{result.total_points} pts</p><p className={`mt-2 text-xs ${result.complete ? "text-lime" : "text-amber-300"}`}>{result.complete ? "Complete calculation" : `Incomplete · missing ${result.missing_statistics.join(", ")}`}</p><div className="mt-3 flex flex-wrap gap-2">{Object.entries(result.breakdown).flatMap(([category, items]) => Object.entries(items).filter(([label]) => label !== "multiplier").map(([label, item]) => <span className="rounded bg-white/5 px-2 py-1 text-[10px] text-slate-400" key={`${category}-${label}`}>{label.replaceAll("_", " ")}: {item.points}</span>))}</div></div>)}</div><ComparisonChart players={results.map((result) => ({ player_name: result.player_name, fantasy: { total_points: result.total_points } }))} group="fantasy" field="total_points" label="Total points" /></> : <p className="text-sm text-slate-500">Calculate both players to compare deterministic fantasy points.</p>}</div></div>;
}

function ComparisonChart({ players, group, field, label }) {
  const data = buildComparisonChartData(players, group, field);
  const available = data.filter((item) => item.value !== null);
  return <div className="mt-6 h-48">{available.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8 }} formatter={(value) => [value, label]} /><Bar dataKey="value" name={label} radius={[4, 4, 0, 0]}>{data.map((item) => <Cell key={item.name} fill={item.value === null ? "transparent" : "#b8f34a"} />)}</Bar></BarChart></ResponsiveContainer> : <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-white/10 text-xs text-slate-600">No verified {label.toLowerCase()} data available</div>}</div>;
}

function MatchMomentum({ match, data, state, error }) {
  if (!match) return <section className="py-20"><div className="panel mx-auto max-w-2xl text-center"><EmptyState icon={Trophy} text="Select a match from Overview or My Fantasy Team to view momentum." /></div></section>;
  if (state === "loading") return <section className="py-20"><div className="panel"><Loading text="Loading scorecard momentum..." /></div></section>;
  if (state === "error") return <section className="py-20"><div className="panel"><ErrorState message={error || "Unable to load scorecard momentum."} /></div></section>;
  if (!data) return <section className="py-20"><div className="panel"><EmptyState icon={Activity} text="No scorecard momentum data is available." /></div></section>;

  const innings = Array.isArray(data.innings) ? data.innings : [];
  const batting = Array.isArray(data.batting_contributions) ? data.batting_contributions : [];
  const bowling = Array.isArray(data.bowling_contributions) ? data.bowling_contributions : [];
  const dismissals = Array.isArray(data.dismissal_events) ? data.dismissal_events : [];
  const scoreChart = innings.map((inning) => ({ name: `${inning.team || "Team unavailable"} · Innings ${inning.innings_number}`, runs: inning.runs, wickets: inning.wickets, run_rate: inning.run_rate }));
  const topBatting = [...batting].filter((player) => player.runs !== null).sort((a, b) => b.runs - a.runs).slice(0, 5);
  const topBowling = [...bowling].filter((player) => player.wickets !== null).sort((a, b) => b.wickets - a.wickets).slice(0, 5);
  const unavailable = [
    ["Ball-by-ball progression", data.availability?.ball_by_ball],
    ["Over-by-over timeline", data.availability?.innings_progression],
    ["Partnerships", data.availability?.partnerships],
    ["Fall-of-wicket timeline", data.availability?.fall_of_wickets]
  ];
  return <section data-testid="match-momentum-panel" className="pb-12 pt-10 lg:pt-14">
    <div className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><p className="eyebrow text-cyan"><Activity size={15} /> Scorecard momentum</p><h1 className="mt-3 font-display text-4xl font-bold tracking-tight sm:text-5xl">Match Momentum.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">A deterministic scorecard view of verified innings and player contributions. This is not a ball-by-ball timeline.</p></div><div className="rounded-xl border border-amber-300/25 bg-amber-300/10 px-4 py-3 text-xs text-amber-100"><strong>{match.name || "Selected match"}</strong> · {data.demo ? "Demo fixture — not live" : "Provider data"}</div></div>
    <div className="panel mb-6"><div className="flex flex-wrap items-center gap-3 text-sm text-slate-300"><ShieldCheck size={18} className="text-amber-300" /><span>Source: <strong className="text-amber-200">{data.source || "unavailable"}</strong>. Unsupported timeline metrics remain unavailable.</span></div></div>
    <div className="grid gap-6 lg:grid-cols-2">{innings.map((inning) => <div className="panel" key={inning.innings_number}><div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Innings {inning.innings_number}</p><h2 className="panel-title">{inning.team || "Team unavailable"} · Innings {inning.innings_number}</h2></div><span className="rounded-full bg-lime/10 px-3 py-1 text-xs font-bold text-lime">{formatMomentumValue(inning.runs)}/{formatMomentumValue(inning.wickets)} ({formatMomentumValue(inning.overs)} ov)</span></div><div className="mt-5 grid grid-cols-3 gap-2 text-xs"><MomentumStat label="Overs" value={formatMomentumValue(inning.overs)} /><MomentumStat label="Run rate" value={formatMomentumValue(inning.run_rate)} /><MomentumStat label="Target" value={formatMomentumValue(inning.target)} /></div></div>)}</div>
    <div className="grid gap-6 mt-6 lg:grid-cols-2"><div className="panel"><div className="mb-5"><p className="eyebrow">Innings comparison</p><h2 className="panel-title">Runs and wickets</h2></div>{scoreChart.length ? <div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={scoreChart} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8 }} /><Legend /><Bar dataKey="runs" fill="#b8f34a" name="Runs" radius={[4, 4, 0, 0]} /><Bar dataKey="wickets" fill="#59d9d0" name="Wickets" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <EmptyState icon={Activity} text="Innings totals are unavailable." />}</div><div className="panel"><div className="mb-5"><p className="eyebrow">Rate comparison</p><h2 className="panel-title">Run rate</h2></div>{scoreChart.some((item) => item.run_rate !== null && item.run_rate !== undefined) ? <div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={scoreChart} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}><CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} axisLine={false} /><YAxis tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8 }} formatter={(value) => [value, "Run rate"]} /><Bar dataKey="run_rate" fill="#59d9d0" name="Run rate" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <EmptyState icon={Activity} text="Run rate is unavailable." />}</div></div>
    <div className="grid gap-6 py-6 lg:grid-cols-2"><ContributionPanel title="Top batting contributions" empty="No verified batting contributions." items={topBatting} valueKey="runs" valueLabel="runs" /><ContributionPanel title="Top bowling contributions" empty="No verified bowling contributions." items={topBowling} valueKey="wickets" valueLabel="wickets" /></div>
    <div className="grid gap-6 lg:grid-cols-2"><div className="panel"><div className="mb-5"><p className="eyebrow">Verified match events</p><h2 className="panel-title">Result and dismissals</h2></div><p className="text-sm text-slate-300">{data.result?.status || "Result unavailable"}{data.result?.winner ? ` · Winner: ${data.result.winner}` : ""}</p>{dismissals.length ? <div className="mt-4 space-y-2">{dismissals.map((event, index) => <div className="rounded-lg bg-ink/50 px-3 py-2 text-xs text-slate-300" key={`${event.player_name}-${index}`}><strong>{event.player_name}</strong> · {event.description || event.dismissal || "Dismissal recorded"} <span className="text-slate-500">({event.team || "Team unavailable"})</span></div>)}</div> : <p className="mt-4 text-xs text-slate-500">No verified dismissal events are available.</p>}</div><div className="panel"><div className="mb-5"><p className="eyebrow">Data availability</p><h2 className="panel-title">Unavailable timelines</h2></div><div className="space-y-2">{unavailable.map(([label, available]) => <div className="flex items-center justify-between rounded-lg bg-ink/50 px-3 py-2 text-sm" key={label}><span className="text-slate-400">{label}</span><span className={available ? "text-lime" : "text-slate-600"}>{available ? "Available" : "Unavailable"}</span></div>)}</div></div></div>
  </section>;
}

function formatMomentumValue(value) {
  if (value === null || value === undefined) return "Unavailable";
  return typeof value === "number" && !Number.isInteger(value) ? formatRate(value) : value;
}

function MomentumStat({ label, value }) {
  return <div className="rounded-lg bg-ink/50 px-3 py-3"><span className="block text-slate-500">{label}</span><strong className={value === "Unavailable" ? "text-slate-600" : "text-slate-200"}>{value}</strong></div>;
}

function ContributionPanel({ title, empty, items, valueKey, valueLabel }) {
  return <div className="panel"><div className="mb-5"><p className="eyebrow">Verified contributions</p><h2 className="panel-title">{title}</h2></div>{items.length ? <div className="space-y-2">{items.map((item, index) => <div className="flex items-center justify-between rounded-lg bg-ink/50 px-3 py-2 text-sm" key={`${item.player_name}-${index}`}><span className="text-slate-300">{item.player_name}</span><strong className="text-lime">{formatMomentumValue(item[valueKey])} {valueLabel}</strong></div>)}</div> : <p className="text-sm text-slate-500">{empty}</p>}</div>;
}

function TeamBuilder({ match, matches, matchState, players, playerState, playerError, onSelectMatch, teamSelection, onTogglePlayer, onChangeSelection, search, onSearch, calculation, calculationState, error, onCalculate }) {
  const allMatches = [...matches.live, ...matches.recent].filter((item, index, list) => list.findIndex((candidate) => candidate.id === item.id) === index);
  const filteredPlayers = players.filter((player) => player.player_name.trim().toLowerCase().includes(search.trim().toLowerCase()));
  const updateRole = (playerId, role) => onChangeSelection((current) => ({ ...current, playerRoles: { ...current.playerRoles, [playerId]: role } }));
  const selectedPlayers = teamSelection.selectedPlayerIds.map((id) => players.find((player) => player.player_id === id)).filter(Boolean);
  const total = calculation?.results?.reduce((sum, result) => sum + result.total_points, 0) || 0;
  return <section className="pb-12 pt-10 lg:pt-14">
    <PageHeader
      eyebrow="Manual fantasy XI"
      title="My Fantasy Team"
      description="Select players manually from the selected match and calculate transparent, deterministic fantasy points. This is not an official Dream11 team."
      actions={<label className="team-match-select">Available match<select className="field mt-2" value={match?.id || ""} onChange={(event) => { const next = allMatches.find((item) => item.id === event.target.value); if (next) onSelectMatch(next); }} disabled={matchState !== "done"}><option value="" disabled>{matchState === "loading" ? "Loading matches..." : "Select a match"}</option>{allMatches.map((item) => <option key={item.id} value={item.id}>{item.name || "Unnamed match"}{item.id === match?.id ? " (selected)" : ""}</option>)}</select></label>}
    />
    {!match && <Panel className="mt-8"><EmptyState icon={Trophy} title="Start with a match" text="Select a match above to start building your manual XI." /></Panel>}
    {match && <><div className="team-context-bar"><div className="team-context-copy"><ShieldCheck size={18} aria-hidden="true" /><div><strong>{match.name || "Selected match"}</strong><span>{match.teams?.join(" · ") || "Teams unavailable"}</span></div></div><div className="team-context-status"><StatusBadge status={match.demo ? "demo" : "live"} label={match.demo ? "Demo · not live" : "Provider data"} /><strong>{teamSelection.selectedPlayerIds.length}/11</strong><span>selected</span></div></div>
      <div className="team-layout">
        <Panel className="team-pool-panel" eyebrow="Player pool" title="Choose players" description="Review verified statistics before adding a player. Roles are not inferred from source data." icon={Users} actions={<label className="team-search"><Search size={16} aria-hidden="true" /><input className="field" placeholder="Search player name" value={search} onChange={(event) => onSearch(event.target.value)} aria-label="Search player name" /></label>}>
          {playerState === "loading" && <Loading text="Loading player statistics..." />}{playerState === "error" && <ErrorState message={playerError} />}{playerState === "done" && filteredPlayers.length === 0 && <EmptyState icon={Users} text="No matching players were found." />}
          <div className="team-player-grid">{filteredPlayers.map((player) => { const selected = teamSelection.selectedPlayerIds.includes(player.player_id); return <button key={player.player_id} onClick={() => onTogglePlayer(player.player_id)} aria-pressed={selected} className={`team-player-card ${selected ? "team-player-card-selected" : ""}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold text-slate-200">{player.player_name.trim()}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">{selected ? "Selected · click to remove" : "Available"} · Role not inferred</p></div><span className={`team-player-action ${selected ? "team-player-action-selected" : ""}`}>{selected ? <X size={16} aria-hidden="true" /> : <Users size={16} aria-hidden="true" />}</span></div><div className="mt-4 grid grid-cols-2 gap-2 text-xs"><Stat label="Runs" value={player.batting.runs ?? "—"} /><Stat label="Balls" value={player.batting.balls_faced ?? "—"} /><Stat label="4s / 6s" value={`${player.batting.fours ?? "—"} / ${player.batting.sixes ?? "—"}`} /><Stat label="Wickets" value={player.bowling.wickets ?? "—"} /><Stat label="Overs" value={player.bowling.overs_bowled ?? "—"} /><Stat label="Economy" value={formatPlayerStat("economy", player.bowling.economy)} /><Stat label="Catches" value={player.fielding.catches ?? "—"} /><Stat label="Stumpings" value={player.fielding.stumpings ?? "—"} /></div></button>; })}</div>
        </Panel>
        <div className="team-side-column">
          <Panel className="team-xi-panel" eyebrow="Team composition" title="Selected XI" description="Assign a scoring role to every selected player before calculating." actions={<MetricCard label="Players" value={`${teamSelection.selectedPlayerIds.length}/11`} subtitle={teamSelection.selectedPlayerIds.length === 11 ? "XI complete" : "Manual selection"} />}>
            {selectedPlayers.length === 0 && <EmptyState icon={Users} title="No players selected" text="Choose players from the pool to build your XI." />}
            <div className="team-selected-list">{selectedPlayers.map((player) => <div key={player.player_id} className="team-selected-card"><div className="flex min-w-0 items-center gap-3"><div className="team-player-number">{teamSelection.selectedPlayerIds.indexOf(player.player_id) + 1}</div><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-200">{player.player_name.trim()}</p><p className="mt-1 text-xs text-slate-500">{teamSelection.playerRoles[player.player_id] || "Role required"}</p></div></div><div className="flex items-center gap-2"><button onClick={() => onTogglePlayer(player.player_id)} className="team-remove-button" aria-label={`Remove ${player.player_name.trim()}`}><X size={15} /></button><select className="field team-role-select" aria-label={`Scoring role for ${player.player_name.trim()}`} value={teamSelection.playerRoles[player.player_id] || ""} onChange={(event) => updateRole(player.player_id, event.target.value)}><option value="">Choose role</option><option value="batter">Batter</option><option value="bowler">Bowler</option><option value="all_rounder">All-rounder</option><option value="wicketkeeper">Wicketkeeper</option></select></div></div>)}</div>
          </Panel>
          <Panel className="team-leadership-panel" eyebrow="Leadership" title="Captaincy multipliers" description="Captain receives 2× points; vice-captain receives 1.5× points. They must be different selected players.">
            <div className="team-leadership-grid"><label className="team-leader-field"><span><strong>Captain</strong><StatusBadge status="complete" label="2×" /></span><select className="field mt-2" value={teamSelection.captainId || ""} onChange={(event) => onChangeSelection((current) => ({ ...current, captainId: event.target.value || null }))}><option value="">Choose captain</option>{selectedPlayers.map((player) => <option key={player.player_id} value={player.player_id}>{player.player_name.trim()}</option>)}</select></label><label className="team-leader-field"><span><strong>Vice-captain</strong><StatusBadge status="live" label="1.5×" /></span><select className="field mt-2" value={teamSelection.viceCaptainId || ""} onChange={(event) => onChangeSelection((current) => ({ ...current, viceCaptainId: event.target.value || null }))}><option value="">Choose vice-captain</option>{selectedPlayers.map((player) => <option key={player.player_id} value={player.player_id}>{player.player_name.trim()}</option>)}</select></label></div>
            <button onClick={onCalculate} disabled={calculationState === "loading"} className="team-calculate-button">{calculationState === "loading" && <LoaderCircle size={16} className="animate-spin" />}Calculate team points</button>
            {error && <div className="mt-4"><ErrorState message={error} /></div>}
          </Panel>
        </div>
      </div>
      {calculation && <TeamPointsSummary calculation={calculation} total={total} />}
    </>}
  </section>;
}

function TeamPointsSummary({ calculation, total }) {
  return <Panel className="team-summary-panel mt-6" eyebrow="Deterministic scoring" title="Team points summary" description="Points are calculated by the existing Python scoring engine. Unknown statistics remain incomplete, not zero.">
    <div className="team-total-row"><div><span className="metric-label">Total team points</span><strong className="team-total-value">{total}</strong></div><StatusBadge status={calculation.complete ? "complete" : "incomplete"} label={calculation.complete ? "Complete" : `${calculation.incompletePlayers} incomplete`} /></div>
    <div className="team-result-list">{calculation.results.map((result) => <div key={result.player_id} className="team-result-card"><div className="flex min-w-0 items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-200">{result.player_name}</p><p className="mt-1 text-xs text-slate-500">{result.multiplier === 2 ? "Captain · 2× multiplier" : result.multiplier === 1.5 ? "Vice-captain · 1.5× multiplier" : "Selected player · 1× multiplier"}</p></div><strong className="team-result-points">{result.total_points} <span>pts</span></strong></div><p className="mt-3 text-xs text-slate-400">{result.subtotal} base points × {result.multiplier} multiplier</p>{!result.complete && <p className="mt-2 text-xs text-amber-300">Unknown statistics: {result.missing_statistics.join(", ")}</p>}<div className="mt-3 flex flex-wrap gap-2">{Object.entries(result.breakdown).flatMap(([category, items]) => Object.entries(items).filter(([label]) => label !== "multiplier").map(([label, item]) => <span key={`${category}-${label}`} className="team-breakdown-chip">{label.replaceAll("_", " ")}: {item.points}</span>))}</div></div>)}</div>
  </Panel>;
}

function FeaturePlaceholder({ title, text }) {
  return <section className="py-20"><div className="panel mx-auto max-w-2xl text-center"><Sparkles className="mx-auto mb-4 text-cyan" size={28} /><p className="eyebrow justify-center">Coming next</p><h1 className="mt-3 font-display text-4xl font-bold">{title}</h1><p className="mt-4 text-sm leading-6 text-slate-400">{text}</p></div></section>;
}

function MatchCard({ match, selected, state, demo, onSelect }) {
  return <button onClick={onSelect} className={`w-full rounded-xl border p-4 text-left transition ${selected ? "border-lime/60 bg-lime/5" : "border-white/10 bg-white/[0.02] hover:border-white/25"}`}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-slate-200">{match.name || "Unnamed match"}</p><p className="mt-1 text-xs text-slate-500">{match.teams?.join(" · ") || "Teams unavailable"} · {match.match_type || "Type unavailable"}</p></div><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${demo ? "bg-amber-300/10 text-amber-200" : state === "live" ? "bg-lime/10 text-lime" : "bg-white/10 text-slate-400"}`}>{demo ? "demo" : state}</span></div><p className="mt-4 text-sm text-slate-400">{match.status || "Status unavailable"}</p>{match.scores?.length > 0 ? <div className="mt-3 grid gap-2 sm:grid-cols-2">{match.scores.map((score, index) => <div key={`${score.inning || index}`} className="rounded-md bg-ink/70 px-3 py-2 text-xs text-slate-300"><span>{formatInningsLabel(score, index)}</span></div>)}</div> : <p className="mt-3 text-xs text-slate-600">Score not available from provider</p>}</button>;
}

function SelectedMatch({ match, players, state, error, selectedPlayer, onSelectPlayer }) {
  return <div><div className="mb-6 border-b border-white/10 pb-5"><p className="eyebrow">Selected match</p><h2 className="panel-title mt-1">{match.name || "Unnamed match"}</h2><p className="mt-2 text-sm text-slate-400">{match.teams?.join(" · ") || "Teams unavailable"} · {match.status || "Status unavailable"}</p></div>{state === "loading" && <Loading text="Loading player statistics..." />}{state === "error" && <ErrorState message={error} />}{state === "done" && players.length === 0 && <EmptyState icon={Users} text="No player rows were available for this match." />}{state === "done" && players.length > 0 && <div className="grid max-h-[570px] gap-3 overflow-y-auto pr-1 sm:grid-cols-2">{players.map((player) => <PlayerCard key={player.player_id} player={player} selected={selectedPlayer?.player_id === player.player_id} onSelect={() => onSelectPlayer(player)} />)}</div>}</div>;
}

function PlayerCard({ player, selected, onSelect }) {
  const stat = (value) => value === null || value === undefined ? "—" : value;
  return <button onClick={onSelect} className={`rounded-xl border p-4 text-left ${selected ? "border-cyan/60 bg-cyan/5" : "border-white/10 bg-ink/40 hover:border-white/25"}`}><div className="flex items-center justify-between"><p className="font-semibold text-slate-200">{player.player_name.trim()}</p><ArrowUpRight size={15} className="text-slate-600" /></div><div className="mt-4 grid grid-cols-2 gap-2 text-xs"><Stat label="Runs" value={stat(player.batting.runs)} /><Stat label="Balls" value={stat(player.batting.balls_faced)} /><Stat label="4s / 6s" value={`${stat(player.batting.fours)} / ${stat(player.batting.sixes)}`} /><Stat label="Wickets" value={stat(player.bowling.wickets)} /><Stat label="Overs" value={stat(player.bowling.overs_bowled)} /><Stat label="Economy" value={formatPlayerStat("economy", player.bowling.economy)} /><Stat label="Catches" value={stat(player.fielding.catches)} /></div></button>;
}

function Stat({ label, value }) { return <div className="rounded-md bg-panel px-2 py-2"><span className="block text-slate-600">{label}</span><strong className={value === "—" ? "text-slate-600" : "text-slate-200"}>{value}</strong></div>; }

function loadDataMode() {
  try {
    const stored = window.localStorage.getItem(DATA_MODE_STORAGE_KEY);
    return Object.values(DATA_MODES).includes(stored) ? stored : DATA_MODES.LIVE;
  } catch {
    return DATA_MODES.LIVE;
  }
}

function saveDataMode(mode) {
  try {
    window.localStorage.setItem(DATA_MODE_STORAGE_KEY, mode);
  } catch {
    // Persistence is optional when browser storage is unavailable or full.
  }
}

function cricketGet(path, mode) {
  return api.get(path, { params: { mode } });
}

function getApiErrorCode(error) {
  const detail = error?.response?.data?.detail;
  return typeof detail?.code === "string" ? detail.code : null;
}

function readApiError(error, fallback) {
  const response = error?.response;
  const data = response?.data;
  const structured = data?.error;
  if (typeof structured?.message === "string" && structured.message.trim()) return structured.message;
  const detail = data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(", ") || fallback;
  if (typeof detail?.message === "string" && detail.message.trim()) return detail.message;
  if (response?.status === 401 || response?.status === 403) return "Gemini authentication failed. Check the backend Gemini API key.";
  if (response?.status === 408 || response?.status === 429 || response?.status === 503 || response?.status === 504) return "Gemini is temporarily unavailable. Please try again shortly.";
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") return "The Gemini request timed out. Please try again.";
  if (error?.request && !response) return "The backend could not be reached. Check that FastAPI is running and try again.";
  if (typeof error?.message === "string" && error.message.trim()) return error.message;
  return fallback;
}

function playerToCalculatorForm(player) {
  const inputs = player?.fantasy_inputs || {};
  const value = (key) => inputs[key] ?? "";
  return {
    ...EMPTY_FORM,
    player_name: player?.player_name?.trim() || EMPTY_FORM.player_name,
    runs: value("runs"),
    fours: value("fours"),
    sixes: value("sixes"),
    balls_faced: value("balls_faced"),
    dismissed: inputs.dismissed ?? EMPTY_FORM.dismissed,
    dot_balls: value("dot_balls"),
    wickets: value("wickets"),
    lbw_bowled_wickets: value("lbw_bowled_wickets"),
    maiden_overs: value("maiden_overs"),
    overs_bowled: value("overs_bowled"),
    runs_conceded: value("runs_conceded"),
    catches: value("catches"),
    stumpings: value("stumpings"),
    direct_hit_run_outs: value("direct_hit_run_outs"),
    other_run_outs: value("other_run_outs"),
    announced_lineup: value("announced_lineup"),
    eligible_playing_substitute: value("eligible_playing_substitute")
  };
}

function CalculatorForm({ form, updateForm, calculate, calculation, calculatorState }) {
  const rows = [["runs", "Runs"], ["fours", "Fours"], ["sixes", "Sixes"], ["balls_faced", "Balls faced"], ["dot_balls", "Dot balls"], ["wickets", "Wickets"], ["lbw_bowled_wickets", "LBW / bowled"], ["maiden_overs", "Maiden overs"], ["overs_bowled", "Overs"], ["runs_conceded", "Runs conceded"], ["catches", "Catches"], ["stumpings", "Stumpings"]];
  return <div className="panel"><form onSubmit={calculate} className="space-y-4"><div className="grid gap-3 sm:grid-cols-3"><Field label="Player name" name="player_name" value={form.player_name} onChange={updateForm} /><SelectField label="Role (required)" name="role" value={form.role} onChange={updateForm} options={[["batter", "Batter"], ["bowler", "Bowler"], ["all_rounder", "All-rounder"], ["wicketkeeper", "Wicketkeeper"]]} /><SelectField label="Multiplier" name="multiplier" value={form.multiplier} onChange={updateForm} options={[["1", "Player (1x)"], ["2", "Captain (2x)"], ["1.5", "Vice-captain (1.5x)"]]} /></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{rows.map(([name, label]) => <Field key={name} label={label} name={name} value={form[name]} onChange={updateForm} />)}</div><div className="grid gap-3 sm:grid-cols-2"><label className="flex items-center gap-2 text-xs font-semibold text-slate-400"><input type="checkbox" name="dismissed" checked={form.dismissed} onChange={updateForm} /> Dismissed</label><SelectField label="Announced lineup" name="announced_lineup" value={form.announced_lineup} onChange={updateForm} options={[["", "Unknown"], ["true", "Yes"], ["false", "No"]]} /></div><button type="submit" disabled={calculatorState === "loading"} className="flex w-full items-center justify-center gap-2 rounded-lg bg-lime px-5 py-3 text-sm font-bold text-ink disabled:cursor-wait disabled:opacity-70">{calculatorState === "loading" && <LoaderCircle size={16} className="animate-spin" />}Calculate points</button></form>{calculation && <CalculationResult calculation={calculation} />}</div>;
}

function AnalystSection({ analysis, state, error, canAnalyze, onAnalyze }) {
  return <section className="panel mb-14"><div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start"><div><p className="eyebrow text-cyan"><BrainCircuit size={15} /> AI Match &amp; Player Analyst</p><h2 className="mt-3 font-display text-3xl font-bold tracking-tight">Understand the performance.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Gemini explains supplied match facts and Python-generated scoring. It never recalculates points or predicts future performance.</p></div><button type="button" onClick={onAnalyze} disabled={!canAnalyze || state === "loading"} className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-cyan px-4 py-3 text-sm font-bold text-ink disabled:cursor-not-allowed disabled:opacity-40">{state === "loading" ? <LoaderCircle size={16} className="animate-spin" /> : <BrainCircuit size={16} />} {state === "loading" ? "Analyzing..." : "Explain Player Performance"}</button></div>{!canAnalyze && <p className="mt-5 text-xs text-slate-500">Select a player and calculate fantasy points before requesting an explanation.</p>}{state === "error" && <div className="mt-5"><ErrorState message={error} /><button type="button" onClick={onAnalyze} className="mt-3 rounded-lg border border-white/15 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-white/30">Retry analysis</button></div>}{analysis && <div className="mt-7 grid gap-3 sm:grid-cols-2"><AnalysisCard title="Summary" text={analysis.summary} /><AnalysisCard title="Batting" text={analysis.batting_analysis} /><AnalysisCard title="Bowling" text={analysis.bowling_analysis} /><AnalysisCard title="Fielding" text={analysis.fielding_analysis} /><AnalysisCard title="Fantasy points" text={analysis.fantasy_points_explanation} /><div className="rounded-lg border border-amber-300/20 bg-amber-300/5 p-4"><p className="text-xs font-bold uppercase tracking-wider text-amber-200">Data limitations</p>{analysis.data_limitations.length ? <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6 text-amber-100">{analysis.data_limitations.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p className="mt-2 text-sm text-slate-300">No additional limitations reported.</p>}</div></div>}</section>;
}

function AnalysisCard({ title, text }) {
  return <div className="rounded-lg border border-white/10 bg-ink/40 p-4"><p className="text-xs font-bold uppercase tracking-wider text-cyan">{title}</p><p className="mt-2 text-sm leading-6 text-slate-300">{text}</p></div>;
}

function Field({ label, name, value, onChange }) { return <label className="text-xs font-semibold text-slate-400">{label}<input className="field mt-2" type={name === "player_name" ? "text" : "number"} min="0" name={name} value={value ?? ""} onChange={onChange} /></label>; }
function SelectField({ label, name, value, onChange, options }) { return <label className="text-xs font-semibold text-slate-400">{label}<select name={name} value={value} onChange={onChange} className="field mt-2">{options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select></label>; }
function CalculationResult({ calculation }) { if (calculation.error) return <ErrorState message={calculation.error} />; const entries = Object.entries(calculation.breakdown).flatMap(([category, items]) => Object.entries(items).filter(([label]) => label !== "multiplier").map(([label, item]) => ({ category, label, ...item }))); return <div className="mt-5 border-t border-white/10 pt-5"><div className="flex items-end justify-between"><div><p className="eyebrow">{calculation.player_name}</p><p className="mt-1 font-display text-3xl font-bold text-lime">{calculation.total_points} pts</p></div><span className={`rounded-full px-3 py-1 text-[10px] font-bold ${calculation.complete ? "bg-lime/10 text-lime" : "bg-amber-400/10 text-amber-300"}`}>{calculation.complete ? "COMPLETE" : "INCOMPLETE"}</span></div><div className="mt-4 grid gap-2 sm:grid-cols-2">{entries.map((item) => <div key={`${item.category}-${item.label}`} className="flex justify-between rounded-md bg-ink/60 px-3 py-2 text-xs"><span className="capitalize text-slate-400">{item.label.replaceAll("_", " ")}</span><span className={item.points < 0 ? "text-red-300" : "text-slate-200"}>{item.points > 0 ? "+" : ""}{item.points}</span></div>)}</div>{!calculation.complete && <p className="mt-4 text-xs leading-5 text-amber-300">Missing: {calculation.missing_statistics.join(", ")}</p>}</div>; }

export default App;
