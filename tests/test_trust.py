import json

import pytest

from unmuzzle import api, trust
from unmuzzle.index import validate_entry


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("UNMUZZLE_TRUST_STORE", str(tmp_path / "known.json"))
    return tmp_path / "known.json"


KEY_A = "RWQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
KEY_B = "RWQBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
OFFICIAL = trust.OFFICIAL_KEYS["unmuzzle"]


def test_first_use_pins(store):
    r = trust.check_continuity("testorg/model", KEY_A)
    assert r["continuity"] == "pinned_first_use"
    assert r["publisher"] == "testorg"
    assert store.exists()


def test_same_key_ok(store):
    trust.check_continuity("testorg/model", KEY_A)
    r = trust.check_continuity("testorg/other-model", KEY_A)
    assert r["continuity"] == "ok"
    assert r["pinned"] is False


def test_changed_key_raises(store):
    trust.check_continuity("testorg/model", KEY_A)
    with pytest.raises(trust.KeyChangedError) as exc:
        trust.check_continuity("testorg/model", KEY_B)
    assert "PUBLISHER KEY CHANGED" in str(exc.value)


def test_accept_new_key_repins(store):
    trust.check_continuity("testorg/model", KEY_A)
    r = trust.check_continuity("testorg/model", KEY_B, accept_new=True)
    assert r["continuity"] == "accepted_new_key"
    assert r["previous_key"] == KEY_A
    assert trust.check_continuity("testorg/model", KEY_B)["continuity"] == "ok"


def test_orgs_are_independent(store):
    trust.check_continuity("testorg/model", KEY_A)
    r = trust.check_continuity("someoneelse/model", KEY_B)
    assert r["continuity"] == "pinned_first_use"


def test_official_key_wrong_on_first_use_fails(store):
    with pytest.raises(trust.KeyChangedError, match="WRONG KEY"):
        trust.check_continuity("unmuzzle/model", KEY_A)


def test_official_key_correct_passes(store):
    r = trust.check_continuity("unmuzzle/model", OFFICIAL)
    assert r["continuity"] == "ok"
    assert r["operator"] is True
    assert trust.check_continuity("unmuzzle/model2", OFFICIAL)["continuity"] == "ok"


def _signed_entry():
    return validate_entry({
        "name": "testorg/t",
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


# --- operator set (root-signed) ----------------------------------------------

def _op_doc(root_key, ops, sig="sig"):
    return {"version": 1, "root_pubkey": root_key, "operators": ops, "signature": sig}


def test_operators_root_signature_checked(store, monkeypatch):
    monkeypatch.setattr(trust.signmod, "verify", lambda *a: True)
    ops = trust.verify_operators(_op_doc(OFFICIAL, {"op1": KEY_A, "op2": KEY_B}))
    assert ops == {"op1": KEY_A, "op2": KEY_B}


def test_operators_untrusted_root_rejected(store, monkeypatch):
    monkeypatch.setattr(trust.signmod, "verify", lambda *a: True)
    with pytest.raises(trust.KeyChangedError, match="untrusted root"):
        trust.verify_operators(_op_doc(KEY_A, {"op1": KEY_B}))


def test_operators_bad_root_signature_rejected(store, monkeypatch):
    monkeypatch.setattr(trust.signmod, "verify", lambda *a: False)
    with pytest.raises(trust.KeyChangedError, match="ROOT SIGNATURE INVALID"):
        trust.verify_operators(_op_doc(OFFICIAL, {"op1": KEY_A}))


def test_official_entry_signed_by_operator_passes(store):
    ops = {"op1": KEY_A}
    r = trust.check_continuity("unmuzzle/model", KEY_A, operators=ops)
    assert r["continuity"] == "ok"
    assert r["operator"] is True


def test_official_entry_signed_by_non_operator_fails(store):
    with pytest.raises(trust.KeyChangedError, match="WRONG KEY"):
        trust.check_continuity("unmuzzle/model", KEY_B, operators={"op1": KEY_A})


def test_official_falls_back_to_root_only_without_operators(store):
    assert trust.check_continuity("unmuzzle/model", OFFICIAL)["continuity"] == "ok"
    with pytest.raises(trust.KeyChangedError):
        trust.check_continuity("unmuzzle/model", KEY_A, operators=None)


def test_load_operators_local(store, tmp_path, monkeypatch):
    monkeypatch.setattr(trust.signmod, "verify", lambda *a: True)
    (tmp_path / "operators.json").write_text(
        json.dumps(_op_doc(OFFICIAL, {"op1": KEY_A})))
    ops = trust.load_operators(str(tmp_path / "index.json"))
    assert ops == {"op1": KEY_A}
    assert trust.load_operators(str(tmp_path / "nonexistent" / "index.json")) is None
