from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path
import shutil
import traceback

# Imports
from app.services.detector_matriculas.detector import detectar_matriculas_en_video
from app.services.detector_matriculas.enrichment import procesar_info
from app.services.detector_matriculas.etecnic_client import obtener_dueno
from app.services.detector_matriculas.extraer_frames_s3 import download_video, extraer_frames

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Paths
VIDEO_PATH = Path("video_temp.mp4")
FRAMES_DIR = Path("frames_local")

@app.get("/")
async def root():
    index_path = Path("static/index.html")
    if not index_path.exists():
        return HTMLResponse("<h1>Error: No se encontró index.html en /static</h1>", status_code=500)
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/procesar_matriculas")
async def procesar_matriculas():
    try:
        # Descargar video desde S3
        download_video()

        # Limpiar frames previos
        if FRAMES_DIR.exists():
            shutil.rmtree(FRAMES_DIR)

        # Extraer frames
        extraer_frames()

        # Detectar matrículas en el video
        resultados_raw = await detectar_matriculas_en_video(str(VIDEO_PATH))

        if not resultados_raw:
            return JSONResponse(content={"error": "No se detectaron matrículas"}, status_code=404)

        resultados_finales = []

        for r in resultados_raw:
            matricula = r.get("matricula")
            if not matricula:
                continue

            # Obtener datos del dueño y vehículo
            dueno_json = await obtener_dueno(matricula)
            if not dueno_json:
                continue

            info = procesar_info(dueno_json)
            if not info:
                continue

            resultados_finales.append(info)

        if not resultados_finales:
            return JSONResponse(content={"error": "No se pudo procesar información de las matrículas"}, status_code=404)

        return JSONResponse(content=resultados_finales)

    except Exception as e:
        print("❌ ERROR procesando matrículas:")
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(
        "app.services.detector_matriculas.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )