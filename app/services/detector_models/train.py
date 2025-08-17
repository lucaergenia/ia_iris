from ultralytics import YOLO

# Cargar modelo base
model = YOLO("yolov8n.pt")

# Entrenar con tu dataset
model.train(
    data="C:/Users/Luca Coronel/OneDrive/Escritorio/erg_matriculas/app/data/mg4_dataset/data.yaml",
    epochs=50,
    imgsz=640
) 