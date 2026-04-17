"""QuickBooks Online — scaffold for Phase B (OAuth + reports).

Not wired: implement token storage, PII-safe logging, and read-only scopes
when you register an Intuit app. See ragstone_ledger_store for manual KPIs until then.
"""

from __future__ import annotations

from typing import Any, Dict


def qbo_placeholder() -> Dict[str, Any]:
    return {"status": "not_implemented", "message": "Use ragstone_ledger.json or Zapier inbound until QBO OAuth is configured."}
