from fastapi import APIRouter

from app.services.sustainability import (
    get_energy_series,
    get_energy_summary,
)

router = APIRouter()


@router.get("/energy/series", tags=["energy"])  # /api/stats/energy/series
def energy_series(station: str = "all", filter: str = "total", period: str | None = None):
    """
    Serie temporal de energía consumida por periodo.
    - station: nombre de estación o 'all'
    - filter: total | mes | diario
    - period: mes | dia | hora (opcional; si no, se infiere del filtro)
    """
    return get_energy_series(station=station, filter=filter, period=period)


@router.get("/energy/summary", tags=["energy"])  # /api/stats/energy/summary
def energy_summary(station: str = "all", filter: str = "total"):
    """
    Resumen de energía y equivalentes de CO2 (red, ICE y evitado) para el rango.
    """
    return get_energy_summary(station=station, filter=filter)

