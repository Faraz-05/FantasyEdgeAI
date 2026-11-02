import asyncio
import hashlib
import json
import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiServiceError(Exception):
    """Raised when Gemini is unavailable or returns an unusable response."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "gemini_unavailable",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class AnalystResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=4000)
    batting_analysis: str = Field(min_length=1, max_length=4000)
    bowling_analysis: str = Field(min_length=1, max_length=4000)
    fielding_analysis: str = Field(min_length=1, max_length=4000)
    fantasy_points_explanation: str = Field(min_length=1, max_length=4000)
    data_limitations: list[str] = Field(default_factory=list, max_length=20)


_SDK_RETRY_ATTEMPTS = 3
_SDK_TIMEOUT_MS = 20000
_OVERALL_DEADLINE_SECONDS = 90
_TRANSIENT_STATUS_CODES = {408, 429, 503, 504}
_analysis_tasks: dict[str, asyncio.Task[AnalystResponse]] = {}


def _fielding_facts(fielding: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    labels = (
        ("catches", "Catches"),
        ("stumpings", "Stumpings"),
        ("runouts", "Run-outs"),
        ("direct_hit_run_outs", "Direct-hit run-outs"),
        ("other_run_outs", "Other run-outs"),
    )
    facts: dict[str, Any] = {}
    limitations: list[str] = []
    for key, label in labels:
        value = fielding.get(key)
        if value is None:
            facts[label] = "unavailable"
            limitations.append(f"{label} were not available in the source data.")
        else:
            facts[label] = value
    return facts, limitations


def _merge_limitations(
    deterministic: list[str], generated: list[str], fielding: dict[str, Any]
) -> list[str]:
    specific_runout_limits = (
        fielding.get("direct_hit_run_outs") is None
        and fielding.get("other_run_outs") is None
    )
    merged: list[str] = []
    seen: set[str] = set()
    for limitation in [*deterministic, *generated]:
        cleaned = limitation.strip()
        normalized = re.sub(r"\s+", " ", cleaned).casefold()
        if not cleaned or normalized in seen:
            continue
        if specific_runout_limits and (
            "specific runout classification" in normalized
            or "specific run-out classification" in normalized
            or "direct-hit vs other" in normalized
            or "direct hit vs other" in normalized
        ):
            continue
        seen.add(normalized)
        merged.append(cleaned)
    return merged


def _prompt(request: Any) -> str:
    fielding_facts, _ = _fielding_facts(request.fielding_statistics)
    facts = {
        "match_name": request.match_name,
        "player_name": request.player_name,
        "player_role": request.player_role,
        "batting_statistics": request.batting_statistics,
        "bowling_statistics": request.bowling_statistics,
        "fielding_statistics": request.fielding_statistics,
        "fielding_facts": fielding_facts,
        "python_fantasy_points_total": request.fantasy_points_total,
        "python_scoring_breakdown": request.scoring_breakdown,
        "calculation_complete": request.calculation_complete,
        "missing_statistics": request.missing_statistics,
        "demo_fixture": request.demo_fixture,
    }
    return (
        "You are the FantasyEdge AI match and player analyst. Use only the supplied "
        "facts. Do not calculate, change, reinterpret, or recommend fantasy points; "
        "repeat the Python-generated total and explain its supplied breakdown. Treat "
        "numeric 0 as a known and verified zero. Treat null or absent statistics as "
        "unknown or unavailable, never as zero, and never describe a known zero as "
        "unavailable. Aggregate runouts must be reported only as aggregate runouts; "
        "never infer direct-hit or other run-out classifications from them. Use only "
        "the supplied facts. "
        "Do not predict future performance, recommend teams, or guarantee outcomes. "
        "If demo_fixture is true, explicitly say the source is a local fixture and "
        "not live/current. Return only valid JSON with exactly these keys: "
        "summary, batting_analysis, bowling_analysis, fielding_analysis, "
        "fantasy_points_explanation, data_limitations. Each analysis value must be "
        "a concise string and data_limitations must be a string array.\n\n"
        f"SUPPLIED FACTS:\n{json.dumps(facts, separators=(',', ':'), default=str)}"
    )


def _comparison_prompt(request: Any) -> str:
    facts = {
        "match_name": request.match_name,
        "player_a": request.player_a.model_dump(),
        "player_b": request.player_b.model_dump(),
        "demo_fixture": request.demo_fixture,
    }
    return (
        "You are the FantasyEdge AI comparison analyst. Compare only the two supplied "
        "players using the verified statistics and Python-generated fantasy totals. "
        "Do not calculate, change, reinterpret, predict, recommend, or invent facts. "
        "Treat numeric 0 as known and null or absent values as unavailable, never zero. "
        "Do not suggest a fantasy team or future performance. If demo_fixture is true, "
        "explicitly say the source is a local fixture and not live/current. Return only "
        "valid JSON with exactly these keys: summary, batting_analysis, bowling_analysis, "
        "fielding_analysis, fantasy_points_explanation, data_limitations. Each analysis "
        "value must be a concise string and data_limitations must be a string array.\n\n"
        f"SUPPLIED FACTS:\n{json.dumps(facts, separators=(',', ':'), default=str)}"
    )


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    raise GeminiServiceError("Gemini returned an empty response")


async def analyze_player(request: Any) -> AnalystResponse:
    key = hashlib.sha256(_prompt(request).encode("utf-8")).hexdigest()
    existing = _analysis_tasks.get(key)
    if existing is not None:
        return await asyncio.shield(existing)

    task = asyncio.create_task(_analyze_player_with_deadline(request))
    _analysis_tasks[key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if _analysis_tasks.get(key) is task:
            _analysis_tasks.pop(key, None)


async def _analyze_player_with_deadline(request: Any) -> AnalystResponse:
    try:
        async with asyncio.timeout(_OVERALL_DEADLINE_SECONDS):
            return await _analyze_player_once(request)
    except TimeoutError as error:
        raise GeminiServiceError(
            "Gemini analysis exceeded the 90-second deadline. Please try again.",
            code="timeout",
            retryable=True,
        ) from error


async def _analyze_player_once(request: Any) -> AnalystResponse:
    return await _analyze_prompt(_prompt(request), request.fielding_statistics)


async def analyze_comparison(request: Any) -> AnalystResponse:
    key = hashlib.sha256(_comparison_prompt(request).encode("utf-8")).hexdigest()
    existing = _analysis_tasks.get(key)
    if existing is not None:
        return await asyncio.shield(existing)
    task = asyncio.create_task(_analyze_comparison_with_deadline(request))
    _analysis_tasks[key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if _analysis_tasks.get(key) is task:
            _analysis_tasks.pop(key, None)


async def _analyze_comparison_with_deadline(request: Any) -> AnalystResponse:
    try:
        async with asyncio.timeout(_OVERALL_DEADLINE_SECONDS):
            return await _analyze_prompt(_comparison_prompt(request), {
                **request.player_a.fielding_statistics,
                **request.player_b.fielding_statistics,
            })
    except TimeoutError as error:
        raise GeminiServiceError(
            "Gemini analysis exceeded the 90-second deadline. Please try again.",
            code="timeout",
            retryable=True,
        ) from error


async def _analyze_prompt(prompt: str, fielding_statistics: dict[str, Any]) -> AnalystResponse:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiServiceError(
            "Gemini analysis is unavailable because GEMINI_API_KEY is not configured.",
            code="missing_api_key",
        )
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    if not model:
        raise GeminiServiceError(
            "Gemini analysis is unavailable because GEMINI_MODEL is empty.",
            code="missing_model",
        )

    if genai is None or types is None:
        raise GeminiServiceError(
            "Gemini analysis is unavailable because the google-genai package is not installed.",
            code="sdk_unavailable",
        )

    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=_SDK_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=_SDK_RETRY_ATTEMPTS,
                    initial_delay=1,
                    max_delay=8,
                    exp_base=2,
                    jitter=1,
                    http_status_codes=[408, 429, 503, 504],
                ),
            ),
        )
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        analyst = AnalystResponse.model_validate_json(_response_text(response))
        _, fielding_limitations = _fielding_facts(fielding_statistics)
        limitations = _merge_limitations(
            fielding_limitations,
            analyst.data_limitations,
            fielding_statistics,
        )
        return analyst.model_copy(update={"data_limitations": limitations})
    except (ValidationError, json.JSONDecodeError) as error:
        raise GeminiServiceError(
            "Gemini returned an invalid structured response.",
            code="invalid_response",
        ) from error
    except GeminiServiceError:
        raise
    except asyncio.TimeoutError as error:
        raise GeminiServiceError(
            "Gemini request timed out after 20 seconds. Please try again.",
            code="timeout",
            retryable=True,
        ) from error
    except Exception as error:
        message = str(error).replace(api_key, "[redacted]")
        status_code = getattr(error, "code", None)
        if status_code in _TRANSIENT_STATUS_CODES:
            raise GeminiServiceError(
                "Gemini is temporarily unavailable after bounded retries "
                f"(HTTP {status_code}). Please try again shortly.",
                code="temporary_unavailable",
                retryable=True,
            ) from error
        code = "authentication_failed" if status_code in {401, 403} else "request_failed"
        raise GeminiServiceError(
            f"Gemini analysis request failed: {message[:300]}",
            code=code,
        ) from error
