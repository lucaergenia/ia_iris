# station_stats.py
from datetime import datetime, timedelta
from pymongo.collection import Collection
from app.database.database import (
    sessions_Portobelo,
    sessions_Salvio,
    insert_station_stats,
    get_last_station_stats,
)
from app.client.etecnic_client import get_user_id_from_code, get_user_info
from app.stats_flow.classifier import classify_single_vehicle
import logging

logger = logging.getLogger(__name__)

# ==========================
# Mapear estaciones a colecciones
# ==========================
STATION_COLLECTIONS: dict[str, Collection] = {
    "Portobelo": sessions_Portobelo,
    "Salvio": sessions_Salvio,
}

def _date_filter(filter: str):
    """Genera filtro de fecha según total, mes o día"""
    now = datetime.utcnow()

    if filter == "mes":
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
        return {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    elif filter in ("dia", "diario"):
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        return {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    return {}  # total → sin filtro

def get_station_summary(station_name: str, filter: str):
    """Resumen de cargas de una estación"""
    collection = STATION_COLLECTIONS.get(station_name)
    if collection is None:
        return {"error": f"Estación {station_name} no soportada."}

    query = _date_filter(filter)

    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": None,
                "total_cargas": {"$sum": 1},
                "total_usuarios": {"$addToSet": "$user_code"},
                "total_energy_Wh": {"$sum": {"$toInt": "$energy_Wh"}},
                "total_ingresos": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}
            }
        }
    ]

    result = list(collection.aggregate(pipeline))
    if not result:
        return {"total_cargas": 0, "total_usuarios": 0, "total_energy_Wh": 0}

    r = result[0]
    return {
        "total_cargas": r.get("total_cargas", 0),
        "total_usuarios": len(r.get("total_usuarios", [])),
        "total_energy_Wh": r.get("total_energy_Wh", 0),
        "total_ingresos": r.get("total_ingresos", 0.0),
    }

def get_user_summary(station_name: str, filter: str):
    """Estadísticas por usuario en una estación"""
    collection = STATION_COLLECTIONS.get(station_name)
    if collection is None:
        return {"usuarios": []}

    query = _date_filter(filter)

    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": "$user_code",
                "user_name": {"$first": "$user_name"},
                "total_cargas": {"$sum": 1},
                "total_energy_Wh": {"$sum": {"$toInt": "$energy_Wh"}},
                "total_ingresos": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}
            }
        },
        {"$sort": {"total_cargas": -1}}
    ]

    return list(collection.aggregate(pipeline))


# ==========================
# Clasificación EV/PHEV por estación
# ==========================
async def run_station_pipeline(station_name: str, filter: str = "total") -> dict:
    """
    Para una estación, obtiene los user_codes únicos, consulta al API de ETECNIC
    para obtener marca/modelo, clasifica (EV/PHEV/unclassified) y guarda en Mongo.
    Devuelve el documento insertado.
    """
    collection = STATION_COLLECTIONS.get(station_name)
    if collection is None:
        raise ValueError(f"Estación {station_name} no soportada")

    # Filtrado temporal opcional
    query = _date_filter(filter)
    sessions = list(collection.find(query))

    total_cargas = len(sessions)
    total_energy_Wh = sum(int(s.get("energy_Wh", 0)) for s in sessions if s.get("energy_Wh"))

    user_codes = {s.get("user_code") for s in sessions if s.get("user_code")}

    details = []
    ev_count = phev_count = unclassified_count = 0

    for code in user_codes:
        try:
            user_id = await get_user_id_from_code(code)
            if not user_id:
                logger.warning(f"[{station_name}] Sin user_id para user_code {code}")
                continue

            info = await get_user_info(user_id)
            brand = info.get("brand")
            model = info.get("model")

            category = classify_single_vehicle(brand, model)
            if category == "EV":
                ev_count += 1
            elif category == "PHEV":
                phev_count += 1
            else:
                unclassified_count += 1

            details.append({
                "user_code": code,
                "brand": brand,
                "model": model,
                "category": category,
            })

        except Exception as e:
            logger.error(f"❌ Error en {station_name} con user_code {code}: {e}")

    doc = insert_station_stats(
        station=station_name,
        ev_count=ev_count,
        phev_count=phev_count,
        unclassified_count=unclassified_count,
        details=details,
        total_cargas=total_cargas,
        total_usuarios=len(user_codes),
        total_energy_Wh=total_energy_Wh,
        filter=filter,
    )

    return doc


def get_station_vehicle_counts(station_name: str, filter: str) -> dict:
    """
    Devuelve conteos EV/PHEV/unclassified para una estación y rango de tiempo.
    Usa el set de user_codes del rango y los detalla con la última clasificación disponible.
    """
    collection = STATION_COLLECTIONS.get(station_name)
    if collection is None:
        return {"ev_count": 0, "phev_count": 0, "unclassified_count": 0}

    # Usuarios en el rango solicitado
    query = _date_filter(filter)
    user_codes = {s.get("user_code") for s in collection.find(query) if s.get("user_code")}

    if not user_codes:
        return {"ev_count": 0, "phev_count": 0, "unclassified_count": 0}

    # Preferir último doc del mismo filtro; si no, usar el último disponible
    last = get_last_station_stats(station_name, filter) or get_last_station_stats(station_name)
    details = (last or {}).get("details", [])
    by_code = {d.get("user_code"): d for d in details}

    ev = phev = unclassified = 0
    for code in user_codes:
        cat = (by_code.get(code) or {}).get("category")
        if cat == "EV":
            ev += 1
        elif cat == "PHEV":
            phev += 1
        else:
            unclassified += 1

    return {"ev_count": ev, "phev_count": phev, "unclassified_count": unclassified}
