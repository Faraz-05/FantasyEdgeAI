from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.services.cricket_utils import overs_to_balls, rate_from_balls

class PlayerRole(str, Enum):
    BATTER = "batter"
    BOWLER = "bowler"
    ALL_ROUNDER = "all_rounder"
    WICKETKEEPER = "wicketkeeper"


class FantasyPointsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_name: str = Field(min_length=1, max_length=100)
    role: PlayerRole
    runs: int | None = Field(default=None, ge=0)
    fours: int | None = Field(default=None, ge=0)
    sixes: int | None = Field(default=None, ge=0)
    balls_faced: int | None = Field(default=None, ge=0)
    dismissed: bool | None = None
    dot_balls: int | None = Field(default=None, ge=0)
    wickets: int | None = Field(default=None, ge=0)
    lbw_bowled_wickets: int | None = Field(default=None, ge=0)
    maiden_overs: int | None = Field(default=None, ge=0)
    overs_bowled: float | None = Field(default=None, ge=0)
    runs_conceded: int | None = Field(default=None, ge=0)
    catches: int | None = Field(default=None, ge=0)
    stumpings: int | None = Field(default=None, ge=0)
    direct_hit_run_outs: int | None = Field(default=None, ge=0)
    other_run_outs: int | None = Field(default=None, ge=0)
    announced_lineup: bool | None = None
    eligible_playing_substitute: bool | None = None
    multiplier: float = Field(default=1, gt=0, le=2)

    @model_validator(mode="after")
    def validate_match_stats(self) -> "FantasyPointsRequest":
        if self.fours is not None and self.sixes is not None and self.runs is not None:
            if self.fours * 4 + self.sixes * 6 > self.runs:
                raise ValueError("Boundary runs cannot exceed total runs")
        if self.lbw_bowled_wickets is not None and self.wickets is not None:
            if self.lbw_bowled_wickets > self.wickets:
                raise ValueError("LBW/bowled wickets cannot exceed total wickets")
        return self


@dataclass(frozen=True)
class ScoringRules:
    run: int = 1
    boundary_bonus: int = 4
    six_bonus: int = 6
    batting_milestones: tuple[tuple[int, int], ...] = (
        (25, 4),
        (50, 8),
        (75, 12),
        (100, 16),
    )
    duck: int = -2
    strike_rate_bands: tuple[tuple[float, float | None, int], ...] = (
        (170, None, 6),
        (150.01, 170, 4),
        (130, 150, 2),
        (60, 70, -2),
        (50, 59.99, -4),
        (float("-inf"), 50, -6),
    )
    dot_ball: int = 1
    wicket: int = 30
    lbw_bowled: int = 8
    wicket_bands: tuple[tuple[int, int], ...] = ((5, 12), (4, 8), (3, 4))
    maiden_over: int = 12
    economy_bands: tuple[tuple[float, float | None, int], ...] = (
        (float("-inf"), 4.99, 6),
        (5, 5.99, 4),
        (6, 7, 2),
        (10, 11, -2),
        (11.01, 12, -4),
        (12.01, None, -6),
    )
    catch: int = 8
    three_catch_bonus: int = 4
    stumping: int = 12
    direct_hit_run_out: int = 12
    other_run_out: int = 6
    announced_lineup: int = 4
    eligible_playing_substitute: int = 4


@dataclass
class _Calculation:
    breakdown: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {"batting": {}, "bowling": {}, "fielding": {}, "bonuses": {}}
    )
    points: int = 0
    missing: list[str] = field(default_factory=list)

    def add(self, category: str, label: str, points: int, detail: str) -> None:
        self.breakdown[category][label] = {"points": points, "detail": detail}
        self.points += points

    def require(self, value: Any, name: str) -> bool:
        if value is None:
            self.missing.append(name)
            return False
        return True


def _band_points(value: float, bands: tuple[tuple[float, float | None, int], ...]) -> int:
    for lower, upper, points in bands:
        if value >= lower and (upper is None or value <= upper):
            return points
    return 0


