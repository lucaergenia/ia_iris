import logging
from datetime import datetime
from app.database.database import insert_stats, sessions_Portobelo, sessions_Salvio
from app.client.etecnic_client import get_user_id_from_code, get_user_info
from app.stats_flow.classifier import classify_single_vehicle  # clasifica EV / PHEV

logger = logging.getLogger(__name__)

# 🚀 Pipeline principal
async def run_pipeline():
    logger.info("🚀 Ejecutando pipeline de estadísticas EV/PHEV...")

    # 1️⃣ Obtener sesiones de ambas estaciones
    portobelo_sessions = list(sessions_Portobelo.find())
    salvio_sessions = list(sessions_Salvio.find())
    all_sessions = portobelo_sessions + salvio_sessions

    total_cargas = len(all_sessions)
    logger.info(f"🔍 Total de cargas encontradas: {total_cargas}")

    # 2️⃣ Obtener todos los user_codes únicos
    user_codes = {s.get("user_code") for s in all_sessions if s.get("user_code")}
    logger.info(f"🔍 Total de user_codes únicos encontrados: {len(user_codes)}")

    # 3️⃣ Energía total
    total_energy_Wh = sum(int(s.get("energy_Wh", 0)) for s in all_sessions if s.get("energy_Wh"))
    logger.info(f"🔍 Energía total consumida: {total_energy_Wh} Wh")

    # 4️⃣ Procesar usuarios
    details = []
    ev_count = phev_count = unclassified_count = 0

    for code in user_codes:
        try:
            # Obtener ID de usuario desde el user_code
            user_id = await get_user_id_from_code(code)
            if not user_id:
                logger.warning(f"⚠️ No se encontró user_id para user_code {code}")
                continue

            # Obtener info del usuario
            user_info = await get_user_info(user_id)
            # get_user_info retorna claves 'brand' y 'model'
            brand = user_info.get("brand")
            model = user_info.get("model")

            # Clasificar vehículo (EV / PHEV / unclassified)
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
            logger.error(f"❌ Error procesando user_code {code}: {e}")

    # 5️⃣ Guardar en Mongo
    stats_doc = insert_stats(
        ev_count=ev_count,
        phev_count=phev_count,
        unclassified_count=unclassified_count,
        details=details,
        total_cargas=total_cargas,
        total_usuarios=len(user_codes),
        total_energy_Wh=total_energy_Wh,
    )

    # Agregar campos que espera el frontend
    stats_doc["coches_electricos"] = ev_count
    stats_doc["coches_hibridos"] = phev_count
    stats_doc["coches_totales"] = ev_count + phev_count + unclassified_count

    logger.info("📊 Estadísticas guardadas en MongoDB:")
    logger.info(stats_doc)
    logger.info("✅ Pipeline ejecutado y estadísticas guardadas en MongoDB")

    return stats_doc
