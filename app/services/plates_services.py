import shutil
import traceback
from pathlib import Path

# Importa tus módulos existentes
from app.scripts.detector import detectar_matriculas_en_video
from app.scripts.enrichment import procesar_info
from app.client.etecnic_client import EtecnicClient
from app.client.extraer_frames_s3 import download_video, extraer_frames

# Paths locales
VIDEO_PATH = Path("video_temp.mp4")
FRAMES_DIR = Path("frames_local")

async def procesar_matriculas_service():
    """
    Lógica completa de procesamiento de matrículas.
    Descarga video, extrae frames, detecta matrículas y obtiene info de Etecnic.
    """
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
            return {"status": "error", "error": "No se detectaron matrículas"}

        resultados_finales = []
        client = EtecnicClient()  # 👉 Instancia del cliente

        for r in resultados_raw:
            matricula = r.get("matricula")
            if not matricula:
                continue

            # Obtener datos del dueño y vehículo desde API externa
            dueno_json = await client.obtener_dueno(matricula)
            if not dueno_json:
                continue

            # Procesar la información (normalizar/enriquecer)
            info = procesar_info(dueno_json)
            if not info:
                continue

            resultados_finales.append(info)

        if not resultados_finales:
            return {
                "status": "error",
                "error": "No se pudo procesar información de las matrículas"
            }

        return {"status": "success", "data": resultados_finales}

    except Exception as e:
        print("❌ ERROR procesando matrículas:")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
