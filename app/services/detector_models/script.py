from ultralytics import YOLO
from PIL import Image
from pathlib import Path

# === RUTAS PERSONALIZADAS ===
IMAGES_DIR = Path("C:/Users/Luca Coronel/OneDrive/Escritorio/erg_matriculas/app/data/imagenes_mg4")
OUTPUT_IMG_DIR = Path("C:/Users/Luca Coronel/OneDrive/Escritorio/erg_matriculas/app/data/mg4_dataset/images/train")
OUTPUT_LABEL_DIR = Path("C:/Users/Luca Coronel/OneDrive/Escritorio/erg_matriculas/app/data/mg4_dataset/labels/train")
CLASS_NAME = "MG 4 EV"

# === CREAR CARPETAS DE SALIDA ===
OUTPUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_LABEL_DIR.mkdir(parents=True, exist_ok=True)

# === CARGAR MODELO YOLOv8 PREENTRENADO ===
model = YOLO("yolov8n.pt")  # modelo liviano

# === CONFIG DE CLASES ===
CAR_CLASS_ID = 2         # 'car' en COCO
NEW_CLASS_ID = 0         # lo vamos a llamar "MG 4 EV"

# === EXTENSIONES ACEPTADAS ===
image_extensions = [".jpg", ".jpeg", ".png"]
image_files = [f for f in IMAGES_DIR.iterdir() if f.suffix.lower() in image_extensions]

print(f"🖼️ Detectando en {len(image_files)} imágenes desde: {IMAGES_DIR}")

# === DETECCIÓN AUTOMÁTICA ===
for img_path in image_files:
    print(f"📷 Procesando: {img_path.name}")
    results = model(img_path)

    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            print(f"⚠️  No se detectaron autos en {img_path.name}")
            continue

        # Guardar imagen en carpeta final
        output_img_path = OUTPUT_IMG_DIR / img_path.name
        Image.open(img_path).save(output_img_path)

        # Crear archivo de etiqueta
        label_path = OUTPUT_LABEL_DIR / (img_path.stem + ".txt")
        with open(label_path, "w") as f:
            for box in boxes:
                cls = int(box.cls.item())
                if cls == CAR_CLASS_ID:
                    x, y, w, h = box.xywhn[0].tolist()
                    f.write(f"{NEW_CLASS_ID} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")

        print(f"✅ Etiqueta creada: {label_path.name}")
