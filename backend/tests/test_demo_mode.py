import asyncio

import httpx
import pytest

from backend.app.main import app
from backend.app.routers import matches as matches_router
from backend.app.services import cricket_demo
from backend.app.services.cricket_provider import CricketDataProvider


def test_demo_fixture_uses_application_data_directory():
    assert cricket_demo._FIXTURE_PATH.parent.name == "demo"
    assert cricket_demo._FIXTURE_PATH.parent.parent.name == "data"
    assert cricket_demo._FIXTURE_PATH.exists()


def test_demo_mode_returns_fixture_backed_match_and_players(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    async def run():
        live = await matches_router.live_matches(offset=0)
        players = await matches_router.match_players(
            "1f16f05e-e25c-43a1-ba00-331b1d2c3b8a"
        )
        return live, players

    live, players = asyncio.run(run())
    assert live["demo"] is True
    assert live["source"] == "demo_fixture"
    assert live["matches"][0]["name"].startswith("Durham vs Warwickshire")
    assert players["demo"] is True
    assert players["source"] == "demo_fixture"
    assert any(player["player_name"].strip() == "Graham Clark" for player in players["players"])


def test_demo_mode_returns_scorecard_momentum_with_target_and_verified_events(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    async def run():
        return await matches_router.match_momentum(
            "1f16f05e-e25c-43a1-ba00-331b1d2c3b8a"
        )

    result = asyncio.run(run())
    assert result["demo"] is True
    assert result["source"] == "demo_fixture"
    assert result["innings"][0]["runs"] == 141
    assert result["innings"][0]["wickets"] == 7
    assert result["innings"][0]["run_rate"] == 7.05
    assert result["innings"][1]["runs"] == 142
    assert result["innings"][1]["target"] == 142
    assert result["result"]["winner"] == "Warwickshire"
    assert result["availability"]["innings_progression"] is False
    assert result["availability"]["partnerships"] is False
    assert result["dismissal_events"]


def test_demo_mode_momentum_does_not_call_cricket_provider(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Cricket provider must not be called in demo mode")

    monkeypatch.setattr(matches_router.CricketDataProvider, "scorecard", fail_if_called)
    result = asyncio.run(matches_router.match_momentum("1f16f05e-e25c-43a1-ba00-331b1d2c3b8a"))
    assert result["source"] == "demo_fixture"


def test_demo_mode_momentum_rejects_unknown_match(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    with pytest.raises(Exception) as raised:
        asyncio.run(matches_router.match_momentum("unknown-match"))
    assert "only supports the saved" in str(raised.value)


def test_demo_mode_does_not_call_cricket_provider(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Cricket provider must not be called in demo mode")

    monkeypatch.setattr(matches_router.CricketDataProvider, "live_matches", fail_if_called)
    monkeypatch.setattr(matches_router.CricketDataProvider, "scorecard", fail_if_called)

    async def run():
        await matches_router.live_matches(offset=0)
        await matches_router.match_players(
            "1f16f05e-e25c-43a1-ba00-331b1d2c3b8a"
        )

    asyncio.run(run())


def test_demo_mode_does_not_instantiate_provider_for_live_or_recent(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    def fail_if_instantiated(*args, **kwargs):
        raise AssertionError("Cricket provider must not be instantiated in demo mode")

    monkeypatch.setattr(matches_router, "CricketDataProvider", fail_if_instantiated)

    async def run():
        live = await matches_router.live_matches(offset=0)
        recent = await matches_router.recent_matches(offset=0)
        return live, recent

    live, recent = asyncio.run(run())
    assert live["demo"] is True
    assert recent["demo"] is True
    assert live["source"] == "demo_fixture"
    assert recent["source"] == "demo_fixture"


def test_demo_mode_is_off_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    service = matches_router._match_service()
    assert isinstance(service, matches_router.CricketDataProvider)


def test_demo_mode_false_keeps_live_provider_available(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    service = matches_router._match_service()
    assert isinstance(service, matches_router.CricketDataProvider)


def test_explicit_demo_mode_overrides_live_deployment_default(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    assert isinstance(
        matches_router._match_service(matches_router.DataMode.DEMO),
        matches_router.DemoCricketDataService,
    )


def test_explicit_live_mode_overrides_demo_deployment_default(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    assert isinstance(
        matches_router._match_service(matches_router.DataMode.LIVE),
        CricketDataProvider,
    )


def test_explicit_live_endpoint_uses_provider(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    async def provider_matches(self, offset=0):
        return {"status": "success", "data": []}

    monkeypatch.setattr(CricketDataProvider, "live_matches", provider_matches)
    result = asyncio.run(
        matches_router.live_matches(mode=matches_router.DataMode.LIVE)
    )
    assert result["demo"] is False
    assert result["matches"] == []


def test_explicit_demo_endpoint_never_calls_provider(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Live provider must not be called in demo mode")

    monkeypatch.setattr(CricketDataProvider, "live_matches", fail_if_called)
    result = asyncio.run(
        matches_router.live_matches(mode=matches_router.DataMode.DEMO)
    )
    assert result["demo"] is True
    assert result["source"] == "demo_fixture"


def test_invalid_mode_is_rejected():
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/api/matches/live?mode=invalid")

    response = asyncio.run(run())
    assert response.status_code == 422
