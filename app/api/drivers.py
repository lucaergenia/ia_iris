from fastapi import APIRouter
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

from app.services.station_stats import STATION_COLLECTIONS

router = APIRouter()


def _collections_for(station: str):
    if station.lower() in ("all", "todas"):
        return [STATION_COLLECTIONS["Portobelo"], STATION_COLLECTIONS["Salvio"]]
    col = STATION_COLLECTIONS.get(station)
    return [col] if col is not None else []


def _range_for(filter: str):
    now = datetime.utcnow()
    if filter == "mes":
        start = datetime(now.year, now.month, 1)
        end = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1)
        return start, end
    if filter in ("dia", "diario"):
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
        return start, end
    return None, None


@router.get("/drivers/ranking", tags=["drivers"])  # /api/stats/drivers/ranking
def drivers_ranking(station: str = "all", filter: str = "total", limit: int = 10):
    cols = _collections_for(station)
    if not cols:
        return {"items": []}

    start, end = _range_for(filter)
    query: Dict[str, Any] = {}
    if start and end:
        query = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    agg = []
    for c in cols:
        agg.extend(list(c.aggregate([
            {"$match": query},
            {"$group": {
                "_id": "$user_code",
                "user_name": {"$first": "$user_name"},
                "total_cargas": {"$sum": 1},
                "total_energy_Wh": {"$sum": {"$toInt": "$energy_Wh"}},
                "total_ingresos": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}
            }}
        ])))

    merged: Dict[str, Dict[str, Any]] = {}
    for u in agg:
        key = u.get("_id")
        if not key:
            continue
        m = merged.setdefault(key, {
            "user_code": key,
            "user_name": u.get("user_name"),
            "total_cargas": 0,
            "total_energy_Wh": 0,
            "total_ingresos": 0.0,
        })
        m["total_cargas"] += u.get("total_cargas", 0)
        m["total_energy_Wh"] += u.get("total_energy_Wh", 0)
        m["total_ingresos"] += float(u.get("total_ingresos", 0.0))

    items = sorted(merged.values(), key=lambda x: x.get("total_cargas", 0), reverse=True)[:limit]
    return {"items": items}


@router.get("/drivers/habits", tags=["drivers"])  # legacy (no usado en UI)
def drivers_habits(station: str = "all", filter: str = "total", top: int = 5):
    cols = _collections_for(station)
    if not cols:
        return {"items": []}

    start, end = _range_for(filter)
    match: Dict[str, Any] = {}
    if start and end:
        match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    totals: Dict[str, Dict[str, Any]] = {}
    for c in cols:
        for u in c.aggregate([
            {"$match": match},
            {"$group": {"_id": "$user_code", "user_name": {"$first": "$user_name"}, "total": {"$sum": 1}}}
        ]):
            uid = u.get("_id");
            if not uid: continue
            m = totals.setdefault(uid, {"user_name": u.get("user_name"), "total": 0})
            m["total"] += u.get("total", 0)

    top_users = sorted(totals.items(), key=lambda kv: kv[1]["total"], reverse=True)[:top]
    top_set = {uid for uid, _ in top_users}

    hist_map: Dict[str, List[int]] = {uid: [0]*24 for uid in top_set}
    name_map: Dict[str, str] = {uid: meta["user_name"] for uid, meta in top_users}

    for c in cols:
        for s in c.find(match, {"user_code": 1, "user_name": 1, "session_start_at": 1}):
            uid = s.get("user_code")
            if uid not in top_set: continue
            try:
                dt = datetime.fromisoformat(s.get("session_start_at").replace("Z","+00:00"))
                hist_map[uid][dt.hour] += 1
                if not name_map.get(uid) and s.get("user_name"):
                    name_map[uid] = s.get("user_name")
            except Exception:
                continue

    items = [{"user_code": uid, "user_name": name_map.get(uid), "histogram": hist_map[uid]} for uid in top_set]
    items.sort(key=lambda it: totals[it["user_code"]]["total"], reverse=True)
    return {"items": items}


