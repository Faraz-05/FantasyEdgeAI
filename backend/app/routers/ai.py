from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.services.gemini_service import AnalystResponse, GeminiServiceError, analyze_comparison, analyze_player

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AnalyzePlayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_name: str = Field(min_length=1, max_length=200)
    player_name: str = Field(min_length=1, max_length=100)
    player_role: str = Field(min_length=1, max_length=30)
    batting_statistics: dict[str, Any] = Field(default_factory=dict)
    bowling_statistics: dict[str, Any] = Field(default_factory=dict)
    fielding_statistics: dict[str, Any] = Field(default_factory=dict)
    fantasy_points_total: int | float
    scoring_breakdown: dict[str, Any]
    calculation_complete: bool
    missing_statistics: list[str] = Field(default_factory=list, max_length=30)
    demo_fixture: bool = False

    @model_validator(mode="after")
    def limit_structured_input(self) -> "AnalyzePlayerRequest":
        supplied = (
            self.batting_statistics,
            self.bowling_statistics,
            self.fielding_statistics,
            self.scoring_breakdown,
        )
        if sum(len(str(value)) for value in supplied) > 20000:
            raise ValueError("Analysis input is too large")
        return self


class ComparisonPlayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_name: str = Field(min_length=1, max_length=100)
    player_role: str = Field(min_length=1, max_length=30)
    batting_statistics: dict[str, Any] = Field(default_factory=dict)
    bowling_statistics: dict[str, Any] = Field(default_factory=dict)
    fielding_statistics: dict[str, Any] = Field(default_factory=dict)
    fantasy_points_total: int | float
    scoring_breakdown: dict[str, Any]
    calculation_complete: bool
    missing_statistics: list[str] = Field(default_factory=list, max_length=30)


class AnalyzeComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_name: str = Field(min_length=1, max_length=200)
    player_a: ComparisonPlayerRequest
    player_b: ComparisonPlayerRequest
    demo_fixture: bool = False

    @model_validator(mode="after")
    def validate_players(self) -> "AnalyzeComparisonRequest":
        if self.player_a.player_name.strip() == self.player_b.player_name.strip():
            raise ValueError("Comparison requires two different players")
        if sum(len(str(value)) for value in (self.player_a, self.player_b)) > 30000:
            raise ValueError("Comparison input is too large")
        return self


@router.post("/analyze-player", response_model=AnalystResponse)
async def analyze_player_route(request: AnalyzePlayerRequest) -> AnalystResponse | JSONResponse:
    try:
        return await analyze_player(request)
    except GeminiServiceError as error:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                }
            },
        )


@router.post("/analyze-comparison", response_model=AnalystResponse)
async def analyze_comparison_route(request: AnalyzeComparisonRequest) -> AnalystResponse | JSONResponse:
    try:
        return await analyze_comparison(request)
    except GeminiServiceError as error:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                }
            },
        )
