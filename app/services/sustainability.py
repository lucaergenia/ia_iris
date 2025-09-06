from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Iterable

from pymongo.collection import Collection

from app.database.database import sessions_Portobelo, sessions_Salvio


# ==========================
# Configuración (vía variables de entorno opcionalmente)
# ==========================
import os


def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


# kg CO2 por kWh de la red eléctrica (promedio). Ajustable por entorno.
GRID_CO2_KG_PER_KWH = _get_env_float("EMISSION_FACTOR_GRID_KG_PER_KWH", 0.20)
# Emisiones de un vehículo ICE (combustión) en kg CO2 por km.
ICE_CO2_KG_PER_KM = _get_env_float("ICE_EMISSIONS_KG_PER_KM", 0.17)
# Eficiencia típica EV (km recorridos por kWh).
EV_KM_PER_KWH = _get_env_float("EV_EFFICIENCY_KM_PER_KWH", 6.0)


# ==========================
# Utilidades de tiempo y colecciones
# ==========================
STATION_COLLECTIONS: dict[str, Collection] = {
    "Portobelo": sessions_Portobelo,
    "Salvio": sessions_Salvio,
}


def _date_bounds_for_filter(filter: str) -> tuple[datetime | None, datetime | None]:
    now = datetime.utcnow()
    if filter == "mes":
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
        return start, end
    elif filter in ("dia", "diario"):
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        return start, end
    # total
    return None, None


def _unit_for_period(period: str, default_for_filter: str | None = None) -> Literal["hour", "day", "month"]:
    period = (period or "").lower()
    if period in ("hora", "hour", "hours"):
        return "hour"
    if period in ("dia", "día", "day", "daily"):
        return "day"
    if period in ("mes", "mensual", "month", "monthly"):
        return "month"
    # fallback basado en filtro si se proporciona
    if default_for_filter in ("diario", "dia"):
        return "hour"
    if default_for_filter == "mes":
        return "day"
    return "month"


def _aggregate_energy_per(collection: Collection, start: datetime | None, end: datetime | None, unit: Literal["hour", "day", "month"]) -> list[dict]:
    match: dict = {}
    if start and end:
        match = {
            "session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}
        }
    pipeline = [
        {"$match": match},
        {
            "$addFields": {
                "_start": {"$toDate": "$session_start_at"},
                "_energy": {"$toInt": {"$ifNull": ["$energy_Wh", 0]}},
            }
        },
        {
            "$group": {
                "_id": {"$dateTrunc": {"date": "$_start", "unit": unit}},
                "energy_Wh": {"$sum": "$_energy"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    return list(collection.aggregate(pipeline))


def _merge_timeseries(rows_list: Iterable[list[dict]]) -> list[dict]:
    buckets: dict[datetime, int] = {}
    for rows in rows_list:
        for r in rows:
            ts = r.get("_id")
            val = int(r.get("energy_Wh", 0) or 0)
            if isinstance(ts, datetime):
                buckets[ts] = buckets.get(ts, 0) + val
    out = [{"period_start": k.isoformat(), "energy_Wh": v} for k, v in buckets.items()]
    out.sort(key=lambda x: x["period_start"])  # ascending
    return out


def get_energy_series(station: str, filter: str = "total", period: str | None = None) -> dict:
    start, end = _date_bounds_for_filter(filter)
    unit = _unit_for_period(period or "", default_for_filter=filter)

    if station and station not in ("all", "todas", "todas las estaciones"):
        coll = STATION_COLLECTIONS.get(station)
        if coll is None:
            return {"series": []}
        rows = _aggregate_energy_per(coll, start, end, unit)
        return {"series": _merge_timeseries([rows])}

    # all stations: merge both
    rows_a = _aggregate_energy_per(sessions_Portobelo, start, end, unit)
    rows_b = _aggregate_energy_per(sessions_Salvio, start, end, unit)
    return {"series": _merge_timeseries([rows_a, rows_b])}


def _sum_energy_wh(collection: Collection, start: datetime | None, end: datetime | None) -> int:
    match: dict = {}
    if start and end:
        match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": None, "energy_Wh": {"$sum": {"$toInt": {"$ifNull": ["$energy_Wh", 0]}}}}},
    ]
    rows = list(collection.aggregate(pipeline))
    return int((rows[0] or {}).get("energy_Wh", 0)) if rows else 0


def compute_co2_equivalents(total_energy_Wh: int) -> dict:
    kwh = float(total_energy_Wh or 0) / 1000.0
    co2_grid_kg = kwh * GRID_CO2_KG_PER_KWH
    km_equiv = kwh * EV_KM_PER_KWH
    co2_ice_kg = km_equiv * ICE_CO2_KG_PER_KM
    co2_avoided_kg = co2_ice_kg - co2_grid_kg
    return {
        "energy_kWh": round(kwh, 3),
        "co2_grid_kg": round(co2_grid_kg, 3),
        "co2_ice_equiv_kg": round(co2_ice_kg, 3),
        "co2_avoided_kg": round(co2_avoided_kg, 3),
        "assumptions": {
            "GRID_CO2_KG_PER_KWH": GRID_CO2_KG_PER_KWH,
            "ICE_CO2_KG_PER_KM": ICE_CO2_KG_PER_KM,
            "EV_KM_PER_KWH": EV_KM_PER_KWH,
        },
    }


def get_energy_summary(station: str, filter: str = "total") -> dict:
    start, end = _date_bounds_for_filter(filter)
    if station and station not in ("all", "todas", "todas las estaciones"):
        coll = STATION_COLLECTIONS.get(station)
        if coll is None:
            total_wh = 0
        else:
            total_wh = _sum_energy_wh(coll, start, end)
    else:
        total_wh = _sum_energy_wh(sessions_Portobelo, start, end) + _sum_energy_wh(sessions_Salvio, start, end)

    co2 = compute_co2_equivalents(total_wh)
    return {
        "total_energy_Wh": total_wh,
        **co2,
    }
