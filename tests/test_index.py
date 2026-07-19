import json

import pytest

from unmuzzle.index import IndexError, find_model, load_index, validate_entry


def entry(**kw):
    base = {
        "name": "unmuzzle/test-model",
        "files": [
            {"path": "config.json", "size": 10, "sha256": "a" * 64},
            {"path": "model.safetensors", "size": 100, "sha256": "b" * 64},
        ],
        "mirrors": {"http": ["https://example.com/m"], "magnet": None},
    }
    base.update(kw)
    return base


def test_validate_ok():
    e = validate_entry(entry())
    assert e.name == "unmuzzle/test-model"
    assert e.total_size == 110
    assert e.revision() and len(e.revision()) == 16


def test_manifest_is_deterministic_and_sorted():
    e = validate_entry(entry())
    assert e.canonical_manifest() == f"{'a' * 64}  config.json\n{'b' * 64}  model.safetensors\n"


def test_rejects_traversal():
    with pytest.raises(IndexError, match="unsafe path"):
        validate_entry(entry(files=[{"path": "../x", "size": 1, "sha256": "a" * 64}]))


def test_rejects_missing_mirrors():
    with pytest.raises(IndexError, match="no mirrors"):
        validate_entry(entry(mirrors={"http": [], "magnet": None}))


def test_rejects_bad_name():
    with pytest.raises(IndexError):
        validate_entry(entry(name="no-org"))


def test_load_and_find(tmp_path):
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"version": 1, "models": [entry()]}))
    entries = load_index(str(idx))
    assert find_model(entries, "unmuzzle/test-model").name == "unmuzzle/test-model"
    assert find_model(entries, "test-model").name == "unmuzzle/test-model"  # shorthand
    assert find_model(entries, "nope") is None
