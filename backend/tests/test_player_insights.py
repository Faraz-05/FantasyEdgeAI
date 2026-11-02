import asyncio
import copy
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.routers import matches as matches_router
from backend.app.services.player_insights import build_player_insights
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


def player_id(name):
    player = next(
        player for player in normalize_scorecard_players(fixture_payload())
        if player["player_name"] == name
    )
    return player["player_id"]


def test_batting_and_bowling_contributions_are_structured():
    report = build_player_insights(fixture_payload(), player_id("Alex Davies"), role="batter")

    assert report["player"]["player_name"] == "Alex Davies"
    assert report["batting"]["source"]["runs"] == 49
    assert report["batting"]["derived"]["strike_rate"] == 49 * 100 / 47
    assert report["bowling"]["source"]["wickets"] is None
    assert report["fantasy_scoring"]["status"] == "incomplete"
    assert report["fantasy_scoring"]["result"] is not None


def test_batter_only_player_keeps_bowling_unavailable():
    report = build_player_insights(fixture_payload(), player_id("Adam Hose"), role="batter")

    assert report["batting"]["status"] == "available"
    assert report["bowling"]["status"] == "unavailable"
    assert report["bowling"]["derived"]["economy"] is None
    assert report["fantasy_scoring"]["status"] == "incomplete"


def test_bowler_only_player_exposes_bowling_derived_metrics():
    payload = copy.deepcopy(fixture_payload())
    payload["data"]["scorecard"] = [{
        "inning": "Warwickshire Inning 1",
        "batting": [],
        "bowling": [{
            "bowler": {
                "id": "bowler-only",
                "name": "Bowler Only",
            },
            "o": 4,
            "m": 0,
            "r": 22,
            "w": 2,
        }],
        "catching": [],
    }]
    report = build_player_insights(payload, "bowler-only", role="bowler")

    assert report["bowling"]["source"]["wickets"] == 2
    assert report["bowling"]["derived"]["overs_bowled"] == 4
    assert report["bowling"]["derived"]["economy"] == 5.5
    assert report["batting"]["status"] == "unavailable"


def test_fielding_contributions_preserve_unknown_runout_subtypes():
    report = build_player_insights(fixture_payload(), player_id("Sam Hain"))

    assert report["fielding"]["source"]["catches"] == 2
    assert report["fielding"]["source"]["stumpings"] == 0
    assert report["fielding"]["source"]["direct_hit_run_outs"] is None
    assert report["fielding"]["source"]["other_run_outs"] is None


def test_unknown_dismissal_and_missing_statistics_are_not_invented():
    payload = {
        "data": {
            "id": "match-1",
            "scorecard": [{
                "batting": [{
                    "batsman": {"id": "player-1", "name": "Unknown Status"},
                    "r": 10,
                    "b": 10,
                }],
                "bowling": [],
                "catching": [],
            }],
        }
    }
    report = build_player_insights(payload, "player-1")

    assert report["batting"]["source"]["dismissed"] is None
    assert "dismissed" not in report["batting"]["unavailable"] or report["batting"]["source"]["dismissed"] is None
    assert report["fantasy_scoring"]["status"] == "unavailable"
    assert report["fantasy_scoring"]["missing_statistics"] == ["role"]


def test_fantasy_result_reuses_existing_scoring_engine():
    report = build_player_insights(fixture_payload(), player_id("Adam Hose"), role="batter")
    normalized = next(
        player for player in normalize_scorecard_players(fixture_payload())
        if player["player_name"] == "Adam Hose"
    )
    expected = calculate_fantasy_points(
        FantasyPointsRequest(
            player_name="Adam Hose",
            role="batter",
            **normalized["fantasy_inputs"],
        )
    )

    assert report["fantasy_scoring"]["result"] == expected


def test_insights_endpoint_returns_demo_report_and_404s():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DEMO_MODE", "true")
    try:
        report = asyncio.run(matches_router.player_insights(
            "1f16f05e-e25c-43a1-ba00-331b1d2c3b8a",
            player_id("Ben Raine"),
            role="bowler",
            multiplier=1,
        ))
        assert report["source"] == "demo_fixture"
        assert report["player"]["player_name"] == "Ben Raine"

        with pytest.raises(HTTPException) as unknown_player:
            asyncio.run(matches_router.player_insights(
                "1f16f05e-e25c-43a1-ba00-331b1d2c3b8a",
                "unknown-player",
            ))
        assert unknown_player.value.status_code == 404

        with pytest.raises(HTTPException) as unknown_match:
            asyncio.run(matches_router.player_insights("unknown-match", "unknown-player"))
        assert unknown_match.value.status_code == 404
    finally:
        monkeypatch.undo()
