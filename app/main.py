from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from app.stats_flow.pipeline import run_pipeline
import logging

from app.api import stats
from app.services.sync_etecnic import sync_etecnic_data
from app.services.station_stats import run_station_pipeline

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar las rutas de stats con prefijo /api/stats
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

# Servir frontend (index.html + static files)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="frontend")

# Scheduler
scheduler = BackgroundScheduler()

def scheduled_sync():
    logging.info("⏳ Ejecutando sincronización periódica...")
    try:
        import asyncio
        asyncio.run(sync_etecnic_data())
    except Exception as e:
        logging.error(f"❌ Error en sincronización periódica: {e}")

# Actualiza sesiones (cargas/usuarios/energía) cada 15 minutos
scheduler.add_job(scheduled_sync, "interval", minutes=15)


@app.on_event("startup")
async def startup_event():
    logging.info("🚀 Ejecutando sincronización inicial...")
    try:
        await sync_etecnic_data()
        logging.info("✅ Sincronización inicial completada")
    except Exception as e:
        logging.error(f"❌ Error en sincronización inicial: {e}")
    
    logging.info("🚀 Ejecutando pipeline inicial de estadísticas EV/PHEV...")
    try:
        await run_pipeline()
        logging.info("✅ Pipeline ejecutado y estadísticas guardadas en MongoDB")
    except Exception as e:
        logging.error(f"⚠️ Error ejecutando pipeline inicial: {e}")

    # Ejecutar pipelines por estación para tener tarjetas por estación listas
    try:
        await run_station_pipeline("Portobelo")
        await run_station_pipeline("Salvio")
        logging.info("✅ Pipelines por estación ejecutados")
    except Exception as e:
        logging.error(f"⚠️ Error ejecutando pipelines por estación: {e}")

    scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
