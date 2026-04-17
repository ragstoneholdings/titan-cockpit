"""identity.json persistence for Purpose Pillar."""

import json

import identity_store


def test_load_identity_creates_default(tmp_path, monkeypatch):
    p = tmp_path / "identity.json"
    monkeypatch.setattr(identity_store, "IDENTITY_JSON_PATH", p)
    assert not p.is_file()
    text = identity_store.load_identity_purpose()
    assert p.is_file()
    assert "integrity" in text.lower() or "Integrity" in text
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("purpose") == text


def test_save_roundtrip_em_dash(tmp_path, monkeypatch):
    monkeypatch.setattr(identity_store, "IDENTITY_JSON_PATH", tmp_path / "identity.json")
    s = "Line one—line two"
    identity_store.save_identity_purpose(s)
    assert identity_store.load_identity_purpose() == s


def test_save_purpose_preserves_drain_profile(tmp_path, monkeypatch):
    path = tmp_path / "identity.json"
    monkeypatch.setattr(identity_store, "IDENTITY_JSON_PATH", path)
    path.write_text(
        '{"version":2,"purpose":"Old","drain_profile":{"high_drain_labels":["#x"],"high_drain_title_substrings":["tax"]}}',
        encoding="utf-8",
    )
    identity_store.save_identity_purpose("New purpose")
    dp = identity_store.load_identity_drain_profile()
    assert dp["high_drain_labels"] == ["#x"]
    assert dp["high_drain_title_substrings"] == ["tax"]
    assert identity_store.load_identity_purpose() == "New purpose"


def test_load_identity_drain_profile_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(identity_store, "IDENTITY_JSON_PATH", tmp_path / "identity.json")
    dp = identity_store.load_identity_drain_profile()
    assert dp["high_drain_labels"] == []
    assert dp["high_drain_title_substrings"] == []
