from fastapi import APIRouter
from app.database.database import get_last_station_stats
from app.services.station_stats import get_user_summary

router = APIRouter()


@router.get("/users/{station}", tags=["stats"])  # /api/stats/users/{station}
def get_users_stats(station: str, filter: str = "total"):
    """Listado de usuarios con cargas/energía por estación o agregado."""
    if station.lower() in ("all", "todas"):
        from app.services.station_stats import get_station_summary  # noqa: F401 (mantener import local si se requiere en futuro)
        users_porto = get_user_summary("Portobelo", filter)
        users_salvio = get_user_summary("Salvio", filter)
        merged: dict[str, dict] = {}
        for src in (users_porto, users_salvio):
            for u in src:
                key = u.get("_id")
                if not key:
                    continue
                m = merged.setdefault(key, {
                    "_id": key,
                    "user_name": u.get("user_name"),
                    "total_cargas": 0,
                    "total_energy_Wh": 0,
                })
                m["total_cargas"] += u.get("total_cargas", 0)
                m["total_energy_Wh"] += u.get("total_energy_Wh", 0)

        last_porto = get_last_station_stats("Portobelo", filter) or get_last_station_stats("Portobelo") or {}
        last_salvio = get_last_station_stats("Salvio", filter) or get_last_station_stats("Salvio") or {}
        details_map = {d.get("user_code"): d for d in last_porto.get("details", [])}
        details_map.update({d.get("user_code"): d for d in last_salvio.get("details", [])})

        usuarios = []
        for u in merged.values():
            out = {
                "user_code": u.get("_id"),
                "user_name": u.get("user_name"),
                "total_cargas": u.get("total_cargas", 0),
                "total_energy_Wh": u.get("total_energy_Wh", 0),
            }
            info = details_map.get(out["user_code"], {})
            if info:
                out["brand"] = info.get("brand")
                out["model"] = info.get("model")
                out["category"] = info.get("category")
            usuarios.append(out)
        usuarios.sort(key=lambda x: x.get("total_cargas", 0), reverse=True)
        return {"usuarios": usuarios}

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

