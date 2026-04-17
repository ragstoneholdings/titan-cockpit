"""
Posture protocol: high-contrast consistency grid, streak mood, optional neck detail in expander.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None  # type: ignore


def _item_ids(protocol_items: List[Dict[str, Any]]) -> List[str]:
    return [str(x["id"]) for x in protocol_items]


def day_completion_score(snap: Dict[str, Any], protocol_items: List[Dict[str, Any]]) -> int:
    ids = _item_ids(protocol_items)
    return sum(1 for i in ids if snap.get(i))


def streak_full_days_ending_yesterday(
    history: Dict[str, Dict[str, bool]],
    today: date,
    protocol_items: List[Dict[str, Any]],
) -> int:
    """Consecutive calendar days (ending yesterday) with a perfect score."""
    n = len(protocol_items)
    if n <= 0:
        return 0
    d = today - timedelta(days=1)
    streak = 0
    while True:
        snap = history.get(d.isoformat(), {})
        if day_completion_score(snap, protocol_items) >= n:
            streak += 1
            d -= timedelta(days=1)
        else:
            break
        if streak > 400:
            break
    return streak


def protocol_dashboard_mood_class(
    history: Dict[str, Dict[str, bool]],
    today: date,
    protocol_items: List[Dict[str, Any]],
) -> str:
    """Cold when the chain is broken (no full days through yesterday); hot when streak is alive."""
    if streak_full_days_ending_yesterday(history, today, protocol_items) > 0:
        return "protocol-dashboard--hot"
    return "protocol-dashboard--cold"


def _heatmap_matrix(
    history: Dict[str, Dict[str, bool]],
    today: date,
    protocol_items: List[Dict[str, Any]],
    num_weeks: int = 8,
) -> Tuple[List[List[float]], List[str], List[str]]:
    """Rows = weeks (oldest first), cols = Mon..Sun; cell = completion fraction 0..1."""
    n = len(protocol_items)
    if n <= 0:
        return [], [], []
    mon_anchor = today - timedelta(days=today.weekday())
    xlabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    z: List[List[float]] = []
    ylabels: List[str] = []
    for w in range(num_weeks - 1, -1, -1):
        week_mon = mon_anchor - timedelta(weeks=w)
        row: List[float] = []
        for i in range(7):
            d = week_mon + timedelta(days=i)
            snap = history.get(d.isoformat(), {})
            row.append(day_completion_score(snap, protocol_items) / float(n))
        z.append(row)
        ylabels.append(week_mon.strftime("%b %d"))
    return z, xlabels, ylabels


def _discrete_consistency_z(z: List[List[float]], n_items: int) -> List[List[int]]:
    """Integer levels 0..n_items for high-contrast grid."""
    if n_items <= 0:
        return []
    out: List[List[int]] = []
    for row in z:
        out.append([min(n_items, max(0, int(round(v * n_items)))) for v in row])
    return out


def _neck_chart_dates_values(neck_cm: Dict[str, float]) -> Tuple[List[str], List[float]]:
    pairs = sorted((k, float(v)) for k, v in neck_cm.items() if k and v and float(v) > 0)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    return xs, ys


def render_protocol_week_dashboard(
    st: Any,
    today: date,
    history: Dict[str, Dict[str, bool]],
    protocol_items: List[Dict[str, Any]],
    neck_cm: Dict[str, float],
) -> None:
    mood = protocol_dashboard_mood_class(history, today, protocol_items)
    streak = streak_full_days_ending_yesterday(history, today, protocol_items)
    n_items = len(protocol_items)
    st.markdown(
        f'<div class="protocol-monolith protocol-well-recessed {mood}">'
        f'<p class="protocol-streak-line"><span class="protocol-streak-label">Streak</span> '
        f"<strong>{streak}</strong> full day(s) through yesterday · "
        f'{"Chain live — keep the heat." if "hot" in mood else "Cold state — reclaim yesterday’s standard."}'
        f"</p></div>",
        unsafe_allow_html=True,
    )

    z, xlabels, ylabels = _heatmap_matrix(history, today, protocol_items)
    if go is not None and z and n_items > 0:
        z_int = _discrete_consistency_z(z, n_items)
        fig = go.Figure(
            data=go.Heatmap(
                z=z_int,
                x=xlabels,
                y=ylabels,
                colorscale=[
                    [0.0, "#030508"],
                    [0.25, "#0a0e14"],
                    [0.5, "#1a2432"],
                    [0.75, "#3d4a5c"],
                    [1.0, "#e8b84d"],
                ],
                zmin=0,
                zmax=n_items,
                xgap=3,
                ygap=3,
                colorbar=dict(
                    title="",
                    tickmode="array",
                    tickvals=list(range(n_items + 1)),
                    ticktext=[str(i) for i in range(n_items + 1)],
                    len=0.45,
                    outlinewidth=0,
                    tickfont=dict(color="#8899aa", size=10),
                ),
            )
        )
        fig.update_layout(
            title="Consistency grid (8 weeks)",
            paper_bgcolor="rgba(3,5,10,0.97)",
            plot_bgcolor="rgba(3,5,10,0.97)",
            font=dict(color="#9aa8b8", family="Montserrat, sans-serif", size=11),
            title_font=dict(size=13, color="#f7d491"),
            margin=dict(l=8, r=8, t=44, b=8),
            height=300 + min(14, len(z_int)) * 20,
            xaxis=dict(side="bottom", showgrid=True, gridcolor="rgba(255,255,255,0.06)", gridwidth=1),
            yaxis=dict(
                autorange="reversed",
                showgrid=True,
                gridcolor="rgba(255,255,255,0.06)",
                gridwidth=1,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif not z:
        st.caption("No week grid yet — log days to populate the consistency grid.")
    else:
        st.info("Install **plotly** for the consistency grid: `pip install plotly`")

    xs, ys = _neck_chart_dates_values(neck_cm)
    with st.expander("Neck circumference (optional detail)", expanded=False):
        if go is not None and len(xs) >= 2:
            fig2 = go.Figure(
                data=go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines+markers",
                    line=dict(color="#5a9fff", width=2),
                    marker=dict(size=7, color="#f7d491"),
                )
            )
            fig2.update_layout(
                title="Neck (cm) over time",
                paper_bgcolor="rgba(3,5,10,0.97)",
                plot_bgcolor="rgba(3,5,10,0.97)",
                font=dict(color="#9aa8b8", family="Montserrat, sans-serif", size=11),
                title_font=dict(size=12, color="#f7d491"),
                margin=dict(l=8, r=8, t=36, b=8),
                height=220,
                xaxis=dict(title="Date"),
                yaxis=dict(title="cm"),
            )
            st.plotly_chart(fig2, use_container_width=True)
        elif len(xs) == 1:
            st.caption(f"**{xs[0]}** = {ys[0]:.1f} cm — add another log for a line chart.")
        else:
            st.caption("No neck measurements logged yet.")

    days = [today - timedelta(days=today.weekday()) + timedelta(days=i) for i in range(7)]
    rows: List[Dict[str, Any]] = []
    for d in days:
        ds = d.isoformat()
        snap = history.get(ds, {})
        n_ok = day_completion_score(snap, protocol_items)
        row: Dict[str, Any] = {"Day": d.strftime("%a"), "Date": ds}
        for it in protocol_items:
            row[str(it["label"])] = "✓" if snap.get(it["id"]) else "—"
        row["Score"] = f"{n_ok}/{len(protocol_items)}"
        rows.append(row)
    with st.expander("This week checklist (detail)", expanded=False):
        try:
            import pandas as pd

            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        except Exception:
            st.table(rows)
