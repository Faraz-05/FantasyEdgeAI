import asyncio
import json

import pytest
from pydantic import ValidationError

from backend.app.routers.ai import AnalyzeComparisonRequest, AnalyzePlayerRequest, analyze_player_route, analyze_comparison_route
from backend.app.services import gemini_service
from backend.app.services.cricket_normalizer import normalize_scorecard_players


def request(**overrides):
    values = {
        "match_name": "Durham vs Warwickshire",
        "player_name": "Ben Raine",
        "player_role": "bowler",
        "batting_statistics": {"runs": None},
        "bowling_statistics": {"wickets": 2, "overs_bowled": 4},
        "fielding_statistics": {"catches": 0},
        "fantasy_points_total": 76,
        "scoring_breakdown": {"bowling": {"wickets": {"points": 60}}},
        "calculation_complete": False,
        "missing_statistics": ["dot_balls"],
        "demo_fixture": True,
    }
    values.update(overrides)
    return AnalyzePlayerRequest(**values)


def response_text(summary="Recovered."):
    return json.dumps({
        "summary": summary,
        "batting_analysis": "Unavailable.",
        "bowling_analysis": "Two wickets.",
        "fielding_analysis": "Known zero catches.",
        "fantasy_points_explanation": "Python total is unchanged.",
        "data_limitations": [],
    })


def fixture_fielding(name):
    from pathlib import Path

    import json

    fixture = (
        Path(__file__).parents[1]
        / "app"
        / "data"
        / "demo"
        / "durham_warwickshire_scorecard.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return next(
        player["fielding"]
        for player in normalize_scorecard_players(payload)
        if player["player_name"].strip() == name
    )


def async_client(generate):
    class AsyncModels:
        async def generate_content(self, **kwargs):
            return await generate(**kwargs)

    class Aio:
        models = AsyncModels()

    class Client:
        aio = Aio()

    return Client


def test_request_schema_accepts_bounded_analysis_input():
    assert request().fantasy_points_total == 76


def test_comparison_request_rejects_duplicate_players():
    player = {
        "player_name": "Same",
        "player_role": "batter",
        "fantasy_points_total": 1,
        "scoring_breakdown": {},
        "calculation_complete": False,
    }
    with pytest.raises(ValidationError):
        AnalyzeComparisonRequest(
            match_name="Demo",
            player_a=player,
            player_b=player,
        )


def test_comparison_endpoint_does_not_call_gemini_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    player = {
        "player_name": "Player",
        "player_role": "batter",
        "fantasy_points_total": 1,
        "scoring_breakdown": {},
        "calculation_complete": False,
    }
    response = asyncio.run(analyze_comparison_route(AnalyzeComparisonRequest(
        match_name="Demo",
        player_a={**player, "player_name": "A"},
        player_b={**player, "player_name": "B"},
        demo_fixture=True,
    )))
    assert response.status_code == 503
    assert json.loads(response.body)["error"]["code"] == "missing_api_key"


def test_request_schema_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        request(untrusted_secret="should fail")


def test_request_schema_rejects_oversized_structured_input():
    with pytest.raises(ValidationError):
        request(scoring_breakdown={"data": "x" * 20001})


