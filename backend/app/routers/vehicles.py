from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.trip_collector import register_vehicles, fetch_sample

from ..dependencies import get_current_token
from ..models import UserToken
from ..services.tesla_service import get_vehicle_data, get_vehicles

router = APIRouter(prefix="/api")


@router.get("/vehicles")
def vehicles(token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    response = get_vehicles(token.access_token)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    payload = response.json()
    register_vehicles(db, payload.get("response") or [])
    return payload


@router.get("/dashboard/{vin}")
def dashboard(vin: str, token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    try:
        data = fetch_sample(db, vin)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    vehicle_state = data.get("vehicle_state", {})
    drive_state = data.get("drive_state", {})
    charge_state = data.get("charge_state", {})
    climate_state = data.get("climate_state", {})

    from ..services.location_service import location
    return {
        "location": location(db, vin),
        "car_type": (data.get("vehicle_config") or {}).get("car_type"),
        "battery": charge_state.get("battery_level"),
        "range_km": (
            charge_state.get("battery_range", 0) * 1.60934
            if charge_state.get("battery_range")
            else None
        ),
        "odometer_km": (
            vehicle_state.get("odometer", 0) * 1.60934
            if vehicle_state.get("odometer")
            else None
        ),
        "speed_kmh": (
            drive_state.get("speed", 0) * 1.60934
            if drive_state.get("speed")
            else 0
        ),
        "shift_state": drive_state.get("shift_state"),
        "navigation": drive_state.get("active_route_destination"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "vehicle_timestamp": vehicle_state.get("timestamp"),
        "locked": vehicle_state.get("locked"),
        "doors": {key: vehicle_state.get(key) for key in ("df", "pf", "dr", "pr", "ft", "rt")},
        "sentry_mode": vehicle_state.get("sentry_mode"),
        "software_version": vehicle_state.get("car_version"),
        "tpms": {key: vehicle_state.get(f"tpms_pressure_{key}") for key in ("fl", "fr", "rl", "rr")},
        "inside_temp": climate_state.get("inside_temp"),
        "outside_temp": climate_state.get("outside_temp"),
        "is_climate_on": climate_state.get("is_climate_on"),
        "charge_limit_soc": charge_state.get("charge_limit_soc"),
        "charge_port_door_open": charge_state.get("charge_port_door_open"),
    }


@router.get('/vehicles/{vin}/location')
def vehicle_location(vin: str, token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    from ..services.location_service import location
    return location(db, vin)
