from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, PlainTextResponse, RedirectResponse
from apscheduler.schedulers.background import BackgroundScheduler
from app.stats_flow.pipeline import run_pipeline
import logging

from app.api import router as api_router
from app.services.sync_etecnic import sync_etecnic_data
from app.services.station_stats import run_station_pipeline
from app.services.executive import materialize_all_scopes

import os

# ==== Logging policy (silence logs in production) ====
LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "WARNING").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.WARNING)
logging.basicConfig(level=LOG_LEVEL)

# Reduce noisy third‑party loggers
for name in (
    "httpx",
    "apscheduler",
    "apscheduler.scheduler",
    "apscheduler.executors.default",
    "uvicorn",
    "uvicorn.error",
):
    try:
        logging.getLogger(name).setLevel(LOG_LEVEL)
    except Exception:
        pass

# Access log (HTTP request per line) can leak info; disable by default
if os.getenv("ACCESS_LOG_DISABLED", "true").lower() == "true":
    try:
        al = logging.getLogger("uvicorn.access")
        al.setLevel(logging.CRITICAL)
        al.propagate = False
        al.disabled = True
        al.handlers = []
    except Exception:
        pass

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
app.include_router(api_router, prefix="/api/stats")

# ============ Simple auth middleware (cookie-based) ============
from app.auth.security import verify_access_token
from app.database.database import db

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    if not AUTH_REQUIRED:
        return await call_next(request)
    path = request.url.path
    # Allowlist for login and static assets
    if (
        path.startswith("/api/auth/") or
        path.startswith("/api/stats/auth/") or  # permitir login bajo el prefijo /api/stats
        path.startswith("/static/") or path == "/login.html" or path == "/favicon.ico"
    ):
        return await call_next(request)

    token = request.cookies.get("access_token")
    uid = verify_access_token(token or "")
    if not uid:
        if path.startswith("/api/"):
            return PlainTextResponse("No autenticado", status_code=401)
        return RedirectResponse(url="/login.html")

    # Attach user info optionally
    try:
        from bson import ObjectId
        request.state.user = db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
    except Exception:
        request.state.user = None
    return await call_next(request)

"""
Streaming RTSP
Rutas SIEMPRE registradas con logs detallados. La cámara se crea bajo demanda.
Utiliza la misma construcción de URL que el script simple.
"""
from typing import Optional

# Log dedicado para streaming
stream_logger = logging.getLogger("streaming.rtsp")
stream_logger.setLevel(LOG_LEVEL)

_RTSPCamera = None
_build_url = None
try:
    # Nuevo módulo simple de streaming
    from app.streaming.rtsp_feed import RTSPCamera as _RTSPCamera  # noqa: N816
    from app.streaming.rtsp_feed import build_rtsp_url as _build_url  # noqa: N816
except Exception as e:  # import error no impide registrar ruta
    stream_logger.warning(f"Import parcial para streaming: {e}")

_camera: Optional[object] = None

def _get_camera():
    global _camera
    if _RTSPCamera is None or _build_url is None:
        raise RuntimeError("Dependencias de streaming no disponibles")
    if _camera is None:
        url = _build_url()
        stream_logger.info("Inicializando RTSPCamera…")
        _camera = _RTSPCamera(url)
    return _camera


@app.get("/api/stream/rtsp")
def stream_rtsp(request: Request, width: int | None = None, q: int | None = 95):
    stream_logger.info(f"Solicitud de stream: width={width}, q={q}")
    try:
        cam = _get_camera()
    except Exception as e:
        stream_logger.error(f"No se pudo inicializar cámara: {e}")
        return PlainTextResponse(f"Streaming no inicializado: {e}", status_code=500)
    max_w = width or 0
    return StreamingResponse(
        cam.frames(max_width=max_w, quality=(q or 95)),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/stream/rtsp/snapshot")
def stream_snapshot(width: int | None = None, q: int | None = 95):
    stream_logger.info(f"Solicitud de snapshot: width={width}, q={q}")
    try:
        cam = _get_camera()
    except Exception as e:
        stream_logger.error(f"No se pudo inicializar cámara: {e}")
        return PlainTextResponse(f"Streaming no inicializado: {e}", status_code=500)
    gen = cam.frames(max_width=width or 0, quality=(q or 95))
    try:
        chunk = next(gen)
    except StopIteration:
        stream_logger.error("Generador sin frames")
        return PlainTextResponse("No se pudo obtener frame", status_code=500)
    boundary = b"\r\n\r\n"
    try:
        header_end = chunk.index(boundary) + len(boundary)
        body = chunk[header_end:-2]
    except ValueError:
        body = chunk
    return StreamingResponse(iter([body]), media_type="image/jpeg")

# Servir frontend (index.html + static files)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
# Scheduler
scheduler = BackgroundScheduler()

def scheduled_sync():
    """Trabajo en hilo aparte que actualiza datos cada 15 minutos.
    Ejecuta toda la cadena para mantener stats al día sin bloquear el servidor.
    """
    logging.info("⏳ Ejecutando sincronización periódica...")
    try:
        import asyncio

        async def full_refresh():
            try:
                await sync_etecnic_data()
            except Exception as e:
                logging.error(f"❌ Error en sync etecnic: {e}")
            try:
                await run_pipeline()
            except Exception as e:
                logging.error(f"❌ Error en pipeline global: {e}")
            for st in ("Portobelo", "Salvio"):
                try:
                    await run_station_pipeline(st)
                except Exception as e:
                    logging.error(f"❌ Error en pipeline estación {st}: {e}")
            # KPIs ejecutivos materializados (global y por estación)
            try:
                materialize_all_scopes()
            except Exception as e:
                logging.error(f"❌ Error materializando KPIs ejecutivos: {e}")

        asyncio.run(full_refresh())
        logging.info("✅ Sincronización periódica completada")
    except Exception as e:
        logging.error(f"❌ Error en sincronización periódica: {e}")

# Actualiza sesiones (cargas/usuarios/energía) cada 15 minutos
scheduler.add_job(scheduled_sync, "interval", minutes=15)


@app.on_event("startup")
async def startup_event():
    """No bloquea el arranque. Sirve datos previos y refresca en background."""
    import asyncio

    async def initial_refresh():
        logging.info("🚀 Sincronización inicial en background...")
        try:
            await sync_etecnic_data()
            await run_pipeline()
            await run_station_pipeline("Portobelo")
            await run_station_pipeline("Salvio")
            logging.info("✅ Refresco inicial completado")
        except Exception as e:
            logging.error(f"⚠️ Error en refresco inicial: {e}")

    # Lanzar tareas sin bloquear el inicio
    asyncio.create_task(initial_refresh())

    # Iniciar scheduler periódico
    scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
