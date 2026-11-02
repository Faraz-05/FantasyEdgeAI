import json
from pathlib import Path

from backend.app.services.cricket_normalizer import normalize_scorecard_players
from backend.app.services.fantasy_points import FantasyPointsRequest, calculate_fantasy_points


FIXTURE = (
    Path(__file__).parents[1]
    / "app"
    / "data"
    / "demo"
    / "durham_warwickshire_scorecard.json"
)


def fixture_payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def by_name(players, name):
    return next(player for player in players if player["player_name"].strip() == name)


def test_fixture_parsing_and_player_identity():
    players = normalize_scorecard_players(fixture_payload())
    assert players
    assert all(player["player_id"] for player in players)
    assert by_name(players, "Graham Clark")["player_id"] == "7442a6e5-9d2b-4bdb-9d0b-37dc09797f40"


def test_batting_statistics_are_mapped():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Jacob Bethell")
    assert player["batting"]["runs"] == 21
    assert player["batting"]["balls_faced"] == 19
    assert player["batting"]["fours"] == 2
    assert player["batting"]["sixes"] == 0
    assert player["batting"]["dismissals"] == ["bowled"]
    assert player["fantasy_inputs"]["runs"] == 21


def test_player_names_are_trimmed_and_explicit_not_out_is_false():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Jacob Bethell")
    assert player["player_name"] == "Jacob Bethell"
    assert player["batting"]["dismissed"] is True

    not_out = by_name(normalize_scorecard_players(fixture_payload()), "Adam Hose")
    assert not_out["batting"]["dismissed"] is False


def test_missing_dismissal_remains_unknown():
    payload = {
        "data": {
            "scorecard": [{
                "batting": [{
                    "batsman": {"id": "player-1", "name": "  Unknown Status  "},
                    "r": 10,
                    "b": 10,
                }],
                "bowling": [],
                "catching": [],
            }]
        }
    }
    player = normalize_scorecard_players(payload)[0]
    assert player["player_name"] == "Unknown Status"
    assert player["batting"]["dismissed"] is None


def test_known_category_fantasy_totals_remain_unchanged_for_comparison_examples():
    players = normalize_scorecard_players(fixture_payload())
    totals = {}
    for name in ("Adam Hose", "Alex Davies"):
        player = by_name(players, name)
        result = calculate_fantasy_points(
            FantasyPointsRequest(
                player_name=name,
                role="batter",
                **player["fantasy_inputs"],
            )
        )
        totals[name] = result["subtotal"]

    assert totals == {"Adam Hose": 54, "Alex Davies": 93}


def test_bowling_statistics_and_lbw_bowled_attribution():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Ben Raine")
    assert player["bowling"]["overs_bowled"] == 4
    assert player["bowling"]["maiden_overs"] == 0
    assert player["bowling"]["runs_conceded"] == 22
    assert player["bowling"]["wickets"] == 2
    assert player["bowling"]["lbw_bowled_wickets"] == 2
    assert player["bowling"]["economy"] == 5.5


def test_catches_stumpings_and_runouts_are_mapped():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Sam Hain")
    assert player["fielding"]["catches"] == 2
    assert player["fielding"]["stumpings"] == 0
    assert player["fielding"]["runouts"] == 0
    assert player["fielding"]["direct_hit_run_outs"] is None
    assert player["fielding"]["other_run_outs"] is None

    runout_player = by_name(normalize_scorecard_players(fixture_payload()), "Adam Hose")
    assert runout_player["fielding"]["runouts"] == 1
    assert runout_player["fielding"]["catches"] == 0
    assert runout_player["fielding"]["stumpings"] == 0
    assert runout_player["fielding"]["direct_hit_run_outs"] is None
    assert runout_player["fielding"]["other_run_outs"] is None


def test_runouts_do_not_count_as_bowler_wickets():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Adam Hose")
    assert player["bowling"]["wickets"] is None
    assert player["bowling"]["lbw_bowled_wickets"] is None


def test_multiple_innings_aggregate_by_player_id_without_duplicates():
    players = normalize_scorecard_players(fixture_payload())
    ids = [player["player_id"] for player in players]
    assert len(ids) == len(set(ids))
    assert len(players) == 22


def test_missing_statistics_remain_unknown():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Graham Clark")
    assert player["bowling"]["dot_balls"] is None
    assert player["fielding"]["stumpings"] is None
    assert player["fantasy_inputs"]["announced_lineup"] is None
    assert player["fantasy_inputs"]["eligible_playing_substitute"] is None
    assert "runouts" not in player["fantasy_inputs"]
    assert "strike_rate" not in player["fantasy_inputs"]


def test_fantasy_inputs_preserve_available_zero_values_and_unknowns():
    players = normalize_scorecard_players(fixture_payload())
    batter = by_name(players, "Jacob Bethell")
    bowler = by_name(players, "Ben Raine")
    fielder = by_name(players, "Sam Hain")

    assert {
        key: batter["fantasy_inputs"][key]
        for key in ("runs", "fours", "sixes", "balls_faced", "dismissed")
    } == {
        "runs": 21,
        "fours": 2,
        "sixes": 0,
        "balls_faced": 19,
        "dismissed": True,
    }
    assert {
        key: bowler["fantasy_inputs"][key]
        for key in (
            "wickets",
            "lbw_bowled_wickets",
            "maiden_overs",
            "overs_bowled",
            "runs_conceded",
        )
    } == {
        "wickets": 2,
        "lbw_bowled_wickets": 2,
        "maiden_overs": 0,
        "overs_bowled": 4,
        "runs_conceded": 22,
    }
    assert fielder["fantasy_inputs"]["catches"] == 2
    assert fielder["fantasy_inputs"]["stumpings"] == 0
    assert fielder["fantasy_inputs"]["direct_hit_run_outs"] is None
    assert fielder["fantasy_inputs"]["other_run_outs"] is None


def test_multi_innings_values_are_aggregated_and_rates_recomputed():
    player = by_name(normalize_scorecard_players(fixture_payload()), "Alex Davies")
    assert player["fielding"]["catches"] == 2
    assert player["batting"]["runs"] == 49
    assert player["batting"]["balls_faced"] == 47
    assert player["batting"]["strike_rate"] == 49 * 100 / 47
