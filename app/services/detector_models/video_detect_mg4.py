import os
import cv2
from ultralytics import YOLO

# Ruta absoluta del video
script_dir = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(script_dir, "video_prueba.mp4")
frame_path = os.path.join(script_dir, "frame_extraido.jpg")
resultado_path = os.path.join(script_dir, "resultado_mg4.jpg")

# Cargar video
cap = cv2.VideoCapture(video_path)
ret, frame = cap.read()
cap.release()

if not ret:
    print("❌ No se pudo leer el video.")
    exit()

cv2.imwrite(frame_path, frame)
print(f"🖼️ Frame guardado como: {frame_path}")

# Cargar modelo YOLO
model = YOLO("runs/detect/train/weights/best.pt")
results = model(frame_path)

# Detectar clase 0
detected = any(int(cls.item()) == 0 for cls in results[0].boxes.cls) if results[0].boxes else False

print("✅ MG4 DETECTADO" if detected else "❌ MG4 NO DETECTADO")
results[0].save(filename=resultado_path)
print(f"📸 Imagen anotada guardada como: {resultado_path}")
