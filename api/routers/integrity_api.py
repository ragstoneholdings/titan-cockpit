"""Physical Integrity stats JSON (sidebar)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from integrity_stats_store import load_bundle, save_bundle

router = APIRouter(prefix="/integrity", tags=["integrity"])


@router.get("/stats")
def get_integrity_stats() -> Dict[str, Any]:
    return load_bundle()


@router.put("/stats")
def put_integrity_stats(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    cur = load_bundle()
    for k, v in body.items():
        if k == "version":
            continue
        cur[k] = v
    save_bundle(cur)
    return load_bundle()
