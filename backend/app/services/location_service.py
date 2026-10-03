from datetime import datetime, timezone
from ..models import VehicleLocation
from .trip_service import number, iso
from .charging_history_service import sample_time


def record_location(db, vin, data):
    if data.get('_location_unavailable'):
        return
    drive = data.get('drive_state') or {}
    lat, lon = number(drive.get('latitude')), number(drive.get('longitude'))
    at = sample_time(drive.get('gps_as_of'), 1) if drive.get('gps_as_of') is not None else sample_time(drive.get('timestamp'))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or at is None:
        return
    if at > datetime.now(timezone.utc).replace(tzinfo=None):
        return
    saved = db.get(VehicleLocation, vin)
    if saved and at <= saved.recorded_at:
        return
    if not saved:
        saved = VehicleLocation(vin=vin)
        db.add(saved)
    saved.latitude, saved.longitude, saved.recorded_at = lat, lon, at
    db.flush()


def location(db, vin):
    saved = db.get(VehicleLocation, vin)
    if not saved:
        return {'available':False}
    age = (datetime.now(timezone.utc).replace(tzinfo=None)-saved.recorded_at).total_seconds()
    return dict(available=True, latitude=saved.latitude, longitude=saved.longitude,
        recorded_at=iso(saved.recorded_at), stale=age>180)
