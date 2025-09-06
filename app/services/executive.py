from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

from pymongo.collection import Collection

from app.database.database import db, sessions_Portobelo, sessions_Salvio

Scope = Literal["global", "station"]


def _to_iso(dt: datetime) -> str:
    # Mantener coherencia con el resto del proyecto (guardan ISO sin tz)
    return dt.replace(tzinfo=None).isoformat()


def _month_bounds(ref: Optional[str] = None) -> tuple[datetime, datetime]:
    """
    Devuelve (inicio_mes, ahora) para el mes indicado en 'YYYY-MM'.
    Si ref es None, usa el mes en curso hasta ahora.
    """
    now = datetime.utcnow()
    if ref:
        year, month = [int(x) for x in ref.split("-")]
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        # si es el mes actual, recortamos a 'now'
        if start.year == now.year and start.month == now.month:
            end = now
    else:
        start = datetime(now.year, now.month, 1)
        end = now
    return start, end


def _prev_month_bounds(ref: Optional[str] = None) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    if ref:
        year, month = [int(x) for x in ref.split("-")]
        base = datetime(year, month, 1)
    else:
        base = datetime(now.year, now.month, 1)
    # ir al primer día del mes anterior
    if base.month == 1:
        start = datetime(base.year - 1, 12, 1)
    else:
        start = datetime(base.year, base.month - 1, 1)
    end = datetime(base.year, base.month, 1)
    return start, end


def _collections_for_scope(station: Optional[str]) -> list[Collection]:
    if station and station.lower() not in ("all", "todas"):
        if station == "Portobelo":
            return [sessions_Portobelo]
        if station == "Salvio":
            return [sessions_Salvio]
        return []
    return [sessions_Portobelo, sessions_Salvio]


def _count_distinct_users(collections: list[Collection], start: datetime, end: datetime) -> int:
    users = set()
    q = {"session_start_at": {"$gte": _to_iso(start), "$lt": _to_iso(end)}}
    for c in collections:
        for doc in c.find(q, {"user_code": 1}):
            code = doc.get("user_code")
            if code:
                users.add(code)
    return len(users)


def _count_sessions(collections: list[Collection], start: datetime, end: datetime) -> int:
    q = {"session_start_at": {"$gte": _to_iso(start), "$lt": _to_iso(end)}}
    total = 0
    for c in collections:
        total += c.count_documents(q)
    return total


def _sum_energy_wh(collections: list[Collection], start: datetime, end: datetime) -> int:
    q = {"session_start_at": {"$gte": _to_iso(start), "$lt": _to_iso(end)}}
    total = 0
    for c in collections:
        cursor = c.find(q, {"energy_Wh": 1})
        for doc in cursor:
            try:
                total += int(doc.get("energy_Wh", 0))
            except Exception:
                pass
    return total


def _sum_amount(collections: list[Collection], start: datetime | None, end: datetime | None) -> float:
    if start is not None and end is not None:
        q = {"session_start_at": {"$gte": _to_iso(start), "$lt": _to_iso(end)}}
    else:
        q = {}
    total = 0.0
    for c in collections:
        cursor = c.find(q, {"amount": 1})
        for doc in cursor:
            try:
                total += float(doc.get("amount", 0) or 0)
            except Exception:
                pass
    return total


def _estimate_occupied_minutes(collections: list[Collection], start: datetime, end: datetime) -> int:
    """
    Estimación simple si no tenemos duración: usa duración media configurable.
    Variables de entorno:
    - SESSION_AVG_MINUTES (default 45)
    """
    avg_minutes = int(os.getenv("SESSION_AVG_MINUTES", "45"))
    sessions = _count_sessions(collections, start, end)
    return sessions * avg_minutes


