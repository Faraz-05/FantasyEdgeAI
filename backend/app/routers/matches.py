import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.config import demo_mode_enabled
from backend.app.services.cricket_normalizer import (
    normalize_match_list,
    normalize_scorecard,
    normalize_scorecard_players,
    normalize_momentum,
)
from backend.app.services.cricket_demo import DemoCricketDataService
from backend.app.services.cricket_provider import CricketDataProvider, CricketProviderError
from backend.app.services.player_insights import build_player_insights

router = APIRouter(prefix="/api/matches", tags=["matches"])
logger = logging.getLogger(__name__)


class MomentumResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match: dict
    demo: bool
    source: str | None
    provider_status: str | None
    provider_info: dict
    result: dict
    innings: list[dict]
    batting_contributions: list[dict]
    bowling_contributions: list[dict]
    dismissal_events: list[dict]
    availability: dict[str, bool]


def _match_service() -> CricketDataProvider | DemoCricketDataService:
    if demo_mode_enabled():
        return DemoCricketDataService()
    return CricketDataProvider()


def _provider_error(error: CricketProviderError) -> HTTPException:
    logger.warning(
        "Cricket provider failure endpoint=%s http_status=%s provider_status=%s provider_message=%s",
        error.endpoint,
        error.http_status,
        error.provider_status,
        error.provider_message or error.provider_reason,
    )
    return HTTPException(status_code=502, detail=error.safe_detail())


@router.get("/live")
async def live_matches(offset: int = Query(default=0, ge=0)) -> dict:
    try:
        return normalize_match_list(await _match_service().live_matches(offset))
    except CricketProviderError as error:
        raise _provider_error(error) from error


@router.get("/recent")
async def recent_matches(offset: int = Query(default=0, ge=0)) -> dict:
    try:
        return normalize_match_list(await _match_service().recent_matches(offset))
    except CricketProviderError as error:
        raise _provider_error(error) from error


@router.get("/{match_id}/scorecard")
async def match_scorecard(match_id: str) -> dict:
    try:
        return normalize_scorecard(await _match_service().scorecard(match_id))
    except CricketProviderError as error:
        raise _provider_error(error) from error


@router.get("/{match_id}/players")
async def match_players(match_id: str) -> dict:
    try:
        payload = await _match_service().scorecard(match_id)
        normalized = normalize_scorecard(payload)
        return {
            "match": normalized["match"],
            "provider_status": normalized["provider_status"],
            "provider_info": normalized["provider_info"],
            "demo": normalized["demo"],
            "source": normalized["source"],
            "players": normalize_scorecard_players(payload),
        }
    except CricketProviderError as error:
        raise _provider_error(error) from error


@router.get("/{match_id}/players/{player_id}/insights")
async def player_insights(
    match_id: str,
    player_id: str,
    role: str | None = Query(default=None),
    multiplier: float = Query(default=1, gt=0, le=2),
) -> dict:
    try:
        payload = await _match_service().scorecard(match_id)
    except CricketProviderError as error:
        if error.provider_status == "demo" or error.http_status == 404:
            raise HTTPException(status_code=404, detail="Match not found.") from error
        raise _provider_error(error) from error

    effective_multiplier = multiplier if isinstance(multiplier, (int, float)) else 1
    report = build_player_insights(payload, player_id, role=role, multiplier=effective_multiplier)
    if report is None:
        raise HTTPException(status_code=404, detail="Player not found in the selected match.")
    return report


@router.get("/{match_id}/momentum", response_model=MomentumResponse)
async def match_momentum(match_id: str) -> dict:
    try:
        return normalize_momentum(await _match_service().scorecard(match_id))
    except CricketProviderError as error:
        raise _provider_error(error) from error
