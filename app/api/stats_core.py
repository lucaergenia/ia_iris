from fastapi import APIRouter
from app.stats_flow.pipeline import run_pipeline
from app.database.database import db
from app.services.station_stats import (
    get_station_summary,
    get_station_vehicle_counts,
)

router = APIRouter()


@router.post("/run", tags=["stats"])  # /api/stats/run
async def generate_stats():
    """Ejecuta el pipeline manualmente y guarda resultados en MongoDB."""
    result = await run_pipeline()
    return {"message": "Estadísticas generadas con éxito", "data": result}


@router.get("/last", tags=["stats"])  # /api/stats/last
def get_last_stats(station: str | None = None, filter: str = "total"):
    """Estadísticas para tarjetas del frontend (global y por estación)."""
    if station:
        if station.lower() in ("all", "todas"):
            sum_porto = get_station_summary("Portobelo", filter)
            sum_salvio = get_station_summary("Salvio", filter)
            counts_porto = get_station_vehicle_counts("Portobelo", filter)
            counts_salvio = get_station_vehicle_counts("Salvio", filter)

            total_cargas = sum_porto.get("total_cargas", 0) + sum_salvio.get("total_cargas", 0)
            total_usuarios = sum_porto.get("total_usuarios", 0) + sum_salvio.get("total_usuarios", 0)
            total_energy_Wh = sum_porto.get("total_energy_Wh", 0) + sum_salvio.get("total_energy_Wh", 0)
            total_ingresos = float(sum_porto.get("total_ingresos", 0.0)) + float(sum_salvio.get("total_ingresos", 0.0))
            ev = counts_porto.get("ev_count", 0) + counts_salvio.get("ev_count", 0)
            phev = counts_porto.get("phev_count", 0) + counts_salvio.get("phev_count", 0)
            return {
                "total_cargas": total_cargas,
                "total_usuarios": total_usuarios,
                "total_energy_Wh": total_energy_Wh,
                "ingresos": round(total_ingresos, 2),
                "coches_hibridos": phev,
                "coches_electricos": ev,
                "coches_totales": ev + phev,
            }

        summary = get_station_summary(station, filter)
        counts = get_station_vehicle_counts(station, filter)
        return {
            "total_cargas": summary.get("total_cargas", 0),
            "total_usuarios": summary.get("total_usuarios", 0),
            "total_energy_Wh": summary.get("total_energy_Wh", 0),
            "ingresos": round(float(summary.get("total_ingresos", 0.0)), 2),
            "coches_hibridos": counts.get("phev_count", 0),
            "coches_electricos": counts.get("ev_count", 0),
            "coches_totales": counts.get("phev_count", 0) + counts.get("ev_count", 0),
        }

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

