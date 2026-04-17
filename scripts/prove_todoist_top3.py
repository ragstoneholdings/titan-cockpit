#!/usr/bin/env python3
"""
Terminal proof: print top 3 Todoist task IDs and titles.
Uses GEMINI_API_KEY + ranking when set; otherwise first three tasks by list order.

Usage (from project root):
  python scripts/prove_todoist_top3.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from todoist_service import (  # noqa: E402
    fetch_all_tasks_rest_v2,
    fetch_todoist_projects,
    normalize_power_task,
    rank_tasks_for_power_trio,
    sort_known_ids_by_priority,
    validate_and_fill_order,
)


def main() -> int:
    key = os.environ.get("TODOIST_API_KEY", "").strip()
    if not key:
        print("Set TODOIST_API_KEY in the environment.", file=sys.stderr)
        return 1
    try:
        raw = fetch_all_tasks_rest_v2(key)
    except Exception as e:
        print(f"Todoist fetch failed: {e}", file=sys.stderr)
        return 1
    pmap = fetch_todoist_projects(key)
    by_id: dict = {}
    for t in raw:
        nt = normalize_power_task(t, pmap)
        tid = nt.get("id")
        if tid:
            by_id[tid] = nt
    if not by_id:
        print("No active tasks returned.")
        return 0

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ranked: list
    if gemini_key:
        try:
            import google.generativeai as genai

            genai.configure(api_key=gemini_key)
            model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            today = date.today()
            ranked, warn = rank_tasks_for_power_trio(
                genai,
                model,
                by_id,
                purpose=os.environ.get("POWER_PURPOSE_STATEMENT", ""),
                ragstone_strategy=os.environ.get("POWER_RAGSTONE_STRATEGY", ""),
                scaled_ops=os.environ.get("POWER_SCALED_OPS", ""),
                weekday_name=today.strftime("%A"),
                is_weekend=today.weekday() >= 5,
                identity_project_substr=[
                    x.strip()
                    for x in os.environ.get("POWER_IDENTITY_PROJECT_SUBSTRINGS", "Ragstone,Home").split(",")
                    if x.strip()
                ],
                google_ops_substr=[
                    x.strip()
                    for x in os.environ.get("POWER_GOOGLE_OPS_SUBSTRINGS", "Google,Work").split(",")
                    if x.strip()
                ],
            )
            if warn:
                print(f"# {warn}", file=sys.stderr)
        except Exception as e:
            print(f"Gemini rank failed ({e}); using list order.", file=sys.stderr)
            ranked = validate_and_fill_order(list(by_id.keys()), list(by_id.keys()))
    else:
        print("# No GEMINI_API_KEY; using first three by Todoist priority fallback.", file=sys.stderr)
        ranked = sort_known_ids_by_priority(by_id, list(by_id.keys()))

    top = ranked[:3]
    for tid in top:
        t = by_id.get(tid, {})
        title = str(t.get("content") or "(no title)")
        print(f"{tid}\t{title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
