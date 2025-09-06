from fastapi import APIRouter
from app.stats_flow.classifier import classify_single_vehicle
from app.database.database import get_last_station_stats

router = APIRouter()


@router.get("/unclassified-models", tags=["stats"])  # /api/stats/unclassified-models
def unclassified_models(station: str = "all", filter: str = "total"):
    """Lista de (brand, model) sin clasificar como EV/PHEV en el período seleccionado."""

    def _details_for(st: str):
        doc = get_last_station_stats(st, filter) or get_last_station_stats(st)
        return (doc or {}).get("details", [])

    if station and station.lower() not in ("all", "todas"):
        details = _details_for(station)
    else:
        details = _details_for("Portobelo") + _details_for("Salvio")

    counter: dict[tuple[str, str], int] = {}
    for d in details:
        brand = d.get("brand") or ""
        model = d.get("model") or ""
        cat = classify_single_vehicle(brand, model)
        if cat != "unclassified":
            continue
        key = (brand.strip(), model.strip())
        counter[key] = counter.get(key, 0) + 1

    items = [
        {"brand": b, "model": m, "count": c}
        for (b, m), c in counter.items()
    ]
    items.sort(key=lambda x: (-x["count"], x["brand"], x["model"]))
    return {"items": items}

