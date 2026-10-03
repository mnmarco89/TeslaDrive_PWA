from bisect import bisect_right
from datetime import datetime, timezone
from ..models import CostRate, TripCostSnapshot, UserSettingsDB
from sqlalchemy import or_
from .trip_service import number, iso


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def current_settings(db):
    settings = db.query(UserSettingsDB).first()
    if not settings:
        settings = UserSettingsDB()
        db.add(settings)
        db.flush()
    return settings


def initial_rate(db, at=None):
    if db.query(CostRate).first():
        return
    settings = current_settings(db)
    values = [number(settings.electricity), number(settings.diesel), number(settings.diesel_km_l)]
    if values[0] is None or values[0] < 0 or values[1] is None or values[1] <= 0 or values[2] is None or values[2] <= 0:
        return
    at = at or now_utc()
    db.add(CostRate(effective_from=at, recorded_at=at, electricity=values[0], diesel=None, diesel_km_l=values[2], source="initial"))
    db.flush()


def serialize_rate(rate):
    return dict(id=rate.id, vin=rate.vin, effective_from=iso(rate.effective_from), recorded_at=iso(rate.recorded_at),
                electricity=rate.electricity, diesel=rate.diesel, diesel_km_l=rate.diesel_km_l, source=rate.source, station=rate.station, dataset_date=rate.dataset_date)


def add_rate(db, electricity, diesel, diesel_km_l, at=None, source="settings", vin=None):
    now = now_utc()
    at = at or now
    rate = CostRate(effective_from=at, recorded_at=now, electricity=electricity, diesel=diesel, diesel_km_l=diesel_km_l, source=source, vin=vin)
    db.add(rate)
    db.flush()
    return rate


def snapshot_trip_cost(db, trip):
    rate = db.query(CostRate).filter(CostRate.effective_from <= trip.started_at, CostRate.diesel.isnot(None),
            or_(CostRate.vin == trip.vin, CostRate.vin.is_(None))).order_by(CostRate.effective_from.desc(), CostRate.id.desc()).first()
    settings = current_settings(db)
    db.add(TripCostSnapshot(trip_id=trip.id, rate_id=rate.id if rate else None,
        diesel=rate.diesel if rate else None, diesel_km_l=float(settings.diesel_km_l)))


def summarize(db, trips):
    rates = db.query(CostRate).order_by(CostRate.effective_from, CostRate.id).all()
    rates = [r for r in rates if not trips or r.vin in (None, trips[0].vin)]
    dates = [r.effective_from for r in rates]
    fuel_rates = [r for r in rates if r.diesel is not None]
    fuel_dates = [r.effective_from for r in fuel_rates]
    snapshots = {s.trip_id: s for s in db.query(TripCostSnapshot).all()}
    result = dict(trips=len(trips), partial_trips=sum(bool(t.partial) for t in trips),
                  distance_km=0.0, electricity_cost=None, diesel_cost=None, electricity_distance_km=0.0,
                  diesel_distance_km=0.0, comparable_distance_km=0.0, comparable_trips=0,
                  comparable_electricity_cost=None, comparable_diesel_cost=None, saving=None,
                  energy_kwh=None, electricity_trips=0, diesel_trips=0, missing_distance_trips=0)
    by_month = {}
    from zoneinfo import ZoneInfo
    for t in trips:
        km = number(t.distance_km)
        if km is None or km < 0:
            result["missing_distance_trips"] += 1
            continue
        result["distance_km"] += km
        month = t.started_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m")
        row = by_month.setdefault(month, dict(month=month, trips=0, distance_km=0.0, electricity_cost=None,
              diesel_cost=None, electricity_distance_km=0.0, diesel_distance_km=0.0, saving=None, comparable_distance_km=0.0))
        row["trips"] += 1
        row["distance_km"] += km
        idx = bisect_right(dates, t.started_at)-1
        rate = rates[idx] if idx >= 0 else None
        fuel_idx = bisect_right(fuel_dates, t.started_at)-1
        fuel_rate = fuel_rates[fuel_idx] if fuel_idx >= 0 else None
        snap = snapshots.get(t.id)
        diesel = snap.diesel if snap and snap.diesel is not None else fuel_rate.diesel if fuel_rate else None
        efficiency = snap.diesel_km_l if snap else fuel_rate.diesel_km_l if fuel_rate else None
        tariff = number(t.tariff)  # original electricity tariff is authoritative
        if tariff is None and rate:
            tariff = rate.electricity
        energy = number(t.energy_kwh)
        ecost = energy*tariff if energy is not None and tariff is not None and tariff >= 0 else None
        dcost = km/efficiency*diesel if diesel is not None and efficiency is not None and efficiency > 0 else None
        for key, value, coverage in (("electricity_cost", ecost, "electricity_distance_km"), ("diesel_cost", dcost, "diesel_distance_km")):
            if value is not None:
                result[key] = (result[key] or 0) + value
                row[key] = (row[key] or 0) + value
                result[coverage] += km
                row[coverage] += km
        if ecost is not None:
            result["electricity_trips"] += 1
            result["energy_kwh"] = (result["energy_kwh"] or 0) + energy
        if dcost is not None:
            result["diesel_trips"] += 1
        if ecost is not None and dcost is not None and km > 0:
            result["comparable_trips"] += 1
            result["comparable_distance_km"] += km
            result["comparable_electricity_cost"] = (result["comparable_electricity_cost"] or 0) + ecost
            result["comparable_diesel_cost"] = (result["comparable_diesel_cost"] or 0) + dcost
            row["comparable_distance_km"] += km
            row["saving"] = (row["saving"] or 0) + dcost-ecost
    if result["comparable_trips"]:
        result["saving"] = result["comparable_diesel_cost"]-result["comparable_electricity_cost"]
    result["months"] = sorted(by_month.values(), key=lambda r: r["month"], reverse=True)
    return result
