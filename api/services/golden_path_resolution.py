"""Human-readable golden path line from saved schedule tradeoff MCQs."""

from __future__ import annotations

from typing import Any, Dict, List

_LABELS: Dict[str, Dict[str, str]] = {
    "overlap_resolution_hint": {
        "acknowledged": "Overlaps: acknowledged — resolve in Daily landscape.",
        "later": "Overlaps: deferring clash resolution.",
        "undecided": "Overlaps: still deciding how to reconcile clashes.",
    },
    "work_vs_personal_truth": {
        "work_screenshot": "Work vs API: trusting the screenshot row.",
        "personal_api": "Work vs API: trusting personal/API calendar.",
        "both_partially": "Work vs API: splitting truth across sources.",
        "undecided": "Work vs API: still reconciling.",
    },
    "meeting_tradeoff": {
        "maintain_all": "Load stance: holding the full meeting grid.",
        "decline_low_value": "Load stance: willing to decline a low-value hold.",
        "move_async": "Load stance: moving one block async.",
        "undecided": "Load stance: still choosing a move.",
    },
    "no_60m_slide": {
        "slide_soft_hold": "No 60m window: can slide a soft hold.",
        "protect_prep": "No 60m window: protecting prep — shrink elsewhere.",
        "undecided": "No 60m window: still deciding what slides.",
    },
    "fragmented_batch": {
        "merge_blocks": "Fragmentation: batching/merging blocks to open focus.",
        "keep_as_is": "Fragmentation: keeping the mosaic schedule.",
        "undecided": "Fragmentation: still planning a merge.",
    },
    "runway_reality": {
        "anchor_accurate": "Runway tension: first hard anchor still accurate.",
        "needs_update": "Runway tension: calendar moved — update anchor.",
        "undecided": "Runway tension: still validating anchor.",
    },
    "shorten_meeting_tradeoff": {
        "will_shorten": "Tradeoff: committing to shorten one meeting for deep work.",
        "no_change": "Tradeoff: keeping meetings as scheduled.",
        "undecided": "Tradeoff: still weighing a shorten.",
    },
}


def golden_path_resolution_summary(answers: Dict[str, Any]) -> str:
    if not isinstance(answers, dict) or not answers:
        return ""
    parts: List[str] = []
    order = [
        "overlap_resolution_hint",
        "work_vs_personal_truth",
        "meeting_tradeoff",
        "no_60m_slide",
        "fragmented_batch",
        "runway_reality",
        "shorten_meeting_tradeoff",
    ]
    for key in order:
        val = answers.get(key)
        if not isinstance(val, str):
            continue
        bucket = _LABELS.get(key) or {}
        parts.append(bucket.get(val, f"{key}={val}"))
    return " ".join(parts).strip()
