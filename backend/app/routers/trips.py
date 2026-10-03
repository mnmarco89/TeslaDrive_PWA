from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_token
from ..models import TrackingVehicle, Trip, TripPoint
from ..services.battery_service import battery_info, recover_missing_energy
from ..services.trip_service import capture_lock, expire_trip, finish, iso, serialize

router = APIRouter(prefix="/api/trips", dependencies=[Depends(get_current_token)])


def tracked(db, vin):
    vehicle = db.get(TrackingVehicle, vin)
    if not vehicle:
        raise HTTPException(404, "Veicolo non disponibile: aggiorna la lista veicoli")
    return vehicle


class TrackingSettings(BaseModel):
    enabled: bool
    capacity_kwh: float | None = Field(default=None, ge=1, le=200)


@router.get("/{vin}/settings")
def get_settings(vin: str, db: Session = Depends(get_db)):
    v = tracked(db, vin)
    return dict(enabled=v.enabled, **battery_info(db, vin), last_sample_at=iso(v.last_sample_at), status=v.last_status)


@router.put("/{vin}/settings")
def set_settings(vin: str, body: TrackingSettings, db: Session = Depends(get_db)):
    with capture_lock:
        v = tracked(db, vin)
        v.enabled, v.capacity_kwh = body.enabled, body.capacity_kwh
        if not v.enabled:
            trip = db.query(Trip).filter_by(vin=vin, status="active").first()
            if trip:
                finish(db, trip, "interrupted")
            v.last_status = "Registrazione disattivata"
        db.commit()
    return get_settings(vin, db)


def period_start(period):
    now = datetime.now(ZoneInfo("Europe/Rome"))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start -= timedelta(days=now.weekday())
    elif period == "month":
        start = start.replace(day=1)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/{vin}")
def list_trips(vin: str, period: str = Query("all", pattern="^(today|week|month|all)$"),
               offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    tracked(db, vin)
    with capture_lock:
        expire_trip(db, vin)
        recover_missing_energy(db, vin)
    query = db.query(Trip).filter_by(vin=vin)
    if period != "all":
        query = query.filter(Trip.started_at >= period_start(period))
    from sqlalchemy import func
    count, km, energy, known_energy = query.with_entities(
        func.count(Trip.id), func.sum(Trip.distance_km), func.sum(Trip.energy_kwh),
        func.count(Trip.energy_kwh)).one()
    paired_km, paired_energy = query.filter(Trip.energy_kwh.isnot(None), Trip.distance_km > 0).with_entities(
        func.sum(Trip.distance_km), func.sum(Trip.energy_kwh)).one()
    cost = query.with_entities(func.sum(Trip.energy_kwh * Trip.tariff)).scalar()
    items = query.order_by(Trip.started_at.desc(), Trip.id.desc()).offset(offset).limit(limit).all()
    return dict(items=[serialize(t) for t in items], total=count,
                summary=dict(trips=count, distance_km=km if count else 0, energy_kwh=energy,
                             energy_trips=known_energy, cost=cost,
                             consumption_kwh_100km=paired_energy/paired_km*100 if paired_km else None))


@router.get("/{vin}/{trip_id}")
def detail(vin: str, trip_id: int, db: Session = Depends(get_db)):
    tracked(db, vin)
    with capture_lock:
        recover_missing_energy(db, vin)
    trip = db.query(Trip).filter_by(vin=vin, id=trip_id).first()
    if not trip:
        raise HTTPException(404, "Viaggio non trovato")
    points = db.query(TripPoint).filter_by(trip_id=trip.id).order_by(TripPoint.recorded_at).all()
    return {**serialize(trip), "points": [dict(recorded_at=iso(pt.recorded_at), latitude=pt.latitude,
            longitude=pt.longitude, speed_kmh=pt.speed_kmh, battery=pt.battery, odometer_km=pt.odometer_km) for pt in points]}


@router.get("/{vin}/{trip_id}/context")
def trip_context(vin: str, trip_id: int, retry: bool = False, db: Session = Depends(get_db)):
    tracked(db, vin)
    trip = db.query(Trip).filter_by(vin=vin, id=trip_id).first()
    if not trip:
        raise HTTPException(404, "Viaggio non trovato")
    from ..services.trip_context_service import context
    return context(db, trip, retry=retry)
