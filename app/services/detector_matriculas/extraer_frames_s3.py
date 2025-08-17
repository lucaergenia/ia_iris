import boto3
import os
from pathlib import Path
import imageio.v3 as iio

# Configuración S3
S3_BUCKET = "ergenia-camara-portobelo"  # Cambia por tu bucket
S3_KEY = "testing.mp4"     # Cambia por tu ruta en S3
TMP_VIDEO = "video_temp.mp4"
FRAMES_DIR = Path("frames_local")

# Descargar el video desde S3
def download_video():
    s3 = boto3.client("s3")
    s3.download_file(S3_BUCKET, S3_KEY, TMP_VIDEO)
    print(f"[INFO] Video descargado: {TMP_VIDEO}")

# Extraer frames usando imageio.v3
def extraer_frames():
    # Crear carpeta si no existe
    FRAMES_DIR.mkdir(exist_ok=True)

    # Obtener metadatos del video
    meta = iio.immeta(TMP_VIDEO)
    fps = meta.get("fps", 30)  # Por defecto 30 si no está
    size = meta.get("size", (0, 0))
    print(f"[INFO] FPS: {fps}, Resolución: {size}")

    # Guardar 1 frame cada segundo
    frame_interval = int(fps)

    for idx, frame in enumerate(iio.imiter(TMP_VIDEO)):
        if idx % frame_interval == 0:
            frame_path = FRAMES_DIR / f"frame_{idx:04d}.jpg"
            iio.imwrite(frame_path, frame)
            print(f"[DEBUG] Guardado frame: {frame_path}")

    print(f"[INFO] Frames extraídos en {FRAMES_DIR}")

if __name__ == "__main__":
    download_video()
    extraer_frames()
