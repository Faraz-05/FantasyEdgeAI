import copy
import json
from pathlib import Path
from typing import Any

from backend.app.services.cricket_provider import CricketProviderError

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "data"
    / "demo"
    / "durham_warwickshire_scorecard.json"
)


class DemoCricketDataService:
    def __init__(self) -> None:
        try:
            self._scorecard = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CricketProviderError(
                "Demo scorecard fixture is unavailable",
                endpoint="demo_fixture",
            ) from error

    def _match(self) -> dict[str, Any]:
        data = self._scorecard["data"]
        return {
            key: copy.deepcopy(data[key])
            for key in (
                "id",
                "name",
                "matchType",
                "status",
                "venue",
                "date",
                "teams",
                "score",
            )
            if key in data
        }

    def _envelope(self, data: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "data": data,
            "info": {"source": "demo_fixture", "demo": True},
            "demo": True,
            "source": "demo_fixture",
        }

    async def live_matches(self, offset: int = 0) -> dict[str, Any]:
        return self._envelope([self._match()] if offset == 0 else [])

    async def recent_matches(self, offset: int = 0) -> dict[str, Any]:
        return self._envelope([self._match()] if offset == 0 else [])

    async def scorecard(self, match_id: str) -> dict[str, Any]:
        if match_id != self._scorecard["data"].get("id"):
            raise CricketProviderError(
                "Demo mode only supports the saved Durham vs Warwickshire fixture",
                endpoint="demo_fixture",
                provider_status="demo",
            )
        return {
            "status": "success",
            "data": copy.deepcopy(self._scorecard["data"]),
            "info": {"source": "demo_fixture", "demo": True},
            "demo": True,
            "source": "demo_fixture",
        }
