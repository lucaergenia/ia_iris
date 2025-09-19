from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from app.client.etecnic_client import EtecnicClient
from app.scripts.detector import REGEX_MATRICULA, normalizar_matricula, ocr


@dataclass
class PlateMatch:
    plate: str
    found: bool
    brand: Optional[str]
    model: Optional[str]
    category: Optional[str]
    source: str
    score: float


class PlateMatcher:
    """Gestiona la detección de matrículas y su consulta en Etecnic."""

    def __init__(self, client: Optional[EtecnicClient] = None, cache_ttl: int = 1800):
        self.client = client or EtecnicClient()
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[PlateMatch, float]] = {}
        self._lock = threading.Lock()
        self._ocr_lock = threading.Lock()
        self._regex = re.compile(REGEX_MATRICULA)

    def lookup(self, crop_bgr: np.ndarray) -> Optional[PlateMatch]:
        plate, score = self._detect_plate(crop_bgr)
        if not plate:
            return None

        cached = self._get_cached(plate)
        if cached is not None:
            return PlateMatch(cached.plate, cached.found, cached.brand, cached.model, cached.category, cached.source, score)

        payload = self.client.obtener_dueno_sync(plate)
        match = self._payload_to_match(plate, score, payload)
        self._set_cached(plate, match)
        return match

    def _detect_plate(self, crop_bgr: np.ndarray, min_score: float = 0.5) -> Tuple[Optional[str], float]:
        if crop_bgr is None or crop_bgr.size == 0:
            return None, 0.0

        # Upscale pequeños recortes para mejorar OCR
        h, w = crop_bgr.shape[:2]
        if min(h, w) < 120:
            scale = 120.0 / max(1, min(h, w))
            crop_bgr = cv2.resize(crop_bgr, (int(w * scale), int(h * scale)))

        with self._ocr_lock:
            result = ocr.predict(crop_bgr)
        best_plate: Optional[str] = None
        best_score = 0.0
        for item in result or []:
            rec_texts = item.get("rec_texts", [])
            rec_scores = item.get("rec_scores", [])
            for text, score in zip(rec_texts, rec_scores):
                norm = normalizar_matricula(text)
                cleaned = text.replace(" ", "").upper()
                if score < min_score:
                    continue
                if len(norm) not in (6, 7):
                    continue
                if not self._regex.match(cleaned):
                    continue
                if score > best_score:
                    best_plate, best_score = norm, float(score)

        if best_plate is None:
            return None, 0.0

        return best_plate, best_score

    def _payload_to_match(self, plate: str, score: float, payload: Optional[dict]) -> PlateMatch:
        info = self._extract_vehicle_info(payload)
        if not info:
            return PlateMatch(plate, False, None, None, None, "plate", score)
        category = self._normalize_category(info.get("category"))
        brand = self._sanitize(info.get("brand"))
        model = self._sanitize(info.get("model"))
        return PlateMatch(plate, True, brand, model, category, "etecnic", score)

    def _extract_vehicle_info(self, data: Any) -> Optional[Dict[str, Optional[str]]]:
        if not data:
            return None
        if isinstance(data, dict):
            if "vehicle_info" in data:
                return self._extract_vehicle_info(data.get("vehicle_info"))
            if "vehicle" in data:
                return self._extract_vehicle_info(data.get("vehicle"))
            if "info" in data and isinstance(data["info"], list):
                for item in data["info"]:
                    info = self._extract_vehicle_info(item)
                    if info:
                        return info
            brand = data.get("vehicle_brand") or data.get("vehicle_brand_name") or data.get("brand") or data.get("marca")
            model = data.get("vehicle_model") or data.get("vehicle_model_name") or data.get("model") or data.get("modelo")
            category = (
                data.get("vehicle_type")
                or data.get("vehicle_type_name")
                or data.get("type_vehicle")
                or data.get("type")
                or data.get("tipo_vehiculo")
                or data.get("tipo_tecnologia")
                or data.get("technology")
            )
            return {"brand": brand, "model": model, "category": category}
        if isinstance(data, list):
            for item in data:
                info = self._extract_vehicle_info(item)
                if info:
                    return info
        return None

    @staticmethod
    def _normalize_category(raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        value = str(raw).lower()
        if any(token in value for token in ("phev", "enchuf", "plug-in", "plug in")):
            return "PHEV"
        if any(token in value for token in ("bev", "eléctr", "electr", "ev")):
            return "EV"
        if "hybrid" in value or "híbrido" in value:
            return "PHEV"
        return None

    @staticmethod
    def _sanitize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _get_cached(self, plate: str) -> Optional[PlateMatch]:
        with self._lock:
            item = self._cache.get(plate)
            if not item:
                return None
            match, ts = item
            if time.time() - ts > self.cache_ttl:
                del self._cache[plate]
                return None
            return match

    def _set_cached(self, plate: str, match: PlateMatch) -> None:
        with self._lock:
            self._cache[plate] = (match, time.time())
