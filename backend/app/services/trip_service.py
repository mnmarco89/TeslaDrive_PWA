"""Persist samples, segment drives and explicitly mark missing coverage."""
import math
import threading
from datetime import datetime, timedelta, timezone
from ..models import Trip, TripPoint, TrackingVehicle, UserSettingsDB

capture_lock = threading.RLock()  # deployment uses one uvicorn process
MAX_GAP_SECONDS = 180


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def sample_from_data(data):
    drive = data.get("drive_state") or {}
    charge = data.get("charge_state") or {}
    state = data.get("vehicle_state") or {}
    stamp = number(drive.get("timestamp"))
    if stamp is None:
        return None  # don't turn stale cached data into fresh samples
    try:
        at = datetime.fromtimestamp(stamp / 1000, timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if at > now + timedelta(seconds=60) or now - at > timedelta(seconds=MAX_GAP_SECONDS):
        return None
    lat, lon = number(drive.get("latitude")), number(drive.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        lat = lon = None
    odo = number(state.get("odometer"))
    speed = number(drive.get("speed"))
    battery = number(charge.get("battery_level"))
    if battery is not None and not 0 <= battery <= 100:
        battery = None
    return dict(at=at, latitude=lat, longitude=lon,
                speed_kmh=speed * 1.609344 if speed is not None else None,
                odometer_km=odo * 1.609344 if odo is not None else None,
                battery=battery, shift=drive.get("shift_state"),
                destination=drive.get("active_route_destination"))


def haversine(a, b):
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2-lat1, math.radians(b.longitude-a.longitude)
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def calculate(db, trip):
    if trip.start_odometer_km is not None and trip.end_odometer_km is not None:
        delta = trip.end_odometer_km - trip.start_odometer_km
        if delta >= 0:
            trip.distance_km, trip.distance_source = delta, "odometer"
        else:
            trip.distance_km, trip.distance_source = None, None
            trip.partial = True
    else:
        points = db.query(TripPoint).filter_by(trip_id=trip.id).order_by(TripPoint.recorded_at).all()
        distance = 0
        segments = 0
        for a, b in zip(points, points[1:]):
            dt = (b.recorded_at-a.recorded_at).total_seconds()
            if a.latitude is None or b.latitude is None or not 0 < dt <= MAX_GAP_SECONDS:
                continue
            km = haversine(a, b)
            if km / dt * 3600 > 250:
                trip.partial = True
                continue
            distance += km
            segments += 1
        trip.distance_km = distance if segments else None
        trip.distance_source = "gps_estimate" if segments else None
    if trip.capacity_kwh and trip.start_battery is not None and trip.end_battery is not None:
        # Net battery delta includes auxiliaries and SOC rounding; regeneration can give a gain.
        trip.energy_kwh = (trip.start_battery-trip.end_battery) / 100 * trip.capacity_kwh
    else:
        trip.energy_kwh = None


def finish(db, trip, status, at=None):
    trip.status = status
    trip.ended_at = at or trip.last_sample_at
    trip.partial = trip.partial or status != "completed"
    calculate(db, trip)


def expire_trip(db, vin, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    trip = db.query(Trip).filter_by(vin=vin, status="active").first()
    if trip and (now-trip.last_sample_at).total_seconds() > MAX_GAP_SECONDS:
        finish(db, trip, "interrupted")
        db.commit()


def record_sample(db, vin, data):
    with capture_lock:
        db.expire_all()
        vehicle = db.get(TrackingVehicle, vin)
        if vehicle is None or not vehicle.enabled:
            return
        from .battery_service import record_charging_sample, battery_info
        record_charging_sample(db, vin, data)
        sample = sample_from_data(data)
        if not sample:
            vehicle.last_status = "Dati assenti o non recenti"
            db.commit()
            return
        at = sample["at"]
        previous_at = vehicle.last_sample_at
        if previous_at and at <= previous_at:
            return
        expire_trip(db, vin, at)
        trip = db.query(Trip).filter_by(vin=vin, status="active").first()
        moving = sample["shift"] in ("D", "R", "N") or (sample["speed_kmh"] or 0) > 0
        parked = sample["shift"] == "P" or (sample["shift"] is None and sample["speed_kmh"] == 0)
        if moving and trip is None:
            settings = db.query(UserSettingsDB).first()
            from .cost_service import current_settings, initial_rate, snapshot_trip_cost
            settings = current_settings(db)
            initial_rate(db)
            battery = battery_info(db, vin)
            trip = Trip(vin=vin, started_at=at, last_sample_at=at,
                        partial=previous_at is None or (at-previous_at).total_seconds() > MAX_GAP_SECONDS,
                        start_odometer_km=sample["odometer_km"], start_battery=sample["battery"],
                        capacity_kwh=battery["effective_capacity_kwh"], capacity_source=battery["capacity_source"],
                        tariff=number(settings.electricity) if settings else None,
                        destination=sample["destination"] if isinstance(sample["destination"], str) else None)
            db.add(trip)
            db.flush()
            snapshot_trip_cost(db, trip)
        if trip:
            # Unknown gear + zero speed requires a minute of confirmation; D at traffic lights stays active.
            if parked and trip.parked_since is None:
                trip.parked_since = at
            if moving:
                trip.parked_since = None
            db.add(TripPoint(trip_id=trip.id, recorded_at=at, **{
                k: sample[k] for k in ("latitude", "longitude", "speed_kmh", "battery", "odometer_km")}))
            trip.last_sample_at = at
            trip.end_odometer_km = sample["odometer_km"]
            trip.end_battery = sample["battery"]
            db.flush()
            calculate(db, trip)
            if parked and (sample["shift"] == "P" or (at-trip.parked_since).total_seconds() >= 60):
                finish(db, trip, "completed", trip.parked_since)
        vehicle.last_sample_at = at
        vehicle.last_status = "Registrazione in corso" if trip and trip.status == "active" else "Auto ferma"
        if data.get("_location_unavailable"):
            vehicle.last_status += " · GPS non autorizzato: ricollega Tesla"
        db.commit()


def iso(at):
    return at.isoformat()+"Z" if at else None


def serialize(trip):
    elapsed = ((trip.ended_at or trip.last_sample_at)-trip.started_at).total_seconds()
    return dict(id=trip.id, vin=trip.vin, started_at=iso(trip.started_at), ended_at=iso(trip.ended_at),
                last_sample_at=iso(trip.last_sample_at), status=trip.status, partial=trip.partial,
                duration_minutes=round(max(0, elapsed)/60, 1), distance_km=trip.distance_km,
                distance_source=trip.distance_source, start_battery=trip.start_battery,
                end_battery=trip.end_battery, energy_kwh=trip.energy_kwh,
                consumption_kwh_100km=trip.energy_kwh/trip.distance_km*100
                if trip.energy_kwh is not None and trip.distance_km and trip.distance_km > 0 else None,
                energy_cost=trip.energy_kwh*trip.tariff if trip.energy_kwh is not None and trip.tariff is not None else None,
                energy_missing_reason=("Capacità utile non ancora calibrata: serve una ricarica osservata di almeno 20 punti percentuali." if trip.capacity_kwh is None else "Percentuale batteria iniziale o finale non disponibile.") if trip.energy_kwh is None else None,
                capacity_kwh=trip.capacity_kwh, capacity_source=trip.capacity_source, destination=trip.destination)
