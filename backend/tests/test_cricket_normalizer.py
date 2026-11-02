import asyncio

import httpx
import pytest

from backend.app.services.cricket_normalizer import (
    normalize_match_list,
    normalize_momentum,
    normalize_scorecard,
)
from backend.app.services.cricket_utils import overs_to_balls, rate_from_balls
from backend.app.services.cricket_provider import (
    _CACHE_TTLS,
    CricketDataProvider,
    CricketProviderError,
    _response_cache,
)

def test_normalize_match_list_preserves_unknown_optional_values():
    result = normalize_match_list(
        {
            "status": "success",
            "data": [
                {
                    "id": "match-1",
                    "name": "Team A vs Team B",
                    "date": "2026-11-01T10:00:00Z",
                    "status": "Live",
                    "matchType": "T20",
                    "teams": ["Team A", "Team B"],
                    "score": [{"r": 42, "w": 2, "o": 6.4}],
                }
            ],
        }
    )
    match = result["matches"][0]
    assert match["id"] == "match-1"
    assert match["venue"] is None
    assert match["scores"][0]["r"] == 42


def test_normalize_scorecard_keeps_provider_scorecard_without_inventing_stats():
    result = normalize_scorecard(
        {
            "status": "success",
            "data": {
                "id": "match-1",
                "name": "Team A vs Team B",
                "teamInfo": [{"name": "Team A", "shortname": "A"}],
                "scorecard": [{"batteam": "Team A"}],
            },
        }
    )
    assert result["match"]["id"] == "match-1"
    assert result["provider_status"] == "success"
    assert result["team_info"][0]["shortname"] == "A"
    assert result["scorecard"]["scorecard"][0]["batteam"] == "Team A"


def test_normalize_momentum_handles_missing_scorecard_fields_without_inventing_values():
    result = normalize_momentum({
        "status": "success",
        "data": {
            "id": "match-1",
            "name": "Team A vs Team B",
            "score": [{"r": 40, "w": 2, "o": 6.4, "inning": "Team A Inning 1"}],
            "scorecard": [{"inning": "Team A Inning 1", "batting": [], "bowling": []}],
            "matchWinner": None,
        },
        "demo": True,
        "source": "demo_fixture",
    })
    assert result["innings"][0]["runs"] == 40
    assert result["innings"][0]["wickets"] == 2
    assert result["innings"][0]["overs"] == 6.4
    assert result["innings"][0]["run_rate"] == 6.0
    assert result["availability"]["ball_by_ball"] is False
    assert result["availability"]["fall_of_wickets"] is False
    assert result["batting_contributions"] == []


def test_cricket_over_notation_uses_legal_balls_for_rates():
    assert overs_to_balls(6.4) == 40
    assert overs_to_balls(3.2) == 20
    assert rate_from_balls(40, overs_to_balls(6.4)) == 6.0
    assert rate_from_balls(20, overs_to_balls(3.2)) == 6.0


def test_completed_first_innings_derives_target():
    result = normalize_momentum({
        "status": "success",
        "data": {
            "id": "match-1",
            "score": [
                {"r": 141, "w": 7, "o": 20, "inning": "Team A Inning 1"},
                {"r": 142, "w": 4, "o": 18, "inning": "Team B Inning 1"},
            ],
            "scorecard": [
                {"inning": "Team A Inning 1", "totals": {"R": 141, "W": 7, "O": 20}},
                {"inning": "Team B Inning 1", "totals": {"R": 142, "W": 4, "O": 18}},
            ],
        },
    })
    assert result["innings"][1]["target"] == 142


def test_incomplete_first_innings_does_not_derive_target():
    result = normalize_momentum({
        "status": "success",
        "data": {
            "id": "match-1",
            "scorecard": [
                {"inning": "Team A Inning 1", "totals": {"R": 40, "O": 6.4}},
                {"inning": "Team B Inning 1", "totals": {"R": 10, "W": 0, "O": 1.2}},
            ],
        },
    })
    assert result["innings"][1]["target"] is None


def test_provider_preserves_unsuccessful_json_diagnostics_without_secret():
    secret = "secret-key"

    async def handler(request):
        return httpx.Response(
            200,
            json={
                "status": "failure",
                "message": f"invalid key {secret}",
                "reason": "account restriction",
            },
        )

    provider = CricketDataProvider(
        api_key=secret,
        base_url="https://example.test/v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    async def run():
        with pytest.raises(CricketProviderError) as raised:
            await provider.live_matches()
        return raised

    raised = asyncio.run(run())

    error = raised.value
    assert error.provider_status == "failure"
    assert error.provider_message == "invalid key [redacted]"
    assert error.provider_reason == "account restriction"
    assert secret not in str(error.safe_detail())


def test_provider_preserves_http_status_and_json_diagnostics():
    async def handler(request):
        return httpx.Response(
            429,
            json={"status": "failure", "message": "daily limit reached", "reason": "quota"},
        )

    provider = CricketDataProvider(
        api_key="secret",
        base_url="https://example.test/v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    async def run():
        with pytest.raises(CricketProviderError) as raised:
            await provider.scorecard("match-1")
        return raised

    raised = asyncio.run(run())

    error = raised.value
    assert error.http_status == 429
    assert error.provider_message == "daily limit reached"
    assert error.provider_reason == "quota"
    assert error.safe_detail() == {
        "message": "Cricket Data HTTP request failed",
        "provider_http_status": 429,
        "provider_status": "failure",
        "provider_message": "daily limit reached",
        "provider_reason": "quota",
    }


def test_provider_caches_successful_responses_without_caching_errors():
    calls = 0

    async def success_handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "success", "data": []})

    async def error_handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"status": "failure", "message": "temporary"})

    async def run():
        _response_cache.clear()
        success = CricketDataProvider(
            api_key="cache-success",
            base_url="https://example.test/v1",
            client=httpx.AsyncClient(transport=httpx.MockTransport(success_handler)),
        )
        await success.live_matches()
        await success.live_matches()
        assert calls == 1

        failing = CricketDataProvider(
            api_key="cache-error",
            base_url="https://example.test/v1",
            client=httpx.AsyncClient(transport=httpx.MockTransport(error_handler)),
        )
        with pytest.raises(CricketProviderError):
            await failing.live_matches()
        with pytest.raises(CricketProviderError):
            await failing.live_matches()
        assert calls == 3

    asyncio.run(run())
    _response_cache.clear()


def test_provider_ttls_match_quota_protection_requirements():
    assert _CACHE_TTLS == {
        "currentMatches": 60,
        "recentMatches": 300,
        "match_scorecard": 120,
    }


def test_concurrent_successful_requests_share_one_provider_call():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"status": "success", "data": []})

    async def run():
        _response_cache.clear()
        provider = CricketDataProvider(
            api_key="concurrent-cache",
            base_url="https://example.test/v1",
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        await asyncio.gather(provider.live_matches(), provider.live_matches())

    asyncio.run(run())
    assert calls == 1
    _response_cache.clear()
