import copy
import json
from pathlib import Path
from typing import Any


_DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "demo" / "historical_matches.json"


class HistoricalRepository:
    """Read-only access to the explicitly labelled historical demo dataset."""

    def __init__(self, dataset_path: Path | None = None) -> None:
        self._dataset_path = dataset_path or _DATASET_PATH
        self._matches = self._load_matches()

    def _load_matches(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._dataset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return []
        if not isinstance(raw, dict) or not isinstance(raw.get("matches"), list):
            return []

        matches: list[dict[str, Any]] = []
        for manifest in raw["matches"]:
            match = self._resolve_match(manifest, raw)
            if match is not None:
                matches.append(match)
        return matches

    def _resolve_match(self, manifest: Any, dataset: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(manifest, dict):
            return None
        match = copy.deepcopy(manifest)
        fixture_path = match.pop("fixture_path", None)
        if isinstance(fixture_path, str):
            try:
                fixture = json.loads(
                    (self._dataset_path.parent / fixture_path).resolve().read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return None
            if not isinstance(fixture, dict) or not isinstance(fixture.get("data"), dict):
                return None
            match = {
                **fixture,
                "synthetic": match.get("synthetic", False),
                "source": match.get("source") or dataset.get("source"),
                "dataset_label": match.get("dataset_label", "genuine_fixture"),
                "is_complete_scorecard": match.get("is_complete_scorecard", False),
            }
        elif isinstance(match.get("data"), dict):
            match.setdefault("synthetic", dataset.get("synthetic") is True)
            match.setdefault("source", dataset.get("source"))
            match.setdefault(
                "dataset_label",
                "synthetic_demo" if match["synthetic"] else "genuine_fixture",
            )
            match.setdefault("is_complete_scorecard", False)
        else:
            return None

        data = match.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            return None
        if not isinstance(match["synthetic"], bool) or not isinstance(match["source"], str):
            return None
        if not isinstance(match["dataset_label"], str) or not isinstance(
            match["is_complete_scorecard"], bool
        ):
            return None
        match["data_quality"] = (
            "synthetic_demo" if match["synthetic"] else "genuine_fixture"
        )
        match["demo"] = True
        return match

    def list_matches(self, include_synthetic: bool = False) -> list[dict[str, Any]]:
        matches = [
            match
            for match in self._matches
            if include_synthetic or not match["synthetic"]
        ]
        return copy.deepcopy(matches)

    def get_match(self, match_id: str) -> dict[str, Any] | None:
        match = next((item for item in self._matches if item["data"]["id"] == match_id), None)
        return copy.deepcopy(match) if match is not None else None

    def get_player_matches(
        self,
        player_id: str | None = None,
        player_name: str | None = None,
        include_synthetic: bool = False,
    ) -> list[dict[str, Any]]:
        if not player_id and not player_name:
            return []
        matches: list[dict[str, Any]] = []
        for match in self._matches:
            if match["synthetic"] and not include_synthetic:
                continue
            identity = self._match_player_identity(match, player_id, player_name)
            if identity is not None:
                result = copy.deepcopy(match)
                result["player_identity"] = identity
                matches.append(result)
        matches.sort(key=lambda item: item["data"].get("date") or "", reverse=True)
        return matches

    @staticmethod
    def _match_player_identity(
        match: dict[str, Any],
        player_id: str | None,
        player_name: str | None,
    ) -> dict[str, str] | None:
        data = match.get("data")
        innings = data.get("scorecard") if isinstance(data, dict) else None
        if not isinstance(innings, list):
            return None

        refs: list[dict[str, Any]] = []
        for inning in innings:
            if not isinstance(inning, dict):
                continue
            for category, key in (("batting", "batsman"), ("bowling", "bowler"), ("fielding", "catcher")):
                for row in inning.get(category, []):
                    if isinstance(row, dict) and isinstance(row.get(key), dict):
                        refs.append(row[key])

        for ref in refs:
            if isinstance(ref.get("id"), str) and ref["id"] == player_id:
                return {"player_id": ref["id"], "player_name": ref.get("name", "").strip(), "source": "provider_id"}

        if match.get("allow_name_fallback") is True and isinstance(player_name, str):
            wanted = player_name.strip().casefold()
            for ref in refs:
                name = ref.get("name")
                if isinstance(name, str) and name.strip().casefold() == wanted:
                    return {"player_id": ref.get("id", ""), "player_name": name.strip(), "source": "name_fallback"}
        return None


_default_repository = HistoricalRepository()


def list_historical_matches(include_synthetic: bool = False) -> list[dict[str, Any]]:
    return _default_repository.list_matches(include_synthetic=include_synthetic)


def get_historical_match(match_id: str) -> dict[str, Any] | None:
    return _default_repository.get_match(match_id)


def get_player_historical_matches(
    player_id: str | None = None,
    player_name: str | None = None,
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    return _default_repository.get_player_matches(
        player_id,
        player_name,
        include_synthetic=include_synthetic,
    )
