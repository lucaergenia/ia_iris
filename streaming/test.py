import cv2

usuario = "admin"
password = "Assis*12345"
ip_publica = "190.159.37.81"
puerto = 554
perfil = "profile2"  # confirmado por tu proveedor

rtsp_url = f"rtsp://{usuario}:{password}@{ip_publica}:{puerto}/{perfil}"
print(f"Conectando a: {rtsp_url}")

cap = cv2.VideoCapture(rtsp_url)

if not cap.isOpened():
    print("❌ No se pudo abrir el stream RTSP")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️ Error al recibir frame, reconectando...")
        cap.release()
        cap = cv2.VideoCapture(rtsp_url)
        continue

    cv2.imshow("Streaming RTSP - Provision ISR", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
