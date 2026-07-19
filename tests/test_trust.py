import pytest

from unmuzzle import api, trust
from unmuzzle.index import validate_entry


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("UNMUZZLE_TRUST_STORE", str(tmp_path / "known.json"))
    return tmp_path / "known.json"


KEY_A = "RWQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
KEY_B = "RWQBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"


def test_first_use_pins(store):
    r = trust.check_continuity("unmuzzle/model", KEY_A)
    assert r["continuity"] == "pinned_first_use"
    assert r["publisher"] == "unmuzzle"
    assert store.exists()


def test_same_key_ok(store):
    trust.check_continuity("unmuzzle/model", KEY_A)
    r = trust.check_continuity("unmuzzle/other-model", KEY_A)
    assert r["continuity"] == "ok"
    assert r["pinned"] is False


def test_changed_key_raises(store):
    trust.check_continuity("unmuzzle/model", KEY_A)
    with pytest.raises(trust.KeyChangedError) as exc:
        trust.check_continuity("unmuzzle/model", KEY_B)
    assert "PUBLISHER KEY CHANGED" in str(exc.value)


def test_accept_new_key_repins(store):
    trust.check_continuity("unmuzzle/model", KEY_A)
    r = trust.check_continuity("unmuzzle/model", KEY_B, accept_new=True)
    assert r["continuity"] == "accepted_new_key"
    assert r["previous_key"] == KEY_A
    assert trust.check_continuity("unmuzzle/model", KEY_B)["continuity"] == "ok"


def test_orgs_are_independent(store):
    trust.check_continuity("unmuzzle/model", KEY_A)
    r = trust.check_continuity("someoneelse/model", KEY_B)
    assert r["continuity"] == "pinned_first_use"


def _signed_entry():
    return validate_entry({
        "name": "unmuzzle/t",
        "files": [{"path": "w.bin", "size": 1,
                   "sha256": "0" * 64}],
        "mirrors": {"http": ["http://localhost"]},
        "signature": "sig",
        "publisher_pubkey": KEY_A,
    })


def test_api_signature_check_enforces_continuity(store, monkeypatch):
    monkeypatch.setattr(api.signmod, "have_minisign", lambda: True)
    monkeypatch.setattr(api.signmod, "verify", lambda *a: True)
    entry = _signed_entry()
    r = api.check_signature(entry, require=True)
    assert r["trust"]["continuity"] == "pinned_first_use"
    entry2 = _signed_entry()
    entry2.publisher_pubkey = KEY_B
    with pytest.raises(api.UnmuzzleError, match="PUBLISHER KEY CHANGED"):
        api.check_signature(entry2, require=True)
