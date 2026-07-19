import json
import os

from unmuzzle import hfcache
from unmuzzle.cli import main
from unmuzzle.publish import build_entry, write_entry

from helpers import serve


def make_model(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"architectures": ["TestForCausalLM"]}))
    (model_dir / "weights.bin").write_bytes(os.urandom(200_000))
    (model_dir / ".DS_Store").write_bytes(b"junk")  # must be skipped
    return model_dir


def test_publish_get_verify_e2e(tmp_path, monkeypatch, capsys):
    model_dir = make_model(tmp_path)

    # publisher: serve the model dir over http, build + sign-free index entry
    srv, base = serve(model_dir)
    index_dir = tmp_path / "index"
    entry = build_entry(model_dir, "unmuzzle/e2e-model", http_bases=[base],
                        description="e2e", tags=["test"])
    write_entry(index_dir, entry)
    index_json = index_dir / "index.json"
    assert index_json.exists()

    # client: install into an isolated HF cache
    hf_home = tmp_path / "hf"
    monkeypatch.setenv("HF_HOME", str(hf_home))
    rc = main(["get", "unmuzzle/e2e-model", "--index", str(index_json), "--jobs", "4"])
    assert rc == 0
    srv.shutdown()

    out = capsys.readouterr().out
    assert "installed into HF cache" in out

    from unmuzzle.index import validate_entry
    rev = validate_entry(entry).revision()
    snapshot = hfcache.model_cache_dir("unmuzzle/e2e-model") / "snapshots" / rev
    assert (snapshot / "config.json").read_text() == (model_dir / "config.json").read_text()
    assert (snapshot / "weights.bin").read_bytes() == (model_dir / "weights.bin").read_bytes()
    assert not (snapshot / ".DS_Store").exists()

    # verify command passes
    rc = main(["verify", "unmuzzle/e2e-model", "--index", str(index_json)])
    assert rc == 0

    # refs/main points at the revision, so transformers can resolve it offline
    refs = hfcache.model_cache_dir("unmuzzle/e2e-model") / "refs" / "main"
    assert refs.read_text() == rev


def test_get_to_plain_dest(tmp_path, capsys):
    model_dir = make_model(tmp_path)
    srv, base = serve(model_dir)
    index_dir = tmp_path / "index"
    write_entry(index_dir, build_entry(model_dir, "unmuzzle/plain", http_bases=[base]))
    dest = tmp_path / "dest"
    rc = main(["get", "unmuzzle/plain", "--dest", str(dest),
               "--index", str(index_dir / "index.json")])
    srv.shutdown()
    assert rc == 0
    assert (dest / "weights.bin").read_bytes() == (model_dir / "weights.bin").read_bytes()
    assert "done. Files in" in capsys.readouterr().out


def test_publish_rejects_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    try:
        build_entry(empty, "unmuzzle/x", http_bases=["https://x"])
        assert False, "should have raised"
    except ValueError:
        pass
