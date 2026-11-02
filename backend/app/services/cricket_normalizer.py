from typing import Any

from backend.app.services.cricket_utils import (
    balls_to_overs,
    overs_to_balls,
    rate_from_balls,
)

def _number(value: Any, number_type: type = int) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return number_type(value)
    return None


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def normalize_match(match: Any) -> dict[str, Any]:
    if not isinstance(match, dict):
        return {"id": None, "name": None, "date": None, "status": None, "match_type": None, "venue": None, "teams": [], "scores": []}
    teams = match.get("teams")
    scores = match.get("score")
    return {
        "id": _optional_string(match.get("id")),
        "name": _optional_string(match.get("name")),
        "date": _optional_string(match.get("date")),
        "status": _optional_string(match.get("status")),
        "match_type": _optional_string(match.get("matchType")),
        "venue": _optional_string(match.get("venue")),
        "teams": teams if isinstance(teams, list) else [],
        "scores": scores if isinstance(scores, list) else [],
    }


def normalize_match_list(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    matches = data if isinstance(data, list) else []
    return {
        "matches": [normalize_match(match) for match in matches],
        "provider_info": payload.get("info") if isinstance(payload.get("info"), dict) else {},
        "demo": payload.get("demo") is True,
        "source": _optional_string(payload.get("source")),
    }


def normalize_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {
            "match": None,
            "team_info": [],
            "scorecard": None,
            "provider_status": payload.get("status") if isinstance(payload.get("status"), str) else None,
            "provider_info": {},
            "demo": payload.get("demo") is True,
            "source": _optional_string(payload.get("source")),
        }
    return {
        "match": normalize_match(data),
        "team_info": data.get("teamInfo") if isinstance(data.get("teamInfo"), list) else [],
        "scorecard": data,
        "provider_status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "provider_info": payload.get("info") if isinstance(payload.get("info"), dict) else {},
        "demo": payload.get("demo") is True,
        "source": _optional_string(payload.get("source")),
    }


def _inning_team(label: Any) -> str | None:
    if not isinstance(label, str) or not label.strip():
        return None
    return label.strip().split(" Inning", 1)[0].strip() or None


def _verified_player_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def _verified_number(value: Any, number_type: type = int) -> int | float | None:
    return _number(value, number_type)


def normalize_momentum(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize scorecard-level momentum facts without inventing a timeline."""
        normalized = normalize_scorecard(payload)
        scorecard = normalized["scorecard"]
        innings_source = scorecard.get("scorecard") if isinstance(scorecard, dict) else None
        innings = innings_source if isinstance(innings_source, list) else []
        summary_scores = normalized["match"].get("scores", []) if normalized["match"] else []
        innings_summary: list[dict[str, Any]] = []
        batting_contributions: list[dict[str, Any]] = []
        bowling_contributions: list[dict[str, Any]] = []
        dismissal_events: list[dict[str, Any]] = []

        for index, inning in enumerate(innings):
            if not isinstance(inning, dict):
                continue
            totals = inning.get("totals") if isinstance(inning.get("totals"), dict) else {}
            summary_score = summary_scores[index] if index < len(summary_scores) and isinstance(summary_scores[index], dict) else {}
            runs = _verified_number(totals.get("R"), int)
            wickets = _verified_number(totals.get("W"), int)
            overs = _verified_number(totals.get("O"), float)
            run_rate = _verified_number(totals.get("RR"), float)
            if runs is None:
                runs = _verified_number(summary_score.get("r"), int)
            if wickets is None:
                wickets = _verified_number(summary_score.get("w"), int)
            if overs is None:
                overs = _verified_number(summary_score.get("o"), float)
            if run_rate is None:
                run_rate = rate_from_balls(runs, overs_to_balls(overs))
            label = inning.get("inning") or summary_score.get("inning")
            innings_summary.append({
                "innings_number": index + 1,
                "team": _inning_team(label) or None,
                "label": label if isinstance(label, str) else None,
                "runs": runs,
                "wickets": wickets,
                "overs": overs,
                "run_rate": run_rate,
                "target": None,
            })

            for row in inning.get("batting", []):
                if not isinstance(row, dict):
                    continue
                name = _verified_player_name(row.get("batsman"))
                if name:
                    batting_contributions.append({
                        "innings_number": index + 1,
                        "team": _inning_team(label),
                        "player_name": name,
                        "runs": _verified_number(row.get("r"), int),
                        "balls_faced": _verified_number(row.get("b"), int),
                        "fours": _verified_number(row.get("4s"), int),
                        "sixes": _verified_number(row.get("6s"), int),
                        "strike_rate": _verified_number(row.get("sr"), float),
                    })
                dismissal = row.get("dismissal")
                dismissal_text = row.get("dismissal-text")
                if name and (isinstance(dismissal, str) or isinstance(dismissal_text, str)):
                    dismissal_events.append({
                        "innings_number": index + 1,
                        "team": _inning_team(label),
                        "player_name": name,
                        "dismissal": dismissal if isinstance(dismissal, str) else None,
                        "description": dismissal_text if isinstance(dismissal_text, str) else None,
                    })

            for row in inning.get("bowling", []):
                if not isinstance(row, dict):
                    continue
                name = _verified_player_name(row.get("bowler"))
                if name:
                    bowling_contributions.append({
                        "innings_number": index + 1,
                        "team": _inning_team(label),
                        "player_name": name,
                        "overs": _verified_number(row.get("o"), float),
                        "maidens": _verified_number(row.get("m"), int),
                        "runs_conceded": _verified_number(row.get("r"), int),
                        "wickets": _verified_number(row.get("w"), int),
                        "economy": _verified_number(row.get("eco"), float),
                    })

        first_innings = innings_summary[0] if innings_summary else None
        first_innings_complete = bool(
            first_innings
            and first_innings["runs"] is not None
            and first_innings["wickets"] is not None
            and first_innings["overs"] is not None
        )
        if len(innings_summary) >= 2 and first_innings_complete:
            innings_summary[1]["target"] = innings_summary[0]["runs"] + 1

        match = normalized["match"] or {}
        return {
            "match": match,
            "demo": normalized["demo"],
            "source": normalized["source"],
            "provider_status": normalized["provider_status"],
            "provider_info": normalized["provider_info"],
            "result": {
                "status": match.get("status"),
                "winner": scorecard.get("matchWinner") if isinstance(scorecard, dict) else None,
            },
            "innings": innings_summary,
            "batting_contributions": batting_contributions,
            "bowling_contributions": bowling_contributions,
            "dismissal_events": dismissal_events,
            "availability": {
                "innings_progression": False,
                "ball_by_ball": False,
                "fall_of_wickets": False,
                "partnerships": False,
                "player_contributions": bool(batting_contributions or bowling_contributions),
                "dismissal_events": bool(dismissal_events),
            },
        }
def _identity(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, dict):
        return None
    player_id = _optional_string(value.get("id"))
    raw_name = value.get("name")
    player_name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    if not player_id and not player_name:
        return None
    return player_id or f"name:{player_name}", player_name or player_id or "Unknown player"


def _player_record(player_id: str, player_name: str) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "player_name": player_name,
        "role": None,
        "batting": {
            "runs": None,
            "balls_faced": None,
            "fours": None,
            "sixes": None,
            "strike_rate": None,
            "dismissed": None,
            "dismissals": [],
            "dismissal_texts": [],
        },
        "bowling": {
            "overs_bowled": None,
            "maiden_overs": None,
            "runs_conceded": None,
            "wickets": None,
            "economy": None,
            "lbw_bowled_wickets": None,
            "dot_balls": None,
        },
        "fielding": {
            "catches": None,
            "stumpings": None,
            "runouts": None,
            "direct_hit_run_outs": None,
            "other_run_outs": None,
        },
        "fantasy_inputs": {
            "runs": None,
            "fours": None,
            "sixes": None,
            "balls_faced": None,
            "dismissed": None,
            "dot_balls": None,
            "wickets": None,
            "lbw_bowled_wickets": None,
            "maiden_overs": None,
            "overs_bowled": None,
            "runs_conceded": None,
            "catches": None,
            "stumpings": None,
            "direct_hit_run_outs": None,
            "other_run_outs": None,
            "announced_lineup": None,
            "eligible_playing_substitute": None,
        },
    }


def _ensure_player(players: dict[str, dict[str, Any]], value: Any) -> dict[str, Any] | None:
    identity = _identity(value)
    if identity is None:
        return None
    player_id, player_name = identity
    if player_id not in players:
        players[player_id] = _player_record(player_id, player_name)
    elif players[player_id]["player_name"].startswith("name:") and player_name:
        players[player_id]["player_name"] = player_name
    return players[player_id]


def _add_number(target: dict[str, Any], key: str, value: Any, number_type: type = int) -> None:
    number = _number(value, number_type)
    if number is not None:
        target[key] = number if target[key] is None else target[key] + number


def _set_or_add_rate(target: dict[str, Any], key: str, value: Any) -> None:
    number = _number(value, float)
    if number is not None and target[key] is None:
        target[key] = number


_overs_to_balls = overs_to_balls
_balls_to_overs = balls_to_overs


def normalize_scorecard_players(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    innings = data.get("scorecard") if isinstance(data, dict) else None
    if not isinstance(innings, list):
        return []

    players: dict[str, dict[str, Any]] = {}
    bowling_balls: dict[str, int] = {}
    for inning in innings:
        if not isinstance(inning, dict):
            continue

        for row in inning.get("batting", []):
            if not isinstance(row, dict):
                continue
            player = _ensure_player(players, row.get("batsman"))
            if player is None:
                continue
            batting = player["batting"]
            for key, source in (
                ("runs", "r"),
                ("balls_faced", "b"),
                ("fours", "4s"),
                ("sixes", "6s"),
            ):
                _add_number(batting, key, row.get(source))
            dismissal = _optional_string(row.get("dismissal"))
            dismissal_text = _optional_string(row.get("dismissal-text"))
            if dismissal is not None:
                batting["dismissals"].append(dismissal)
                batting["dismissed"] = True
            elif dismissal_text is not None and dismissal_text.strip().lower() == "not out":
                batting["dismissed"] = False
            if dismissal_text is not None:
                batting["dismissal_texts"].append(dismissal_text)

            if dismissal in {"lbw", "bowled"}:
                bowler = _ensure_player(players, row.get("bowler"))
                if bowler is not None:
                    bowling = bowler["bowling"]
                    _add_number(bowling, "lbw_bowled_wickets", 1)

        for row in inning.get("bowling", []):
            if not isinstance(row, dict):
                continue
            player = _ensure_player(players, row.get("bowler"))
            if player is None:
                continue
            bowling = player["bowling"]
            overs_balls = _overs_to_balls(row.get("o"))
            if overs_balls is not None:
                player_id = player["player_id"]
                bowling_balls[player_id] = bowling_balls.get(player_id, 0) + overs_balls
            _add_number(bowling, "maiden_overs", row.get("m"))
            _add_number(bowling, "runs_conceded", row.get("r"))
            _add_number(bowling, "wickets", row.get("w"))

        for row in inning.get("catching", []):
            if not isinstance(row, dict):
                continue
            player = _ensure_player(players, row.get("catcher"))
            if player is None:
                continue
            fielding = player["fielding"]
            _add_number(fielding, "catches", row.get("catch"))
            _add_number(fielding, "stumpings", row.get("stumped"))
            _add_number(fielding, "runouts", row.get("runout"))

    for player_id, player in players.items():
        bowling = player["bowling"]
        if player_id in bowling_balls:
            bowling["overs_bowled"] = balls_to_overs(bowling_balls[player_id])
        batting = player["batting"]
        if batting["runs"] is not None and batting["balls_faced"]:
            batting["strike_rate"] = batting["runs"] * 100 / batting["balls_faced"]
        if bowling["runs_conceded"] is not None and player_id in bowling_balls:
            bowling["economy"] = rate_from_balls(
                bowling["runs_conceded"], bowling_balls[player_id]
            )
        fantasy_inputs = player["fantasy_inputs"]
        for key in (
            "runs",
            "fours",
            "sixes",
            "balls_faced",
            "dismissed",
        ):
            fantasy_inputs[key] = batting[key]
        for key in (
            "dot_balls",
            "wickets",
            "lbw_bowled_wickets",
            "maiden_overs",
            "overs_bowled",
            "runs_conceded",
        ):
            fantasy_inputs[key] = bowling[key]
        for key in (
            "catches",
            "stumpings",
            "direct_hit_run_outs",
            "other_run_outs",
        ):
            fantasy_inputs[key] = player["fielding"][key]

    return sorted(players.values(), key=lambda player: player["player_name"].strip().lower())
