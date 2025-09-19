import os
import cv2
import time
import logging
from typing import Generator, Optional

logger = logging.getLogger("streaming.rtsp")


def build_rtsp_url() -> str:
    user = os.getenv("CAMERA_USER")
    password = os.getenv("CAMERA_PASSWORD")
    host = os.getenv("CAMERA_HOST")
    port = os.getenv("CAMERA_PORT", "554")
    profile = os.getenv("CAMERA_PROFILE", "profile1")

    if not (user and password and host):
        raise RuntimeError("Config de cámara incompleta: define CAMERA_USER, CAMERA_PASSWORD, CAMERA_HOST en .env")

    url = f"rtsp://{user}:{password}@{host}:{port}/{profile}"
    logger.info(f"RTSP URL: rtsp://{user}:***@{host}:{port}/{profile}")
    return url


class RTSPCamera:
    def __init__(self, rtsp_url: str, reconnect_delay: float = 2.0):
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay
        self.cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> bool:
        if os.getenv("OPENCV_FFMPEG_CAPTURE_OPTIONS") is None:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|"
                "stimeout;5000000|"
                "reorder_queue_size;0|"
                "fflags;discardcorrupt|"
                "fflags;nobuffer|"
                "flags;low_delay|"
                "max_delay;500000|"
                "probesize;32000|"
                "analyzeduration;0|"
                "allowed_media_types;video"
            )
        logger.info("Abriendo RTSP con OpenCV+FFMPEG…")
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        ok = bool(self.cap and self.cap.isOpened())
        logger.info(f"VideoCapture abierto: {ok}")
        return ok

    def frames(self, max_width: int = 0, quality: int = 95) -> Generator[bytes, None, None]:
        while True:
            if self.cap is None or not self.cap.isOpened():
                if not self._open():
                    logger.warning("No se pudo abrir RTSP; reintento…")
                    time.sleep(self.reconnect_delay)
                    continue

            ok, frame = self.cap.read()
            if not ok or frame is None:
                logger.warning("Frame inválido; reconectar…")
                try:
                    self.cap.release()
                except Exception:
                    pass
                time.sleep(self.reconnect_delay)
                continue

            if max_width and frame.shape[1] > max_width:
                h, w = frame.shape[:2]
                new_w = max_width
                new_h = int(h * (new_w / w))
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # calidad JPEG alta para máxima definición
            q = max(60, min(100, int(quality or 95)))
            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), q])
            if not ok:
                continue
            b = jpg.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + b + b"\r\n"
            )
