# models.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StationModel(BaseModel):
    id: str
    name: str
    location: Optional[str]
    capacity: Optional[float]
    status: Optional[str]

class ChargeModel(BaseModel):
    id: str
    station_id: str
    timestamp: datetime
    energy_kwh: float
    cost: float

