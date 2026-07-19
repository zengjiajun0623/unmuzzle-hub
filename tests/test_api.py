import json
import os

import pytest

from unmuzzle import api
from unmuzzle.cli import main
from unmuzzle.publish import build_entry, write_entry

from helpers import serve


@pytest.fixture
def published(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    (model_dir / "weights.bin").write_bytes(os.urandom(150_000))
    srv, base = serve(model_dir)
    index_dir = tmp_path / "index"
    write_entry(index_dir, build_entry(model_dir, "unmuzzle/api-test",
                                       http_bases=[base], tags=["test"]))
    yield str(index_dir / "index.json"), model_dir
    srv.shutdown()


def test_list_and_info(published):
    index, _ = published
    models = api.list_models(index=index)
    assert [m["name"] for m in models] == ["unmuzzle/api-test"]
    assert models[0]["revision"]
    info = api.model_info("unmuzzle/api-test", index=index)
    assert info["total_size"] > 0 and not info["signed"]


def test_get_and_verify_api(published, tmp_path, monkeypatch):
    index, model_dir = published
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    result = api.get("unmuzzle/api-test", index=index, method="http", jobs=2)
    assert result["hf_cache"] and result["files"] == 2
    assert "local_files_only=True" in result["load_with"]
    v = api.verify("unmuzzle/api-test", index=index)
    assert v["ok"] and v["checked"] == 2


def test_get_missing_model_errors(published):
    index, _ = published
    with pytest.raises(api.UnmuzzleError, match="not found"):
        api.get("unmuzzle/nope", index=index)


def test_require_signature_on_unsigned_entry(published):
    index, _ = published
    with pytest.raises(api.UnmuzzleError, match="unsigned"):
        api.get("unmuzzle/api-test", index=index, require_signature=True)


def test_cli_json_output(published, tmp_path, monkeypatch, capsys):
    index, _ = published
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    rc = main(["list", "--json", "--index", index])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed[0]["name"] == "unmuzzle/api-test"

    rc = main(["get", "unmuzzle/api-test", "--json", "--index", index, "--jobs", "2"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hf_cache"] is True

    rc = main(["get", "unmuzzle/nope", "--json", "--index", index])
    assert rc == 1
    assert "error" in json.loads(capsys.readouterr().err)


def test_keygen(tmp_path, monkeypatch):
    import shutil
    if not shutil.which("minisign"):
        pytest.skip("minisign not installed")
    key = tmp_path / "k.key"
    result = api.keygen(str(key))
    assert result["pubkey"] and key.exists()
    with pytest.raises(api.UnmuzzleError, match="already exists"):
        api.keygen(str(key))


def test_sign_and_verify_roundtrip(published, tmp_path):
    import shutil
    if not shutil.which("minisign"):
        pytest.skip("minisign not installed")
    index, model_dir = published
    key = tmp_path / "k.key"
    api.keygen(str(key))
    result = api.publish(str(model_dir), "testorg/signed-test",
                         http_bases=["https://example.com/x"],
                         sign_key=str(key), index_dir=str(tmp_path / "idx2"))
    assert result["signed"] and result["entry"]["publisher_pubkey"]
    from unmuzzle.index import validate_entry
    status = api.check_signature(validate_entry(result["entry"]), require=True)
    assert status["signed"] and status["verified"]
    assert status["trust"]["continuity"] in ("pinned_first_use", "ok")
