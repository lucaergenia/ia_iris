from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, PlainTextResponse
import time

from .service import vision_service
import json


router = APIRouter(prefix="/api/vision", tags=["vision"])


@router.post("/sources")
def start_source(url: str, rois: str | None = None, x0: float = 0.1, y0: float = 0.3, x1: float = 0.9, y1: float = 0.8):
    # rois: JSON string [[x0,y0,x1,y1], ...]
    if rois:
        try:
            arr = json.loads(rois)
            rois_list = [(
                max(0.0, float(r[0])), max(0.0, float(r[1])), min(1.0, float(r[2])), min(1.0, float(r[3]))
            ) for r in arr]
        except Exception:
            rois_list = []
    else:
        rois_list = [(max(0.0,x0), max(0.0,y0), min(1.0,x1), min(1.0,y1))]
    vision_service.start(url, rois_list)
    return {"status": "started", "url": url, "rois": rois_list}


@router.delete("/sources")
def stop_source(url: str):
    vision_service.stop(url)
    return {"status": "stopped", "url": url}


@router.get("/summary")
def get_summary(window_sec: int = 600):
    return vision_service.summary(window_sec)


@router.get("/entries")
def get_entries(since_sec: int = 600, limit: int = 50):
    since = time.time() - max(1, since_sec)
    items = vision_service.entries(since)[:max(1, min(500, limit))]
    return {"items": [e.__dict__ for e in items]}


@router.put("/sources/rois")
def update_rois(url: str, rois: str):
    try:
        arr = json.loads(rois)
        rois_list = [(
            max(0.0, float(r[0])), max(0.0, float(r[1])), min(1.0, float(r[2])), min(1.0, float(r[3]))
        ) for r in arr]
    except Exception:
        return PlainTextResponse("invalid rois", status_code=400)
    ok = vision_service.update_rois(url, rois_list)
    if not ok:
        return PlainTextResponse("source not started", status_code=404)
    return {"status": "updated", "url": url, "rois": rois_list}


@router.get("/debug")
def debug_stream(url: str, w: int = 960, q: int = 90):
    wkr = vision_service.workers.get(url)
    if not wkr:
        return PlainTextResponse("source not started", status_code=404)
    return StreamingResponse(wkr.debug_jpeg_iter(maxw=w, q=q), media_type="multipart/x-mixed-replace; boundary=frame")
