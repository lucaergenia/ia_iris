from fastapi import APIRouter
from typing import Optional

from app.services.executive import (
    compute_executive_summary,
    latest_executive_summary,
)

router = APIRouter()


@router.get("/executive/summary", tags=["executive"])  # /api/stats/executive/summary
def executive_summary(
    station: Optional[str] = None,
    month: Optional[str] = None,
    materialized: bool = False,
):
    st = None if (not station or station.lower() in ("all", "todas")) else station
    if materialized:
        doc = latest_executive_summary(st)
        if doc:
            doc.pop("_id", None)
            return doc
        # fallback a cálculo en vivo si no hay materializado
    return compute_executive_summary(station=st, month=month)