def _available_minutes(station: Optional[str], start: datetime, end: datetime) -> int:
    minutes = int((end - start).total_seconds() // 60)
    if station and station.lower() not in ("all", "todas"):
        conns = int(os.getenv(f"CONNECTORS_{station.upper()}", "0"))
    else:
        conns = int(os.getenv("CONNECTORS_PORTOBELO", "0")) + int(os.getenv("CONNECTORS_SALVIO", "0"))
    return minutes * max(1, conns)


def compute_executive_summary(
    station: Optional[str] = None,
    window_days: int = 30,
    month: Optional[str] = None,
) -> dict:
    """
    Calcula KPIs ejecutivos.
    - station: None/"all" para global o nombre de estación
    - window_days: ventana para clientes activos
    - month: YYYY-MM para el mes de referencia
    """
    colls = _collections_for_scope(station)
    now = datetime.utcnow()
    # Clientes activos
    win_start = now - timedelta(days=window_days)
    active_customers = _count_distinct_users(colls, win_start, now)

    # Cargas mes actual vs mes anterior
    cur_start, cur_end = _month_bounds(month)
    prev_start, prev_end = _prev_month_bounds(month)
    charges_cur = _count_sessions(colls, cur_start, cur_end)
    charges_prev = _count_sessions(colls, prev_start, prev_end)
    growth_pct = ((charges_cur - charges_prev) / charges_prev * 100.0) if charges_prev > 0 else (100.0 if charges_cur > 0 else 0.0)

    # Ingresos por mes, YTD (hasta fin del mes seleccionado) y totales
    year_start = datetime(now.year, 1, 1)
    revenue_month = _sum_amount(colls, cur_start, cur_end)
    revenue_ytd = _sum_amount(colls, year_start, cur_end)
    revenue_total = _sum_amount(colls, None, None)

    # Meta YTD (meta anual por defecto 1,996,677,530 COP ≈ 500k USD)
    rate_cop_usd = float(os.getenv("EXCHANGE_RATE_COP_USD", "3993.35506"))  # COP por 1 USD
    target_annual_cop = float(
        os.getenv("REVENUE_TARGET_ANNUAL_COP")
        or os.getenv("REVENUE_TARGET_ANNUAL")
        or 1996677530.00
    )
    target_annual_usd = float(os.getenv("REVENUE_TARGET_ANNUAL_USD") or (target_annual_cop / rate_cop_usd))

    if target_annual_cop > 0:
        # proporcional al día del año hasta fin del mes seleccionado
        end_ref = cur_end
        day_of_year = (end_ref - datetime(end_ref.year, 1, 1)).days + 1
        days_in_year = 366 if (end_ref.year % 4 == 0 and (end_ref.year % 100 != 0 or end_ref.year % 400 == 0)) else 365
        revenue_target_ytd = target_annual_cop * (day_of_year / days_in_year)
    else:
        revenue_target_ytd = 0.0
    revenue_achv_pct = (revenue_ytd / revenue_target_ytd * 100.0) if revenue_target_ytd > 0 else 0.0

    # Utilización promedio de red
    occupied_min = _estimate_occupied_minutes(colls, cur_start, cur_end)
    available_min = _available_minutes(station, cur_start, cur_end)
    utilization_pct = (occupied_min / available_min * 100.0) if available_min > 0 else 0.0

    return {
        "scope": "station" if station and station.lower() not in ("all", "todas") else "global",
        "station": None if not station or station.lower() in ("all", "todas") else station,
        "window_days": window_days,
        "month": month,
        "active_customers": active_customers,
        "charges_month": charges_cur,
        "charges_prev_month": charges_prev,
        "growth_pct": growth_pct,
        "revenue_month": round(revenue_month, 2),
        "revenue_ytd": round(revenue_ytd, 2),
        "revenue_total": round(revenue_total, 2),
        "revenue_target_ytd": round(revenue_target_ytd, 2),
        "revenue_achv_pct": round(revenue_achv_pct, 2),
        "utilization_pct": round(utilization_pct, 2),
        # Conversión a USD
        "exchange_rate_cop_usd": rate_cop_usd,
        "revenue_month_usd": round(revenue_month / rate_cop_usd, 2),
        "revenue_ytd_usd": round(revenue_ytd / rate_cop_usd, 2),
        "revenue_total_usd": round(revenue_total / rate_cop_usd, 2),
        "revenue_target_ytd_usd": round(revenue_target_ytd / rate_cop_usd, 2),
        "revenue_target_annual_cop": round(target_annual_cop, 2),
        "revenue_target_annual_usd": round(target_annual_usd, 2),
        "cached": False,
    }


# =============================
# Cache en memoria (TTL corto)
# =============================
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = int(os.getenv("EXEC_SUMMARY_CACHE_TTL", "60"))


def _cache_key(station: Optional[str], window_days: int, month: Optional[str]) -> str:
    return f"{station or 'all'}|{window_days}|{month or ''}"


def get_executive_summary_cached(
    station: Optional[str] = None,
    window_days: int = 30,
    month: Optional[str] = None,
) -> dict:
    import time

    key = _cache_key(station, window_days, month)
    now = time.time()
    if key in _CACHE:
        ts, data = _CACHE[key]
        if now - ts < _CACHE_TTL_SECONDS:
            return {**data, "cached": True}
    data = compute_executive_summary(station, window_days, month)
    _CACHE[key] = (now, data)
    return data


def materialize_all_scopes():
    """Calcula y guarda KPIs materializados para global y cada estación."""
    for st in (None, "Portobelo", "Salvio"):
        doc = compute_executive_summary(st)
        store_executive_summary(doc)


def store_executive_summary(doc: dict) -> dict:
    doc = {**doc, "timestamp": datetime.utcnow()}
    res = db.executive_kpis.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


def latest_executive_summary(station: Optional[str] = None) -> Optional[dict]:
    scope = "station" if station and station.lower() not in ("all", "todas") else "global"
    query = {"scope": scope}
    if scope == "station":
        query["station"] = station
    return db.executive_kpis.find_one(query, sort=[("timestamp", -1)])