def test_missing_gemini_key_is_handled(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = asyncio.run(analyze_player_route(request()))
    assert response.status_code == 503
    assert json.loads(response.body)["error"]["code"] == "missing_api_key"


def test_async_gemini_success_and_sdk_configuration(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    captured = {}

    async def generate(**kwargs):
        captured["request"] = kwargs

        class Response:
            text = response_text()

        return Response()

    def make_client(**kwargs):
        captured["client"] = kwargs
        return async_client(generate)()

    monkeypatch.setattr(gemini_service.genai, "Client", make_client)
    result = asyncio.run(analyze_player_route(request()))

    assert result.summary == "Recovered."
    assert "76" in captured["request"]["contents"]
    options = captured["client"]["http_options"]
    assert options.timeout == 20000
    assert options.retry_options.attempts == 3
    assert options.retry_options.http_status_codes == [408, 429, 503, 504]


def test_fielding_facts_preserve_zero_and_unknown_values():
    fielding = fixture_fielding("Adam Hose")
    facts, limitations = gemini_service._fielding_facts(fielding)

    assert facts == {
        "Catches": 0,
        "Stumpings": 0,
        "Run-outs": 1,
        "Direct-hit run-outs": "unavailable",
        "Other run-outs": "unavailable",
    }
    assert limitations == [
        "Direct-hit run-outs were not available in the source data.",
        "Other run-outs were not available in the source data.",
    ]


def test_prompt_contains_deterministic_fielding_facts_and_zero_rules():
    fielding = fixture_fielding("Adam Hose")
    prompt = gemini_service._prompt(request(fielding_statistics=fielding))

    assert '"Catches":0' in prompt
    assert '"Stumpings":0' in prompt
    assert '"Run-outs":1' in prompt
    assert '"Direct-hit run-outs":"unavailable"' in prompt
    assert '"Other run-outs":"unavailable"' in prompt
    assert "never describe a known zero as unavailable" in prompt
    assert "never infer direct-hit or other run-out classifications" in prompt


def test_fielding_limitations_are_deterministic_and_do_not_include_known_zeros(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def generate(**kwargs):
        class Response:
            text = response_text()

        return Response()

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    response = asyncio.run(
        analyze_player_route(
            request(fielding_statistics=fixture_fielding("Adam Hose"))
        )
    )
    assert response.data_limitations == [
        "Direct-hit run-outs were not available in the source data.",
        "Other run-outs were not available in the source data.",
    ]


def test_redundant_general_runout_limitation_is_removed(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def generate(**kwargs):
        class Response:
            text = response_text()

        payload = json.loads(Response.text)
        payload["data_limitations"] = [
            "Specific runout classifications (direct-hit vs other) are unavailable.",
            "Bowling statistics were not available in the source fixture.",
        ]
        Response.text = json.dumps(payload)
        return Response()

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    response = asyncio.run(
        analyze_player_route(
            request(fielding_statistics=fixture_fielding("Adam Hose"))
        )
    )
    assert response.data_limitations == [
        "Direct-hit run-outs were not available in the source data.",
        "Other run-outs were not available in the source data.",
        "Bowling statistics were not available in the source fixture.",
    ]
    assert not any(
        "specific runout classification" in item.casefold()
        for item in response.data_limitations
    )


def test_sdk_transient_error_is_handled_without_application_retry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = 0

    async def generate(**kwargs):
        nonlocal calls
        calls += 1

        class TemporaryUnavailable(Exception):
            code = 503

        raise TemporaryUnavailable("UNAVAILABLE")

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    response = asyncio.run(analyze_player_route(request()))

    assert response.status_code == 503
    assert json.loads(response.body)["error"]["code"] == "temporary_unavailable"
    assert calls == 1


def test_overall_deadline_is_enforced(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    started = asyncio.Event()

    async def generate(**kwargs):
        started.set()
        await asyncio.sleep(10)

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    monkeypatch.setattr(gemini_service, "_OVERALL_DEADLINE_SECONDS", 0.01)
    response = asyncio.run(analyze_player_route(request()))

    assert response.status_code == 503
    body = json.loads(response.body)
    assert body["error"]["code"] == "timeout"
    assert body["error"]["retryable"] is True
    assert started.is_set()


def test_inflight_request_cleanup_after_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def generate(**kwargs):
        raise ValueError("unsupported model")

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    first = asyncio.run(analyze_player_route(request()))
    assert first.status_code == 503
    assert not gemini_service._analysis_tasks


def test_inflight_request_cleanup_after_cancellation(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    cancelled = asyncio.Event()

    async def generate(**kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )

    async def run():
        task = asyncio.create_task(gemini_service.analyze_player(request()))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert cancelled.is_set()
    assert not gemini_service._analysis_tasks


def test_malformed_response_is_handled(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    async def generate(**kwargs):
        class Response:
            text = '{"summary": "incomplete"}'

        return Response()

    monkeypatch.setattr(
        gemini_service.genai,
        "Client",
        lambda **kwargs: async_client(generate)(),
    )
    response = asyncio.run(analyze_player_route(request()))
    assert response.status_code == 503
    assert json.loads(response.body)["error"]["code"] == "invalid_response"
