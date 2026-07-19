import os

from unmuzzle.hfcache import install, model_cache_dir


def test_install_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "config.json").write_text("{}")
    sub = staging / "subdir"
    sub.mkdir()
    (sub / "weights.bin").write_bytes(os.urandom(1000))

    files = [
        {"path": "config.json", "size": 2, "sha256": "a" * 64},
        {"path": "subdir/weights.bin", "size": 1000, "sha256": "b" * 64},
    ]
    snapshot = install("unmuzzle/test", "rev123", staging, files)

    cache = model_cache_dir("unmuzzle/test")
    assert (cache / "blobs" / ("a" * 64)).exists()
    assert (cache / "blobs" / ("b" * 64)).exists()
    link = snapshot / "subdir" / "weights.bin"
    assert link.read_bytes() == (sub / "weights.bin").read_bytes()
    assert (cache / "refs" / "main").read_text() == "rev123"
