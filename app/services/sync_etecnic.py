from app.database.database import sessions_Portobelo, sessions_Salvio
from app.client.etecnic_client import get_charger_charges
import logging

STATIONS = {
    "Portobelo": [31033, 31150],
    "Salvio": [31726, 31727],
}

async def sync_etecnic_data():
    results = {}
    for station, ids in STATIONS.items():
        all_sessions = []
        for sid in ids:
            resp = await get_charger_charges(sid)   # 👈 devuelve dict
            charges = resp.get("charges", [])       # 👈 lista de sesiones
            all_sessions.extend(charges)

        # Seleccionar colección Mongo
        col = sessions_Portobelo if station.lower() == "portobelo" else sessions_Salvio

        inserted = 0
        for s in all_sessions:
            if "charge_id" not in s:
                continue
            col.update_one({"charge_id": s["charge_id"]}, {"$set": s}, upsert=True)
            inserted += 1

        logging.info(f"✅ {station}: {inserted} sesiones sincronizadas")
        results[station] = inserted

    return results
