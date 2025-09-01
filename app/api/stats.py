from fastapi import APIRouter
from app.stats_flow.pipeline import run_pipeline
from app.database.database import db, get_last_station_stats
from app.services.station_stats import (
    get_station_summary,
    get_user_summary,
    run_station_pipeline,
    get_station_vehicle_counts,
)

router = APIRouter()

# 1. Ejecutar pipeline y guardar estadísticas
@router.post("/run", tags=["stats"])  # final: /api/stats/run
async def generate_stats():
    """
    Ejecuta el pipeline manualmente y guarda los resultados en MongoDB.
    """
    result = await run_pipeline()
    return {"message": "Estadísticas generadas con éxito", "data": result}


# 2. Últimas estadísticas globales
@router.get("/last", tags=["stats"])  # final: /api/stats/last
def get_last_stats(station: str | None = None, filter: str = "total"):
    """
    Devuelve estadísticas para tarjetas del frontend.
    - Globales cuando no se especifica estación.
    - Por estación cuando se pasa ?station=Portobelo|Salvio (usa resumen de sesiones + último conteo EV/PHEV de la estación).
    """
    if station:
        # Agregado entre estaciones cuando station = all/todas
        if station.lower() in ("all", "todas"):
            sum_porto = get_station_summary("Portobelo", filter)
            sum_salvio = get_station_summary("Salvio", filter)
            counts_porto = get_station_vehicle_counts("Portobelo", filter)
            counts_salvio = get_station_vehicle_counts("Salvio", filter)

            total_cargas = sum_porto.get("total_cargas", 0) + sum_salvio.get("total_cargas", 0)
            total_usuarios = sum_porto.get("total_usuarios", 0) + sum_salvio.get("total_usuarios", 0)
            total_energy_Wh = sum_porto.get("total_energy_Wh", 0) + sum_salvio.get("total_energy_Wh", 0)
            ev = counts_porto.get("ev_count", 0) + counts_salvio.get("ev_count", 0)
            phev = counts_porto.get("phev_count", 0) + counts_salvio.get("phev_count", 0)
            return {
                "total_cargas": total_cargas,
                "total_usuarios": total_usuarios,
                "total_energy_Wh": total_energy_Wh,
                "coches_hibridos": phev,
                "coches_electricos": ev,
                "coches_totales": ev + phev,
            }

        # Resumen de cargas/usuarios/energía por estación (en vivo desde colecciones de la estación)
        summary = get_station_summary(station, filter)
        # Conteo EV/PHEV basado en usuarios del rango y última clasificación disponible
        counts = get_station_vehicle_counts(station, filter)

        return {
            "total_cargas": summary.get("total_cargas", 0),
            "total_usuarios": summary.get("total_usuarios", 0),
            "total_energy_Wh": summary.get("total_energy_Wh", 0),
            "coches_hibridos": counts.get("phev_count", 0),
            "coches_electricos": counts.get("ev_count", 0),
            "coches_totales": counts.get("phev_count", 0) + counts.get("ev_count", 0),
        }
    else:
        # Últimas estadísticas globales (colección stats)
        last_stat = db.stats.find_one(sort=[("timestamp", -1)])
        if not last_stat:
            return {"message": "No existen estadísticas registradas aún."}

        last_stat["_id"] = str(last_stat["_id"])
        return {
            "total_cargas": last_stat.get("total_cargas", 0),
            "total_usuarios": last_stat.get("total_usuarios", 0),
            "total_energy_Wh": last_stat.get("total_energy_Wh", 0),
            "coches_hibridos": last_stat.get("phev_count", 0),
            "coches_electricos": last_stat.get("ev_count", 0),
            "coches_totales": last_stat.get("phev_count", 0) + last_stat.get("ev_count", 0),
        }


# 3. Listado de usuarios por estación
@router.get("/users/{station}", tags=["stats"])  # final: /api/stats/users/{station}
def get_users_stats(station: str, filter: str = "total"):
    """
    Devuelve el listado de usuarios con cargas y energía acumulada por estación.
    """
    # Listado agregado para todas las estaciones
    if station.lower() in ("all", "todas"):
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
    # Enriquecer con modelo/tipo desde último pipeline por estación
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


# ==========================
# Endpoints por estación
# ==========================
@router.get("/stations/{station}/summary", tags=["stats"])  # /api/stats/stations/{station}/summary
def station_summary(station: str, filter: str = "total"):
    return get_station_summary(station, filter)

@router.get("/stations/{station}/users", tags=["stats"])  # /api/stats/stations/{station}/users
def station_users(station: str, filter: str = "total"):
    usuarios = get_user_summary(station, filter)
    # Enriquecer con modelo/tipo desde último pipeline por estación
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

@router.post("/stations/{station}/run", tags=["stats"])  # /api/stats/stations/{station}/run
async def station_run(station: str, filter: str = "total"):
    doc = await run_station_pipeline(station, filter)
    # campos para frontend
    doc["coches_electricos"] = doc.get("ev_count", 0)
    doc["coches_hibridos"] = doc.get("phev_count", 0)
    doc["coches_totales"] = doc.get("ev_count", 0) + doc.get("phev_count", 0) + doc.get("unclassified_count", 0)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

@router.get("/stations/{station}/last", tags=["stats"])  # /api/stats/stations/{station}/last
def station_last(station: str, filter: str = "total"):
    doc = get_last_station_stats(station, filter)
    if not doc:
        return {"message": f"No existen estadísticas registradas aún para {station}."}
    # campos para frontend
    doc["coches_electricos"] = doc.get("ev_count", 0)
    doc["coches_hibridos"] = doc.get("phev_count", 0)
    doc["coches_totales"] = doc.get("ev_count", 0) + doc.get("phev_count", 0) + doc.get("unclassified_count", 0)
    doc["_id"] = str(doc["_id"])
    return doc

@router.get("/stations/{station}/cards", tags=["stats"])  # /api/stats/stations/{station}/cards
def station_cards(station: str, filter: str = "total"):
    """
    Devuelve las tarjetas de resumen para una estación con la misma forma que /api/stats/last.
    Usa el último documento de stats por estación.
    """
    # Totales en vivo desde sesiones + EV/PHEV por usuarios del rango
    summary = get_station_summary(station, filter)
    counts = get_station_vehicle_counts(station, filter)
    return {
        "total_cargas": summary.get("total_cargas", 0),
        "total_usuarios": summary.get("total_usuarios", 0),
        "total_energy_Wh": summary.get("total_energy_Wh", 0),
        "coches_hibridos": counts.get("phev_count", 0),
        "coches_electricos": counts.get("ev_count", 0),
        "coches_totales": counts.get("phev_count", 0) + counts.get("ev_count", 0),
    }
