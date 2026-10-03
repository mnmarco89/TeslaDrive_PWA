from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_current_token
from ..models import UserToken
from ..services.tesla_service import get_vehicle_data, get_vehicles

router = APIRouter(prefix="/api")


@router.get("/vehicles")
def vehicles(token: UserToken = Depends(get_current_token)):
    response = get_vehicles(token.access_token)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@router.get("/dashboard/{vin}")
def dashboard(vin: str, token: UserToken = Depends(get_current_token)):
    response = get_vehicle_data(vin, token.access_token)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json().get("response", {})
    vehicle_state = data.get("vehicle_state", {})
    drive_state = data.get("drive_state", {})
    charge_state = data.get("charge_state", {})

    return {
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
        "shift_state": drive_state.get("shift_state", "P"),
        "navigation": drive_state.get("active_route_destination"),
        "updated_at": datetime.utcnow().isoformat(),
    }
