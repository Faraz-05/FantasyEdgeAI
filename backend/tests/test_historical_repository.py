import json
from pathlib import Path

from backend.app.services.historical_repository import HistoricalRepository


DATASET = Path(__file__).parents[1] / "app" / "data" / "demo" / "historical_matches.json"


def test_dataset_loads_genuine_and_synthetic_matches_with_provenance():
    repository = HistoricalRepository(DATASET)
    matches = repository.list_matches(include_synthetic=True)

    assert len(matches) >= 3
    assert len({match["data"]["id"] for match in matches}) == len(matches)
    synthetic = [match for match in matches if match["synthetic"]]
    assert len(synthetic) >= 2
    assert all(match["source"] == "demo_historical_fixture" for match in synthetic)
    assert all(match["dataset_label"] == "synthetic_demo" for match in synthetic)
    assert all(match["is_complete_scorecard"] is False for match in synthetic)
    genuine = [match for match in matches if not match["synthetic"]]
    assert len(genuine) == 1
    assert genuine[0]["dataset_label"] == "genuine_fixture"
    assert genuine[0]["is_complete_scorecard"] is True


def test_original_fixture_is_reused_without_modifying_it():
    repository = HistoricalRepository(DATASET)
    match = repository.get_match("1f16f05e-e25c-43a1-ba00-331b1d2c3b8a")

    assert match["data"]["name"] == "Durham vs Warwickshire, North Group"
    assert match["synthetic"] is False
    assert match["source"] == "demo_fixture"


def test_player_identity_is_stable_and_records_sort_newest_first():
    repository = HistoricalRepository(DATASET)
    player_matches = repository.get_player_matches(
        player_id="27257774-29e0-4822-91fb-b298500b55a3",
        include_synthetic=True,
    )

    assert len(player_matches) == 3
    assert [match["data"]["date"] for match in player_matches] == sorted(
        (match["data"]["date"] for match in player_matches), reverse=True
    )
    assert all(match["player_identity"]["source"] == "provider_id" for match in player_matches)


def test_synthetic_history_is_excluded_by_default():
    repository = HistoricalRepository(DATASET)

    assert len(repository.list_matches()) == 1
    player_matches = repository.get_player_matches(
        player_id="27257774-29e0-4822-91fb-b298500b55a3"
    )
    assert len(player_matches) == 1
    assert player_matches[0]["synthetic"] is False


def test_unknown_match_and_player_return_empty_or_none():
    repository = HistoricalRepository(DATASET)

    assert repository.get_match("missing-match") is None
    assert repository.get_player_matches(player_id="missing-player") == []
    assert repository.get_player_matches() == []


def test_repository_returns_deep_copies():
    repository = HistoricalRepository(DATASET)
    first = repository.get_match("demo-history-2022-06-01")
    first["data"]["name"] = "Mutated"

    second = repository.get_match("demo-history-2022-06-01")
    assert second["data"]["name"] == "Synthetic Durham vs Warwickshire Match 1"


def test_missing_statistics_remain_null():
    repository = HistoricalRepository(DATASET)
    match = repository.get_match("demo-history-2022-05-25")
    ben = next(
        row for row in match["data"]["scorecard"][0]["batting"]
        if row["batsman"]["name"] == "Ben Raine"
    )

    assert ben["4s"] is None


def test_malformed_dataset_is_safe_and_does_not_call_external_services(tmp_path):
    malformed = tmp_path / "historical_matches.json"
    malformed.write_text("{not-json", encoding="utf-8")
    repository = HistoricalRepository(malformed)

    assert repository.list_matches() == []
