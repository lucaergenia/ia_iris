from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int
    conf: float
    cls: int


class VehicleDetector:
    """YOLOv8 detector wrapper with safe fallbacks.

    - If Ultralytics is available, use yolov8n.pt (local path from env YOLO_WEIGHTS or auto-download).
    - Else, fallback to background subtraction to at least return motion boxes.
    """

    def __init__(self):
        self._yolo = None
        self._use_yolo = False
        self._load_yolo()
        self._bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=True)
        try:
            self._imgsz = int(os.getenv("YOLO_IMGSZ", "512"))
        except Exception:
            self._imgsz = 512

    def _load_yolo(self):
        try:
            from ultralytics import YOLO
            weights = os.getenv("YOLO_WEIGHTS", "yolov8n.pt")
            self._yolo = YOLO(weights)
            self._use_yolo = True
        except Exception:
            self._yolo = None
            self._use_yolo = False

    def detect(self, frame) -> List[Box]:
        h, w = frame.shape[:2]
        if self._use_yolo:
            try:
                res = self._yolo.predict(frame, imgsz=self._imgsz, conf=0.25, verbose=False)[0]
                boxes: List[Box] = []
                for b in res.boxes:
                    cls = int(b.cls.item()) if hasattr(b.cls, "item") else int(b.cls)
                    # COCO: 2 car, 5 bus, 7 truck
                    if cls not in (2, 5, 7):
                        continue
                    xyxy = b.xyxy.cpu().numpy().astype(int)[0]
                    x0, y0, x1, y1 = xyxy
                    boxes.append(Box(x0, y0, max(1, x1-x0), max(1, y1-y0), float(b.conf.item()), cls))
                return boxes
            except Exception:
                # Silent fallback to bg-subtraction
                pass

        # Fallback: MOG2 motion boxes
        mask = self._bg.apply(frame)
        mask = cv2.medianBlur(mask, 5)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out: List[Box] = []
        area_min = max(4000, int(0.0015 * w * h))
        for c in contours:
            x, y, ww, hh = cv2.boundingRect(c)
            if ww*hh < area_min:
                continue
            out.append(Box(x, y, ww, hh, 0.4, 2))
        return out
