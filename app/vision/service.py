from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2

from .detector import VehicleDetector, Box
from .classifier import classifier
from .plate_lookup import PlateMatcher, PlateMatch


@dataclass
class Entry:
    ts: float
    source: str
    brand: Optional[str]
    model: Optional[str]
    category: str
    score: float
    plate: Optional[str] = None
    origin: str = "ai"


class Worker:
    def __init__(self, url: str, rois: Optional[List[Tuple[float,float,float,float]]] = None, plate_matcher: Optional[PlateMatcher] = None):
        self.url = url
        self.rois = rois or []  # normalized (x0,y0,x1,y1)
        self.det = VehicleDetector()
        self._stop = False
        self.entries: List[Entry] = []
        self._last_frame = None
        self._boxes: List[Box] = []
        self.plate_matcher = plate_matcher
        # one state per ROI
        self._states: List[Dict[str, float | bool]] = [
            {"counted": False, "last_free": time.time()} for _ in self.rois
        ]
        self._min_iou = 0.12  # exigir solape mínimo con la ROI
        self._detect_every = int(os.getenv("DETECT_EVERY", "1"))
        self._recent: List[Dict] = []  # para overlay: cajas de ingresos recientes

    @staticmethod
    def _iou(ax, ay, aw, ah, bx, by, bw, bh) -> float:
        ax2, ay2 = ax+aw, ay+ah
        bx2, by2 = bx+bw, by+bh
        ix1, iy1 = max(ax, bx), max(ay, by)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2-ix1), max(0, iy2-iy1)
        inter = iw*ih
        if inter <= 0:
            return 0.0
        area_a = aw*ah
        area_b = bw*bh
        return inter / max(1.0, (area_a + area_b - inter))

    def stop(self):
        self._stop = True

    def run(self):
        # RTSP options for stability
        if os.getenv("OPENCV_FFMPEG_CAPTURE_OPTIONS") is None:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|fflags;discardcorrupt|fflags;nobuffer|flags;low_delay|"
                "max_delay;500000|probesize;32000|analyzeduration;0|allowed_media_types;video"
            )
        cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        bad = 0
        frame_index = 0
        while not self._stop:
            ok, frame = cap.read()
            if not ok or frame is None:
                bad += 1
                if bad > 50:
                    cap.release(); cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    bad = 0
                time.sleep(0.1)
                continue
            bad = 0
            h, w = frame.shape[:2]
            # Ejecutar el detector cada N frames para ganar FPS
            if frame_index % max(1, self._detect_every) == 0:
                boxes = self.det.detect(frame)
                self._boxes = boxes
            else:
                boxes = self._boxes
            frame_index += 1
            now = time.time()
            # For each ROI, check occupancy independently
            if self.rois:
                for i, r in enumerate(self.rois):
                    x0 = int(r[0]*w); y0=int(r[1]*h); x1=int(r[2]*w); y1=int(r[3]*h)
                    rw, rh = max(1, x1-x0), max(1, y1-y0)
                    # best box by IoU with ROI (más robusto que solo el centro)
                    best = None
                    best_conf = -1.0
                    for b in boxes:
                        iou = self._iou(x0, y0, rw, rh, b.x, b.y, b.w, b.h)
                        # Aceptar también si el centro cae dentro de la ROI
                        cx, cy = b.x + b.w//2, b.y + b.h//2
                        center_in = (x0 < cx < x1 and y0 < cy < y1)
                        # Si la ROI ocupa casi toda la imagen, relajar IoU
                        roi_frac = (rw * rh) / float(max(1, w*h))
                        min_iou = 0.02 if roi_frac > 0.85 else self._min_iou
                        if (iou >= min_iou or center_in) and b.conf > best_conf:
                            best_conf = b.conf
                            best = b
                    state = self._states[i]
                    counted = bool(state.get("counted", False))
                    if best is not None and not counted:
                        entry = self._build_entry(frame, best, now)
                        if entry is not None:
                            self.entries.append(entry)
                            state["counted"] = True
                            # guardar para overlay solo cuando hubo ingreso
                            self._recent.append({
                                "x": best.x, "y": best.y, "w": best.w, "h": best.h,
                                "cat": entry.category, "ts": now
                            })
                    if best is None:
                        # reset after a while to allow a new entry later
                        if now - float(state.get("last_free", now)) > 5:
                            state["counted"] = False
                        state["last_free"] = now
            else:
                # No ROI ⇒ treat as a single zone
                best = max(boxes, key=lambda b: b.conf, default=None)
                if best is not None:
                    entry = self._build_entry(frame, best, now)
                    if entry is not None:
                        self.entries.append(entry)

            self._last_frame = frame
            # self._boxes ya se actualiza cuando corre el detector
        cap.release()

    def _build_entry(self, frame, box: Box, ts: float) -> Optional[Entry]:
        h, w = frame.shape[:2]
        margin_x = int(box.w * 0.1)
        margin_y = int(box.h * 0.1)
        x0 = max(0, box.x - margin_x)
        y0 = max(0, box.y - margin_y)
        x1 = min(w, box.x + box.w + margin_x)
        y1 = min(h, box.y + box.h + margin_y)
        if x1 <= x0 or y1 <= y0:
            crop = frame[max(0, y0-5):min(h, y1+5), max(0, x0-5):min(w, x1+5)]
        else:
            crop = frame[y0:y1, x0:x1]

        plate_match: Optional[PlateMatch] = None
        if self.plate_matcher is not None:
            try:
                plate_match = self.plate_matcher.lookup(crop)
            except Exception:
                plate_match = None

        if plate_match is None:
            return None

        plate = plate_match.plate
        if not plate:
            return None

        origin = "etecnic" if plate_match.found else "plate_ocr"
        brand = plate_match.brand
        model = plate_match.model
        category = plate_match.category
        score = float(plate_match.score or 0.0)

        cls = None
        used_ai = False

        def ensure_cls():
            nonlocal cls, used_ai
            if cls is None:
                cls = classifier.classify(crop)
                used_ai = True
            return cls

        # Fallbacks cuando Etecnic no trae toda la información
        if not plate_match.found:
            ensure_cls()
        elif not model or not brand or not category:
            ensure_cls()

        if cls is not None:
            if not brand:
                brand = cls.brand
            if not model:
                model = cls.model
            if not category:
                category = cls.category
            score = max(score, float(cls.score or 0.0))

        category = category or "indeterminado"
        if used_ai and origin == "etecnic":
            origin = "etecnic_ai"
        elif used_ai and origin == "plate_ocr":
            origin = "ai"

        score = round(float(score or 0.0), 4)

        return Entry(ts, self.url, brand, model, category, score, plate=plate, origin=origin)

    def debug_jpeg_iter(self, maxw=960, q=90):
        while not self._stop:
            frame = self._last_frame
            if frame is None:
                time.sleep(0.05); continue
            h, w = frame.shape[:2]
            draw = frame.copy()
            # Dibujar ROIs para validar zonas
            for r in self.rois:
                x0=int(r[0]*w); y0=int(r[1]*h); x1=int(r[2]*w); y1=int(r[3]*h)
                cv2.rectangle(draw, (x0,y0), (x1,y1), (0,165,255), 2)
            # Dibujar detecciones actuales finas que están dentro de alguna ROI
            for b in self._boxes:
                show = False
                for r in self.rois:
                    x0=int(r[0]*w); y0=int(r[1]*h); x1=int(r[2]*w); y1=int(r[3]*h)
                    rw, rh = max(1, x1-x0), max(1, y1-y0)
                    if self._iou(x0,y0,rw,rh,b.x,b.y,b.w,b.h) >= 0.02:
                        show = True; break
                if show:
                    cv2.rectangle(draw, (b.x,b.y), (b.x+b.w,b.y+b.h), (0,200,0), 1)
            # Dibujar solo cuadros de ingresos recientes
            now = time.time()
            # mantener visibles 10s
            self._recent = [it for it in self._recent if (now - it["ts"]) < 10]
            for it in self._recent:
                color = (60,255,120) if it["cat"] == "EV" else ((0,255,255) if it["cat"] == "PHEV" else (255,215,0))
                cv2.rectangle(draw, (int(it["x"]), int(it["y"])), (int(it["x"]+it["w"]), int(it["y"]+it["h"])), color, 3)
            if maxw and w>maxw:
                nh = int(h*(maxw/w)); draw = cv2.resize(draw, (maxw, nh))
            ok, jpg = cv2.imencode('.jpg', draw, [int(cv2.IMWRITE_JPEG_QUALITY), int(q)])
            if ok:
                b = jpg.tobytes()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+b+b"\r\n"
            time.sleep(0.06)


