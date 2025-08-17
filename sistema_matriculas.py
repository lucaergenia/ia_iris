import cv2
from paddleocr import PaddleOCR
import re
import numpy as np
import os
import json

# ----------- CONFIG ----------- #
VIDEOS_DIR = "videos"
ANDEMOS_DIR = "andemos"
PATRON_MATRICULA = r'^[A-Z]{3,4}\d{3}$'
# ----------- ----------- ----------- #

ocr = PaddleOCR(use_textline_orientation=True, lang='en')
matriculas_detectadas = set()

# Carga todos los informes JSON en memoria
def cargar_informes():
    informes = {}
    for archivo in os.listdir(ANDEMOS_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "").lower()
            with open(os.path.join(ANDEMOS_DIR, archivo), "r", encoding="utf-8") as f:
                informes[nombre] = json.load(f)
    return informes

informes = cargar_informes()

def buscar_info_marca(marca):
    # Busca info de la marca en los informes
    for info in informes.values():
        for fila in info:
            if 'MARCA' in fila and fila['MARCA'].lower() == marca.lower():
                return fila
    return None

def buscar_info_modelo(modelo):
    # Busca info del modelo en los informes
    for info in informes.values():
        for fila in info:
            if ('LINEA' in fila or 'MODELO' in fila) and (fila.get('LINEA','').lower() == modelo.lower() or fila.get('MODELO','').lower() == modelo.lower()):
                return fila
    return None

def buscar_info_tecnologia(tipo):
    # Busca info de tecnología (BEV/HEV/PHEV) en los informes
    for info in informes.values():
        for fila in info:
            if 'TIPO DE TECNOLOGIA' in fila and fila['TIPO DE TECNOLOGIA'].lower() == tipo.lower():
                return fila
    return None

def buscar_info_segmento(segmento):
    for info in informes.values():
        for fila in info:
            if 'SEGMENTO' in fila and fila['SEGMENTO'].lower() == segmento.lower():
                return fila
    return None

def enriquecer_datos(vehiculo):
    # Enriquecer con informes (puedes agregar más lógica)
    info = {}
    marca = vehiculo.get("marca", "")
    modelo = vehiculo.get("modelo", "")
    tipo_vehiculo = vehiculo.get("tipo_vehiculo", "")
    segmento = vehiculo.get("clase_vehiculo", "")
    info["marca_stats"] = buscar_info_marca(marca)
    info["modelo_stats"] = buscar_info_modelo(modelo)
    info["tecnologia_stats"] = buscar_info_tecnologia(tipo_vehiculo)
    if segmento:
        info["segmento_stats"] = buscar_info_segmento(segmento)
    return info

def procesar_video(video_path, duenos):
    cap = cv2.VideoCapture(video_path)
    print(f"\n=== Procesando: {os.path.basename(video_path)} ===")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        result = ocr.predict(frame)
        for item in result:
            rec_texts = item.get('rec_texts', [])
            rec_scores = item.get('rec_scores', [])
            rec_boxes = item.get('rec_boxes', [])
            for text, score, box in zip(rec_texts, rec_scores, rec_boxes):
                if score > 0.7 and re.match(PATRON_MATRICULA, text):
                    if text not in matriculas_detectadas:
                        matriculas_detectadas.add(text)
                        # Buscar dueño/vehículo por matrícula
                        usuario_encontrado = None
                        vehiculo_encontrado = None
                        for usuario in duenos:
                            for vehiculo in usuario.get("vehiculos", []):
                                if vehiculo.get("matricula") == text:
                                    usuario_encontrado = usuario
                                    vehiculo_encontrado = vehiculo
                                    break
                            if usuario_encontrado:
                                break
                        print(f"\nMATRÍCULA DETECTADA: {text} (confianza: {score:.2f})")
                        if usuario_encontrado and vehiculo_encontrado:
                            print(f"  Dueño:   {usuario_encontrado['nombre']}")
                            print(f"  Teléfono:{usuario_encontrado['telefono']}")
                            print(f"  Email:   {usuario_encontrado['email']}")
                            print(f"  Vehículo:{vehiculo_encontrado['marca']} {vehiculo_encontrado['modelo']} - {vehiculo_encontrado['tipo_vehiculo']}")
                            # Enriquecimiento con informes
                            info_extra = enriquecer_datos(vehiculo_encontrado)
                            if info_extra["marca_stats"]:
                                print("  --- Datos de la marca ---")
                                print("   ", info_extra["marca_stats"])
                            if info_extra["modelo_stats"]:
                                print("  --- Datos del modelo ---")
                                print("   ", info_extra["modelo_stats"])
                            if info_extra["tecnologia_stats"]:
                                print("  --- Datos de tecnología ---")
                                print("   ", info_extra["tecnologia_stats"])
                            if info_extra.get("segmento_stats"):
                                print("  --- Datos del segmento ---")
                                print("   ", info_extra["segmento_stats"])
                        else:
                            print("  Matrícula detectada pero no encontrada en base de dueños/vehículos.")
    cap.release()
    print(f"=== Fin de procesamiento de {os.path.basename(video_path)} ===")

if __name__ == "__main__":
    # Carga tu JSON principal de dueños/vehículos
    with open("duenos.json", "r", encoding="utf-8") as f:
        duenos = json.load(f)

    # Procesa todos los videos en la carpeta
    for fname in os.listdir(VIDEOS_DIR):
        if fname.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
            procesar_video(os.path.join(VIDEOS_DIR, fname), duenos)