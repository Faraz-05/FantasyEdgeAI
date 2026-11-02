import pytest
from pydantic import ValidationError

from backend.app.services.fantasy_points import FantasyPointsRequest, calculate_fantasy_points


def complete(**overrides):
    values = {
        "player_name": "Test Player",
        "role": "batter",
        "runs": 0,
        "fours": 0,
        "sixes": 0,
        "balls_faced": 10,
        "dismissed": False,
        "dot_balls": 0,
        "wickets": 0,
        "lbw_bowled_wickets": 0,
        "maiden_overs": 0,
        "overs_bowled": 0,
        "runs_conceded": 0,
        "catches": 0,
        "stumpings": 0,
        "direct_hit_run_outs": 0,
        "other_run_outs": 0,
        "announced_lineup": False,
        "eligible_playing_substitute": False,
    }
    values.update(overrides)
    return FantasyPointsRequest(**values)


def test_batter_scoring_40_runs():
    result = calculate_fantasy_points(complete(runs=40, fours=4, sixes=2, balls_faced=40))
    assert result["total_points"] == 72


def test_century_only_gets_highest_milestone():
    result = calculate_fantasy_points(complete(runs=100, fours=10, sixes=2, balls_faced=100))
    assert result["breakdown"]["batting"]["milestone"]["points"] == 16
    assert result["total_points"] == 168


def test_duck_for_dismissed_batter():
    result = calculate_fantasy_points(complete(runs=0, dismissed=True))
    assert result["breakdown"]["batting"]["duck"]["points"] == -2


def test_three_wickets():
    result = calculate_fantasy_points(complete(role="bowler", wickets=3))
    assert result["breakdown"]["bowling"]["wicket_haul"]["points"] == 4


def test_five_wickets():
    result = calculate_fantasy_points(complete(role="bowler", wickets=5))
    assert result["breakdown"]["bowling"]["wicket_haul"]["points"] == 12


def test_three_catches():
    result = calculate_fantasy_points(complete(catches=3))
    assert result["breakdown"]["fielding"]["three_catch_bonus"]["points"] == 4
    assert result["breakdown"]["fielding"]["catches"]["points"] == 24


@pytest.mark.parametrize("multiplier", [2, 1.5])
def test_captain_and_vice_captain_multipliers(multiplier):
    result = calculate_fantasy_points(complete(runs=10, multiplier=multiplier))
    assert result["total_points"] == result["subtotal"] * multiplier


def test_missing_statistics_are_reported():
    result = calculate_fantasy_points(
        FantasyPointsRequest(player_name="Incomplete", role="batter", runs=40, fours=4, sixes=2)
    )
    assert result["complete"] is False
    assert "balls_faced" in result["missing_statistics"]


def test_bowler_does_not_require_batting_statistics():
    result = calculate_fantasy_points(
        FantasyPointsRequest(
            player_name="Bowler",
            role="bowler",
            dot_balls=0,
            wickets=1,
            lbw_bowled_wickets=0,
            maiden_overs=0,
            overs_bowled=2,
            runs_conceded=12,
            catches=0,
            stumpings=0,
            direct_hit_run_outs=0,
            other_run_outs=0,
            announced_lineup=False,
            eligible_playing_substitute=False,
        )
    )
    assert result["complete"] is True
    assert "runs" not in result["missing_statistics"]
    assert "balls_faced" not in result["missing_statistics"]


def test_batter_does_not_require_bowling_statistics():
    result = calculate_fantasy_points(
        FantasyPointsRequest(
            player_name="Batter",
            role="batter",
            runs=40,
            fours=4,
            sixes=2,
            balls_faced=40,
            dismissed=False,
            catches=0,
            stumpings=0,
            direct_hit_run_outs=0,
            other_run_outs=0,
            announced_lineup=False,
            eligible_playing_substitute=False,
        )
    )
    assert result["complete"] is True
    assert "wickets" not in result["missing_statistics"]
    assert "overs_bowled" not in result["missing_statistics"]