@router.get("/drivers/loyalty", tags=["drivers"])  # /api/stats/drivers/loyalty
def drivers_loyalty(station: str = "all", filter: str = "mes"):
    cols = _collections_for(station)
    if not cols:
        return {"nuevos": 0, "recurrentes": 0}

    start, end = _range_for(filter)
    if not start or not end:
        users = set()
        for c in cols:
            users.update({s.get("user_code") for s in c.find({}, {"user_code": 1}) if s.get("user_code")})
        return {"nuevos": len(users), "recurrentes": 0}

    first_seen: Dict[str, datetime] = {}
    for c in cols:
        for s in c.aggregate([
            {"$addFields": {"dt": {"$dateFromString": {"dateString": "$session_start_at"}}}},
            {"$group": {"_id": "$user_code", "first": {"$min": "$dt"}}}
        ]):
            uid = s.get("_id"); f = s.get("first")
            if uid and isinstance(f, datetime):
                if uid not in first_seen or f < first_seen[uid]:
                    first_seen[uid] = f

    match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
    active = set()
    for c in cols:
        active.update({s.get("user_code") for s in c.find(match, {"user_code": 1}) if s.get("user_code")})

    nuevos = sum(1 for uid in active if first_seen.get(uid) and first_seen[uid] >= start)
    recurrentes = max(0, len(active) - nuevos)
    return {"nuevos": nuevos, "recurrentes": recurrentes}


@router.get("/drivers/alerts", tags=["drivers"])  # legacy (no usado en UI)
def drivers_alerts(station: str = "all", filter: str = "mes", threshold: float = 2.5):
    cols = _collections_for(station)
    if not cols:
        return {"items": []}

    start, end = _range_for(filter)
    match: Dict[str, Any] = {}
    if start and end:
        match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    per_user: Dict[str, List[int]] = defaultdict(list)
    name_map: Dict[str, str] = {}
    for c in cols:
        for s in c.find(match, {"user_code":1, "user_name":1, "energy_Wh":1}):
            uid = s.get("user_code")
            if not uid: continue
            try:
                val = int(s.get("energy_Wh") or 0)
            except Exception:
                continue
            per_user[uid].append(val)
            if s.get("user_name"):
                name_map[uid] = s.get("user_name")

    def z_anomalies(vals: List[int]):
        if not vals: return 0
        n = len(vals); mean = sum(vals)/n
        var = sum((x-mean)**2 for x in vals)/n if n>0 else 0
        std = var ** 0.5
        if std == 0: return 0
        return sum(1 for x in vals if abs((x-mean)/std) > float(threshold))

    items = []
    for uid, vals in per_user.items():
        count = z_anomalies(vals)
        if count > 0:
            items.append({"user_code": uid, "user_name": name_map.get(uid), "anomaly_sessions": count})

    items.sort(key=lambda x: x["anomaly_sessions"], reverse=True)
    return {"items": items}


@router.get("/drivers/summary", tags=["drivers"])  # /api/stats/drivers/summary
def drivers_summary(station: str = "all", filter: str = "total"):
    cols = _collections_for(station)
    if not cols:
        return {"total_drivers": 0, "total_charges": 0, "avg_charges_per_driver": 0.0}

    start, end = _range_for(filter)
    match: Dict[str, Any] = {}
    if start and end:
        match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    merged: Dict[str, Dict[str, Any]] = {}
    total_charges = 0
    for c in cols:
        for u in c.aggregate([
            {"$match": match},
            {"$group": {
                "_id": "$user_code",
                "user_name": {"$first": "$user_name"},
                "total_cargas": {"$sum": 1},
                "total_energy_Wh": {"$sum": {"$toInt": "$energy_Wh"}}
            }}
        ]):
            uid = u.get("_id");
            if not uid: continue
            m = merged.setdefault(uid, {"user_name": u.get("user_name"), "total_cargas": 0})
            m["total_cargas"] += u.get("total_cargas", 0)
            total_charges += u.get("total_cargas", 0)

    total_drivers = len(merged)
    avg = (total_charges / total_drivers) if total_drivers else 0.0

    return {
        "total_drivers": total_drivers,
        "total_charges": total_charges,
        "avg_charges_per_driver": round(avg, 2),
    }


@router.get("/habits/general", tags=["drivers"])  # /api/stats/habits/general
def habits_general(station: str = "all", filter: str = "total"):
    cols = _collections_for(station)
    if not cols:
        return {"histogram": [0]*24}

    start, end = _range_for(filter)
    match: Dict[str, Any] = {}
    if start and end:
        match = {"session_start_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}

    hist = [0]*24
    for c in cols:
        for s in c.find(match, {"session_start_at": 1}):
            try:
                dt = datetime.fromisoformat(s.get("session_start_at").replace("Z","+00:00"))
                hist[dt.hour] += 1
            except Exception:
                continue
    return {"histogram": hist}

