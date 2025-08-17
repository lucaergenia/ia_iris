import re
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_textline_orientation=True, lang="en")
REGEX_MATRICULA = r"^[A-Z]{3}-?\d{3}$"


def normalizar_matricula(text):
    return text.replace("-", "").replace(" ", "").upper()


async def detectar_matriculas_en_video(video_path, informes=None, buscar_dueno_por_patente=None):
    import cv2

    matriculas_detectadas = set()
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_interval = int(fps * 10)
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval != 0:
            frame_count += 1
            continue

        result = ocr.predict(frame)
        for item in result:
            rec_texts = item.get("rec_texts", [])
            rec_scores = item.get("rec_scores", [])

            for text, score in zip(rec_texts, rec_scores):
                mat_norm = normalizar_matricula(text)
                if (
                    score > 0.5
                    and len(mat_norm) in (6, 7)
                    and re.match(REGEX_MATRICULA, text.replace(" ", "").upper())
                ):
                    if mat_norm not in matriculas_detectadas:
                        print("🔍 Matrícula detectada:", mat_norm)
                        matriculas_detectadas.add(mat_norm)

        frame_count += 1

    cap.release()

    # Devolver siempre en formato lista de diccionarios
    return [{"matricula": m} for m in matriculas_detectadas]