@pytest.mark.parametrize("role", ["batter", "bowler", "all_rounder", "wicketkeeper"])
def test_completeness_is_role_aware_for_all_roles(role):
    values = {
        "player_name": role,
        "role": role,
        "catches": 0,
        "stumpings": 0,
        "direct_hit_run_outs": 0,
        "other_run_outs": 0,
        "announced_lineup": False,
        "eligible_playing_substitute": False,
    }
    if role in {"batter", "all_rounder", "wicketkeeper"}:
        values.update(runs=10, fours=1, sixes=0, balls_faced=10, dismissed=False)
    if role in {"bowler", "all_rounder"}:
        values.update(
            dot_balls=0,
            wickets=0,
            lbw_bowled_wickets=0,
            maiden_overs=0,
            overs_bowled=2,
            runs_conceded=12,
        )

    result = calculate_fantasy_points(FantasyPointsRequest(**values))

    assert result["complete"] is True
    if role == "bowler":
        assert "runs" not in result["missing_statistics"]
        assert "balls_faced" not in result["missing_statistics"]
    else:
        assert "wickets" not in result["missing_statistics"]
        assert "overs_bowled" not in result["missing_statistics"]


def test_all_rounder_requires_batting_and_bowling_statistics():
    result = calculate_fantasy_points(
        FantasyPointsRequest(
            player_name="All-rounder",
            role="all_rounder",
            runs=10,
            fours=1,
            sixes=0,
            balls_faced=10,
            dismissed=False,
            catches=0,
            stumpings=0,
            direct_hit_run_outs=0,
            other_run_outs=0,
            announced_lineup=False,
            eligible_playing_substitute=False,
        )
    )
    assert result["complete"] is False
    assert "wickets" in result["missing_statistics"]
    assert "overs_bowled" in result["missing_statistics"]


def test_announced_lineup_true_does_not_require_substitute_status():
    result = calculate_fantasy_points(
        complete(announced_lineup=True, eligible_playing_substitute=None)
    )

    assert result["complete"] is True
    assert result["breakdown"]["bonuses"]["announced_lineup"]["points"] == 4
    assert "eligible_playing_substitute" not in result["missing_statistics"]


def test_unannounced_player_with_unknown_substitute_status_is_incomplete():
    result = calculate_fantasy_points(
        complete(announced_lineup=False, eligible_playing_substitute=None)
    )

    assert result["complete"] is False
    assert "eligible_playing_substitute" in result["missing_statistics"]
    assert "announced_lineup" not in result["missing_statistics"]


def test_unannounced_eligible_substitute_receives_substitute_bonus():
    result = calculate_fantasy_points(
        complete(announced_lineup=False, eligible_playing_substitute=True)
    )

    assert result["complete"] is True
    assert result["breakdown"]["bonuses"]["eligible_playing_substitute"]["points"] == 4


def test_unknown_run_out_statistics_remain_incomplete():
    result = calculate_fantasy_points(
        complete(direct_hit_run_outs=None, other_run_outs=None)
    )

    assert result["complete"] is False
    assert "direct_hit_run_outs" in result["missing_statistics"]
    assert "other_run_outs" in result["missing_statistics"]
    assert "direct_hit_run_outs" not in result["breakdown"]["fielding"]
    assert "other_run_outs" not in result["breakdown"]["fielding"]


def test_run_out_fielding_does_not_awARD_bowler_wicket_points():
    result = calculate_fantasy_points(
        FantasyPointsRequest(
            player_name="Fielder Bowler",
            role="bowler",
            dot_balls=0,
            wickets=0,
            lbw_bowled_wickets=0,
            maiden_overs=0,
            overs_bowled=2,
            runs_conceded=12,
            catches=0,
            stumpings=0,
            direct_hit_run_outs=1,
            other_run_outs=0,
            announced_lineup=False,
            eligible_playing_substitute=False,
        )
    )
    assert result["breakdown"]["bowling"]["wickets"]["points"] == 0
    assert result["breakdown"]["fielding"]["direct_hit_run_outs"]["points"] == 12


@pytest.mark.parametrize(
    ("runs", "balls", "expected"),
    [(4, 10, -6), (5, 10, -4), (13, 10, 2), (18, 10, 6)],
)
def test_strike_rate_boundaries(runs, balls, expected):
    result = calculate_fantasy_points(complete(runs=runs, balls_faced=balls))
    assert result["breakdown"]["batting"]["strike_rate"]["points"] == expected


@pytest.mark.parametrize(
    ("runs_conceded", "expected"),
    [(8, 6), (10, 4), (12, 2), (20, -2), (23, -4), (25, -6)],
)
def test_economy_boundaries(runs_conceded, expected):
    result = calculate_fantasy_points(
        complete(
            role="bowler",
            runs_conceded=runs_conceded,
            overs_bowled=2,
        )
    )
    assert result["breakdown"]["bowling"]["economy"]["points"] == expected


def test_invalid_input():
    with pytest.raises(ValidationError):
        FantasyPointsRequest(
            player_name="Invalid",
            role="batter",
            runs=2,
            fours=1,
            sixes=1,
        )