def calculate_fantasy_points(
    stats: FantasyPointsRequest, rules: ScoringRules | None = None
) -> dict[str, Any]:
    rules = rules or ScoringRules()
    result = _Calculation()
    role = stats.role
    bats = role in (PlayerRole.BATTER, PlayerRole.ALL_ROUNDER, PlayerRole.WICKETKEEPER)
    bowls = role in (PlayerRole.BOWLER, PlayerRole.ALL_ROUNDER)
    fields = True

    if bats:
        if stats.runs is not None:
            result.add("batting", "runs", stats.runs * rules.run, f"{stats.runs} runs x {rules.run}")
        else:
            result.require(stats.runs, "runs")
        if stats.fours is not None:
            result.add("batting", "boundary_bonus", stats.fours * rules.boundary_bonus, f"{stats.fours} fours x {rules.boundary_bonus}")
        else:
            result.require(stats.fours, "fours")
        if stats.sixes is not None:
            result.add("batting", "six_bonus", stats.sixes * rules.six_bonus, f"{stats.sixes} sixes x {rules.six_bonus}")
        else:
            result.require(stats.sixes, "sixes")

        if stats.runs is not None:
            milestone = next(
                ((threshold, points) for threshold, points in reversed(rules.batting_milestones) if stats.runs >= threshold),
                None,
            )
            if milestone:
                threshold, points = milestone
                result.add("batting", "milestone", points, f"{threshold}-run milestone")

        if stats.dismissed is not None and stats.runs is not None:
            if stats.dismissed and stats.runs == 0:
                result.add("batting", "duck", rules.duck, f"Dismissed for {stats.runs}")
        else:
            if stats.dismissed is None:
                result.require(stats.dismissed, "dismissed")
            if stats.runs is None:
                result.require(stats.runs, "runs")

        if stats.balls_faced is not None and stats.runs is not None:
            if stats.balls_faced >= 10 and stats.balls_faced > 0:
                strike_rate = stats.runs * 100 / stats.balls_faced
                points = _band_points(strike_rate, rules.strike_rate_bands)
                if points:
                    result.add("batting", "strike_rate", points, f"Strike rate {strike_rate:.2f}")
        else:
            if stats.balls_faced is None:
                result.require(stats.balls_faced, "balls_faced")
            if stats.runs is None:
                result.require(stats.runs, "runs")

    if bowls:
        for value, name in (
            (stats.dot_balls, "dot_balls"),
            (stats.wickets, "wickets"),
            (stats.lbw_bowled_wickets, "lbw_bowled_wickets"),
            (stats.maiden_overs, "maiden_overs"),
            (stats.overs_bowled, "overs_bowled"),
            (stats.runs_conceded, "runs_conceded"),
        ):
            result.require(value, name)
        if stats.dot_balls is not None:
            result.add("bowling", "dot_balls", stats.dot_balls * rules.dot_ball, f"{stats.dot_balls} dot balls x {rules.dot_ball}")
        if stats.wickets is not None:
            result.add("bowling", "wickets", stats.wickets * rules.wicket, f"{stats.wickets} wickets x {rules.wicket}")
            wicket_bonus = next((points for threshold, points in rules.wicket_bands if stats.wickets >= threshold), 0)
            if wicket_bonus:
                result.add("bowling", "wicket_haul", wicket_bonus, f"{stats.wickets}-wicket haul")
        if stats.lbw_bowled_wickets is not None:
            result.add("bowling", "lbw_bowled", stats.lbw_bowled_wickets * rules.lbw_bowled, f"{stats.lbw_bowled_wickets} LBW/bowled wickets x {rules.lbw_bowled}")
        if stats.maiden_overs is not None:
            result.add("bowling", "maiden_overs", stats.maiden_overs * rules.maiden_over, f"{stats.maiden_overs} maiden overs x {rules.maiden_over}")
        overs_balls = overs_to_balls(stats.overs_bowled)
        if overs_balls is not None and stats.runs_conceded is not None and overs_balls >= 12:
            economy = rate_from_balls(stats.runs_conceded, overs_balls)
            economy_points = _band_points(economy, rules.economy_bands)
            if economy_points:
                result.add("bowling", "economy", economy_points, f"Economy rate {economy:.2f}")
        elif overs_balls is not None and overs_balls < 12:
            result.breakdown["bowling"]["economy"] = {"points": 0, "detail": "Requires at least 2 overs"}

    for value, name, label, points in (
        (stats.catches, "catches", "catches", rules.catch),
        (stats.stumpings, "stumpings", "stumpings", rules.stumping),
        (stats.direct_hit_run_outs, "direct_hit_run_outs", "direct_hit_run_outs", rules.direct_hit_run_out),
        (stats.other_run_outs, "other_run_outs", "other_run_outs", rules.other_run_out),
    ):
        if fields:
            result.require(value, name)
        if value is not None:
            result.add("fielding", label, value * points, f"{value} x {points}")
    if stats.catches is not None and stats.catches >= 3:
        result.add("fielding", "three_catch_bonus", rules.three_catch_bonus, "Three-catch bonus awarded once")

    if stats.announced_lineup is None:
        result.require(stats.announced_lineup, "announced_lineup")
    elif stats.announced_lineup:
        result.add("bonuses", "announced_lineup", rules.announced_lineup, "Announced in lineup")
        if stats.eligible_playing_substitute:
            result.add(
                "bonuses",
                "eligible_playing_substitute",
                rules.eligible_playing_substitute,
                "Eligible playing substitute",
            )
    elif stats.eligible_playing_substitute is None:
        result.require(stats.eligible_playing_substitute, "eligible_playing_substitute")
    elif stats.eligible_playing_substitute:
        result.add(
            "bonuses",
            "eligible_playing_substitute",
            rules.eligible_playing_substitute,
            "Eligible playing substitute",
        )

    result.missing = sorted(set(result.missing))
    subtotal = result.points
    total = subtotal * stats.multiplier
    result.breakdown["bonuses"]["multiplier"] = {
        "points": total - subtotal,
        "detail": f"{subtotal} x {stats.multiplier:g}",
    }
    return {
        "player_name": stats.player_name,
        "role": role.value,
        "complete": not result.missing,
        "missing_statistics": result.missing,
        "breakdown": result.breakdown,
        "subtotal": subtotal,
        "multiplier": stats.multiplier,
        "total_points": total,
        "note": (
            "Exact Dream11-equivalent calculation is not claimed until all required "
            "statistics are supplied."
            if result.missing
            else "Calculation uses the configured T20 scoring rules."
        ),
    }
