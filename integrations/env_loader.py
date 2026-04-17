"""Load Ragstone env files into os.environ (same behavior as Streamlit app)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from integrations.paths import PROJECT_ROOT


def load_ragstone_env_files() -> None:
    candidates = [
        Path.home() / ".ragstone" / "command_center.env",
        PROJECT_ROOT / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            if val:
                os.environ[key] = val


def _merge_streamlit_secrets_dict(data: Dict[str, Any], *, prefix: str = "") -> None:
    """Apply TOML values into os.environ if the key is not already set (matches Streamlit env-then-secrets order)."""
    for k, v in data.items():
        full_key = f"{prefix}_{k}" if prefix else str(k)
        if isinstance(v, dict):
            _merge_streamlit_secrets_dict(v, prefix=full_key)
            continue
        if not isinstance(v, (str, int, float, bool)):
            continue
        if str(os.environ.get(full_key, "")).strip():
            continue
        if isinstance(v, bool):
            os.environ[full_key] = "true" if v else "false"
        else:
            os.environ[full_key] = str(v)


def load_streamlit_secrets_into_environ() -> None:
    """Load ``.streamlit/secrets.toml`` into ``os.environ`` for keys not already set.

    Streamlit's ``_env_or_secret`` checks the process environment first, then ``st.secrets``.
    The Cockpit API loads ``.env`` via :func:`load_ragstone_env_files` first; this fills gaps
    from the same ``secrets.toml`` the Streamlit app uses (e.g. ``APPLE_CALENDAR_ICS_URL``,
    ``ICLOUD_*``) so personal calendar works without duplicating values.
    """
    path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if not path.is_file():
        return
    try:
        import toml
    except ImportError:  # pragma: no cover
        return
    try:
        data = toml.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    _merge_streamlit_secrets_dict(data)


def env_str(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip() or default
