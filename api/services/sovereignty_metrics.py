"""Sovereignty Engine KPI read model for cockpit snapshot."""

from __future__ import annotations

from typing import Any, Dict, List

import identity_store
import ragstone_ledger_store
import sovereignty_store
import vanguard_health_store


def _pct(n: float, d: float) -> float:
    if d <= 0:
        return 0.0
    return round(100.0 * min(1.0, max(0.0, n / d)), 1)


def count_utility_weighted_tasks(by_id: Dict[str, Any], drain: Dict[str, Any]) -> int:
    """Rough utility load: tasks matching high-drain labels or title substrings."""
    labs = drain.get("high_drain_labels") if isinstance(drain, dict) else []
    subs = drain.get("high_drain_title_substrings") if isinstance(drain, dict) else []
    if not isinstance(labs, list):
        labs = []
    if not isinstance(subs, list):
        subs = []
    labs_l = [str(x).strip().lower() for x in labs if str(x).strip()]
    subs_l = [str(x).strip().lower() for x in subs if str(x).strip()]
    if not labs_l and not subs_l:
        return 0
    n = 0
    for t in by_id.values():
        if not isinstance(t, dict):
            continue
        tlabs = t.get("labels")
        title = str(t.get("content") or "").lower()
        desc = str(t.get("description") or "").lower()
        blob = f"{title} {desc}"
        hit = False
        if labs_l and isinstance(tlabs, list):
            for nm in tlabs:
                if str(nm).strip().lower() in labs_l:
                    hit = True
                    break
        if not hit and subs_l:
            for s in subs_l:
                if s and s in blob:
                    hit = True
                    break
        if hit:
            n += 1
    return n


def build_sovereignty_block(
    *,
    vanguard_executed: Dict[str, Any],
    integrity_consistency_percent: float,
) -> Dict[str, Any]:
    """Nested object for CockpitResponse.sovereignty."""
    deep = int(vanguard_executed.get("deep") or 0)
    mixed = int(vanguard_executed.get("mixed") or 0)
    shallow = int(vanguard_executed.get("shallow") or 0)
    exec_total = max(0, deep + mixed + shallow)
    # Sovereignty quotient: deep share of logged execution counts (proxy for deep vs shallow work).
    sq = _pct(float(deep), float(exec_total)) if exec_total else 0.0

    s_in = sovereignty_store.load_bundle()
    fi = s_in.get("firefighting_incidents_week")
    zp = s_in.get("zapier_failure_events_week")
    op_parts: List[str] = []
    if fi is not None:
        op_parts.append(f"Firefighting incidents (wk): {fi}")
    if zp is not None:
        op_parts.append(f"Zapier failures (wk): {zp}")
    dn = s_in.get("delegations_not_pushed_week")
    if dn is not None:
        op_parts.append(f"Delegations you kept (wk): {dn}")
    note = str(s_in.get("operational_authority_note") or "").strip()
    if note:
        op_parts.append(note[:120])
    operational_line = " · ".join(op_parts) if op_parts else "—"

    rk = ragstone_ledger_store.computed_kpis()
    fin_parts: List[str] = []
    if rk.get("yoy_revenue_growth_percent") is not None:
        fin_parts.append(f"YoY rev {rk['yoy_revenue_growth_percent']}%")
    if rk.get("cash_runway_months") is not None:
        fin_parts.append(f"Runway {rk['cash_runway_months']}mo")
    if rk.get("revenue_per_fte_usd") is not None:
        fin_parts.append(f"Rev/FTE ${rk['revenue_per_fte_usd']}")
    tax = str(rk.get("tax_posture_note") or "").strip()
    scorp = str(rk.get("s_corp_election_note") or "").strip()
    if tax or scorp:
        fin_parts.append(f"Tax: {(scorp or tax)[:80]}")
    financial_line = " · ".join(fin_parts) if fin_parts else "—"

    hb = vanguard_health_store.load_bundle()
    cur = hb.get("current") if isinstance(hb.get("current"), dict) else {}
    tgt = hb.get("targets") if isinstance(hb.get("targets"), dict) else {}
    bf = cur.get("body_fat_percent")
    bench = cur.get("bench_press_lb")
    phys_parts: List[str] = []
    if bf is not None:
        phys_parts.append(f"BF {bf}% / target {tgt.get('body_fat_percent_target', 13)}%")
    if bench is not None:
        phys_parts.append(f"Bench {bench}lb")
    phys_parts.append(f"Integrity {integrity_consistency_percent:.0f}%")
    physical_line = " · ".join(phys_parts) if phys_parts else f"Integrity {integrity_consistency_percent:.0f}%"

    return {
        "sovereignty_quotient_percent": sq,
        "deep_work_sessions_logged": deep,
        "execution_mix_total": exec_total,
        "sovereignty_line": f"Deep share {sq}% of logged trio work",
        "operational_authority_line": operational_line,
        "financial_sovereignty_line": financial_line,
        "physical_baseline_line": physical_line,
    }


def build_sovereignty_with_todoist(
    *,
    vanguard_executed: Dict[str, Any],
    integrity_consistency_percent: float,
    tasks_by_id: Dict[str, Any],
) -> Dict[str, Any]:
    block = build_sovereignty_block(
        vanguard_executed=vanguard_executed,
        integrity_consistency_percent=integrity_consistency_percent,
    )
    drain = identity_store.load_identity_drain_profile()
    u_count = count_utility_weighted_tasks(tasks_by_id, drain)
    deep = int(vanguard_executed.get("deep") or 0)
    mixed = int(vanguard_executed.get("mixed") or 0)
    shallow = int(vanguard_executed.get("shallow") or 0)
    denom = max(1, deep + mixed + shallow + max(0, u_count))
    blended = _pct(float(deep), float(denom))
    line = str(block.get("sovereignty_line") or "")
    if u_count:
        line = f"{line}; utility-tagged open: {u_count}"
    block["sovereignty_quotient_blended_percent"] = blended
    block["utility_tagged_open_count"] = u_count
    block["sovereignty_line"] = line
    return block
