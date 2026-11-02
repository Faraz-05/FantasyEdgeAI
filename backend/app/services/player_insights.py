from typing import Any

from pydantic import ValidationError

from backend.app.services.cricket_normalizer import (
    normalize_match,
    normalize_scorecard_players,
)
from backend.app.services.fantasy_points import FantasyPointsRequest, calculate_fantasy_points


_BATTER_SOURCE_FIELDS = (
    "runs",
    "balls_faced",
    "fours",
    "sixes",
    "dismissed",
    "dismissals",
    "dismissal_texts",
)
_BOWLER_SOURCE_FIELDS = (
    "maiden_overs",
    "runs_conceded",
    "wickets",
    "lbw_bowled_wickets",
    "dot_balls",
)
_FIELDING_SOURCE_FIELDS = (
    "catches",
    "stumpings",
    "runouts",
    "direct_hit_run_outs",
    "other_run_outs",
)


def _section(
    stats: dict[str, Any],
    source_fields: tuple[str, ...],
    derived_fields: tuple[str, ...],
) -> dict[str, Any]:
    source = {field: stats.get(field) for field in source_fields}
    derived = {field: stats.get(field) for field in derived_fields}
    def is_known(value: Any) -> bool:
        return value is not None and (not isinstance(value, list) or bool(value))

    values = {**source, **derived}
    known = sum(is_known(value) for value in values.values())
    unavailable = [
        field
        for field, value in values.items()
        if value is None or (known == 0 and isinstance(value, list) and not value)
    ]
    return {
        "source": source,
        "derived": derived,
        "unavailable": unavailable,
        "status": "unavailable" if known == 0 else "partial" if unavailable else "available",
    }


def _fantasy_report(player: dict[str, Any], role: str | None, multiplier: float) -> dict[str, Any]:
    if not role:
        return {
            "status": "unavailable",
            "role": None,
            "result": None,
            "missing_statistics": ["role"],
            "message": "Fantasy points require an explicit player role.",
        }

    try:
        request = FantasyPointsRequest(
            player_name=player["player_name"],
            role=role,
            **player["fantasy_inputs"],
            multiplier=multiplier,
        )
    except ValidationError as error:
        missing = sorted({
            str(item["loc"][0])
            for item in error.errors()
            if item.get("type") == "missing"
        })
        return {
            "status": "incomplete",
            "role": role,
            "result": None,
            "missing_statistics": missing,
            "message": "Fantasy points are unavailable because the supplied statistics are invalid or incomplete.",
        }

    result = calculate_fantasy_points(request)
    return {
        "status": "complete" if result["complete"] else "incomplete",
        "role": role,
        "result": result,
        "missing_statistics": result["missing_statistics"],
        "message": None if result["complete"] else result["note"],
    }


def build_player_insights(
    payload: dict[str, Any],
    player_id: str,
    role: str | None = None,
    multiplier: float = 1,
) -> dict[str, Any] | None:
    """Build a transparent insight report from one normalized scorecard."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None

    players = normalize_scorecard_players(payload)
    player = next((item for item in players if item["player_id"] == player_id), None)
    if player is None:
        return None

    match = normalize_match(data)
    batting = _section(
        player["batting"],
        _BATTER_SOURCE_FIELDS,
        ("strike_rate",),
    )
    bowling = _section(
        player["bowling"],
        _BOWLER_SOURCE_FIELDS,
        ("overs_bowled", "economy"),
    )
    fielding = _section(player["fielding"], _FIELDING_SOURCE_FIELDS, ())
    fantasy = _fantasy_report(player, role, multiplier)
    return {
        "match": match,
        "demo": payload.get("demo") is True,
        "source": payload.get("source") if isinstance(payload.get("source"), str) else None,
        "provider_status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "player": {
            "player_id": player["player_id"],
            "player_name": player["player_name"],
            "role": player.get("role"),
        },
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "fantasy_scoring": fantasy,
        "availability": {
            "batting": batting["status"],
            "bowling": bowling["status"],
            "fielding": fielding["status"],
            "fantasy_scoring": fantasy["status"],
        },
    }
