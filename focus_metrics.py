"""Focus Score from Power Trio execution counts (heuristic deep / mixed / shallow)."""

from __future__ import annotations

# Default: warn when deep focus share is below this percent.
FOCUS_DANGER_THRESHOLD = 20.0


def focus_score_percent(deep: int, mixed: int, shallow: int) -> float:
    """Mixed slots count half toward 'deep' in the numerator (Momentum = mixed)."""
    total = deep + mixed + shallow
    if total <= 0:
        return 0.0
    return (deep + 0.5 * mixed) / float(total) * 100.0
