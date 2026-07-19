import pytest


@pytest.fixture(autouse=True)
def isolated_trust_store(tmp_path, monkeypatch):
    """Keep every test away from the user's real known_publishers.json."""
    monkeypatch.setenv("UNMUZZLE_TRUST_STORE", str(tmp_path / "known_publishers.json"))
