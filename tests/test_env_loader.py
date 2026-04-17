"""Env / secrets loading (Cockpit API parity with Streamlit)."""

import os


def test_load_streamlit_secrets_respects_existing_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EXISTING_ONLY", "from_shell")
    streamlit_dir = tmp_path / ".streamlit"
    streamlit_dir.mkdir()
    (streamlit_dir / "secrets.toml").write_text(
        'EXISTING_ONLY = "from_toml"\nFROM_TOML_ONLY = "yes"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("integrations.env_loader.PROJECT_ROOT", tmp_path)

    from integrations.env_loader import load_streamlit_secrets_into_environ

    load_streamlit_secrets_into_environ()
    assert os.environ["EXISTING_ONLY"] == "from_shell"
    assert os.environ["FROM_TOML_ONLY"] == "yes"

    monkeypatch.delenv("FROM_TOML_ONLY", raising=False)
