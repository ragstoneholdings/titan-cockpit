"""Deterministic golden-path proposals (v1). AI-style copy without auto-apply."""

from __future__ import annotations

from typing import Any, Dict, List, Set


def build_rule_based_proposals(
    runway: Dict[str, Any],
    schedule_signals: Dict[str, Any],
    *,
    dismissed: Set[str],
    snoozed: bool,
) -> List[Dict[str, Any]]:
    if snoozed:
        return []
    out: List[Dict[str, Any]] = []

    if runway.get("runway_conflict"):
        cs = runway.get("conflict_summary") or "Default wake cannot clear full protocol before the first hard anchor."
        out.append(
            {
                "id": "runway_conflict",
                "headline": "Resolve morning runway tension",
                "detail": str(cs),
                "deltas": {"kind": "runway_conflict"},
            }
        )

    if not schedule_signals.get("deep_slot_60_available"):
        out.append(
            {
                "id": "no_deep_slot",
                "headline": "No defendable 60m focus window",
                "detail": "Your merged calendar shows no single 60+ minute gap in the awake band. "
                "Either carve one (decline, shorten, or batch) or accept a fragmented execution day.",
                "deltas": {"kind": "schedule_density"},
            }
        )

    if schedule_signals.get("meeting_load_warning"):
        hrs = schedule_signals.get("meeting_load_hours_display") or "many hours"
        out.append(
            {
                "id": "heavy_meeting_load",
                "headline": f"Heavy meeting load (~{hrs})",
                "detail": "Protect one prep block and one outbound slot, or you will run the day in reactive mode.",
                "deltas": {"kind": "meeting_load"},
            }
        )

    if schedule_signals.get("fragmented_day") and not schedule_signals.get("overlap_count"):
        out.append(
            {
                "id": "fragmented_day",
                "headline": "Fragmented gaps",
                "detail": "Short gaps between holds eat deep work. Merge two adjacent soft blocks or move prep earlier.",
                "deltas": {"kind": "fragmentation"},
            }
        )

    if schedule_signals.get("overlap_count", 0) > 0:
        out.append(
            {
                "id": "calendar_overlaps",
                "headline": f"{schedule_signals['overlap_count']} calendar overlap(s)",
                "detail": (
                    "Overlaps mean two feeds claim the same clock time. "
                    "Open **Daily landscape** and use **Overlapping meetings** — pick **Keep event A**, **Keep event B**, "
                    "or **Not sure yet** for each clash. Approve / dismiss here only acknowledges this reminder."
                ),
                "deltas": {"kind": "overlap", "tradeoff_keys_prefix": "overlap:"},
            }
        )

    filtered = [p for p in out if p["id"] not in dismissed]
    return filtered[:5]
