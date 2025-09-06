from fastapi import APIRouter
from app.database.database import get_last_station_stats
from app.services.station_stats import get_station_summary, get_user_summary

router = APIRouter()


@router.get("/stations/{station}/summary", tags=["stats"])  # /api/stats/stations/{station}/summary
def station_summary(station: str, filter: str = "total"):
    return get_station_summary(station, filter)


@router.get("/stations/{station}/users", tags=["stats"])  # /api/stats/stations/{station}/users
def station_users(station: str, filter: str = "total"):
    usuarios = get_user_summary(station, filter)
    last = get_last_station_stats(station) or {}
    details = last.get("details", [])
    by_code = {d.get("user_code"): d for d in details}

    for u in usuarios:
        u["user_code"] = u.get("_id")
        if "_id" in u:
            del u["_id"]
        info = by_code.get(u["user_code"], {})
        if info:
            u["brand"] = info.get("brand")
            u["model"] = info.get("model")
            u["category"] = info.get("category")
    return {"usuarios": usuarios}

