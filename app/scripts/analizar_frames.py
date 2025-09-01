import os
import cv2
import numpy as np
from app.scripts.detector import detectar_matriculas_en_imagen
from app.scripts.data_loader import cargar_duenos
from app.scripts.enrichment import cargar_informes

FRAMES_DIR = "frames_local/"

duenos = cargar_duenos()
informes = cargar_informes()

frames = [os.path.join(FRAMES_DIR, f) for f in os.listdir(FRAMES_DIR) if f.endswith(".jpg")]

print(f"[INFO] Total de frames a analizar: {len(frames)}")
for frame_path in frames:
    frame = cv2.imread(frame_path)
    resultado = detectar_matriculas_en_imagen(frame, duenos, informes)
    print(f"[{frame_path}] - {resultado}")