class VisionService:
    def __init__(self):
        self.workers: Dict[str, Worker] = {}
        self.plate_matcher = PlateMatcher()

    def start(self, url: str, rois: List[Tuple[float,float,float,float]] | None = None):
        if url in self.workers:
            return
        w = Worker(url, rois, self.plate_matcher)
        self.workers[url] = w
        import threading
        t = threading.Thread(target=w.run, daemon=True)
        t.start()

    def update_rois(self, url: str, rois: List[Tuple[float,float,float,float]]):
        w = self.workers.get(url)
        if not w:
            return False
        w.rois = rois
        w._states = [{"counted": False, "last_free": time.time()} for _ in rois]
        return True

    def stop(self, url: str):
        w = self.workers.pop(url, None)
        if w: w.stop()

    def entries(self, since: float) -> List[Entry]:
        out: List[Entry] = []
        for w in self.workers.values():
            out.extend([e for e in w.entries if e.ts>=since])
        return sorted(out, key=lambda e: e.ts, reverse=True)

    def summary(self, window: int = 600) -> dict:
        import time
        since = time.time()-window
        items = self.entries(since)
        total = len(items)
        ev = sum(1 for e in items if e.category=="EV")
        phev = sum(1 for e in items if e.category=="PHEV")
        return {"window_sec": window, "total": total, "ev": ev, "phev": phev, "indeterminado": total-ev-phev}


vision_service = VisionService()
