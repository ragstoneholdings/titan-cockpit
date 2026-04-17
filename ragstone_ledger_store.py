"""Ragstone S-Corp sovereignty ledger — ragstone_ledger.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "ragstone_ledger.json"


def _default() -> Dict[str, Any]:
    return {
        "version": 1,
        "revenue_ytd_usd": None,
        "revenue_prior_ytd_usd": None,
        "cash_balance_usd": None,
        "monthly_burn_usd": None,
        "fte_count": None,
        "s_corp_election_note": "",
        "tax_posture_note": "",
        "yoy_revenue_growth_percent": None,
        "revenue_per_fte_usd": None,
        "cash_runway_months": None,
    }


def load_bundle() -> Dict[str, Any]:
    if not PATH.is_file():
        return _default()
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default()
    if not isinstance(raw, dict):
        return _default()
    out = _default()
    out.update(raw)
    out.setdefault("version", 1)
    return out


def save_bundle(bundle: Dict[str, Any]) -> None:
    data = _default()
    data.update(bundle)
    data["version"] = max(1, int(data.get("version") or 1))
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def computed_kpis() -> Dict[str, Any]:
    b = load_bundle()
    rev = _f(b.get("revenue_ytd_usd"))
    prev = _f(b.get("revenue_prior_ytd_usd"))
    yoy = None
    if rev is not None and prev is not None and prev > 0:
        yoy = round(100.0 * (rev - prev) / prev, 1)
    elif b.get("yoy_revenue_growth_percent") is not None:
        yoy = _f(b.get("yoy_revenue_growth_percent"))

    cash = _f(b.get("cash_balance_usd"))
    burn = _f(b.get("monthly_burn_usd"))
    runway = None
    if cash is not None and burn is not None and burn > 0:
        runway = round(cash / burn, 2)
    elif b.get("cash_runway_months") is not None:
        runway = _f(b.get("cash_runway_months"))

    fte = _f(b.get("fte_count"))
    rpf = None
    if rev is not None and fte is not None and fte > 0:
        rpf = round(rev / fte, 2)
    elif b.get("revenue_per_fte_usd") is not None:
        rpf = _f(b.get("revenue_per_fte_usd"))

    return {
        "yoy_revenue_growth_percent": yoy,
        "revenue_per_fte_usd": rpf,
        "cash_runway_months": runway,
        "revenue_ytd_usd": rev,
        "s_corp_election_note": str(b.get("s_corp_election_note") or ""),
        "tax_posture_note": str(b.get("tax_posture_note") or ""),
    }


def _f(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
