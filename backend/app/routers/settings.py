import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_token
from ..models import UserSettingsDB, UserToken
from ..services.tesla_service import get_vehicle_data, get_vehicles

router = APIRouter(prefix="/api")


@router.get("/settings")
def get_settings(
    token: UserToken = Depends(get_current_token),
    db: Session = Depends(get_db),
):
    settings = db.query(UserSettingsDB).first()
    if not settings:
        settings = UserSettingsDB()
        db.add(settings)
        db.commit()

    diesel_price = 2.19
    electricity_price = float(settings.electricity)

    try:
        vehicles_response = get_vehicles(token.access_token)
        if vehicles_response.status_code == 200:
            vehicles = vehicles_response.json().get("response", [])
            if vehicles:
                vin = vehicles[0].get("vin")
                data_response = get_vehicle_data(vin, token.access_token, timeout=5)
                if data_response.status_code == 200:
                    drive_state = (
                        data_response.json()
                        .get("response", {})
                        .get("drive_state", {})
                    )
                    lat = drive_state.get("latitude")
                    lon = drive_state.get("longitude")
                    if lat and lon:
                        fuel_response = requests.get(
                            "https://prezzi-carburante.onrender.com/api/distributori",
                            params={
                                "latitude": lat,
                                "longitude": lon,
                                "distance": 10,
                                "fuel": "gasolio",
                                "results": 1,
                            },
                            timeout=5,
                        )
                        if fuel_response.status_code == 200:
                            stations = fuel_response.json()
                            if isinstance(stations, list) and stations:
                                live_price = stations[0].get("prezzo")
                                if live_price:
                                    diesel_price = float(live_price)
    except Exception as exc:
        print("Errore aggiornamento GPS prezzi:", exc)

    return {
        "electricity": electricity_price,
        "diesel": round(diesel_price, 2),
        "diesel_km_l": float(settings.diesel_km_l),
        "voltage_protection": settings.voltage_protection,
    }


@router.post("/settings")
def save_settings(payload: dict, db: Session = Depends(get_db)):
    settings = db.query(UserSettingsDB).first()
    if not settings:
        settings = UserSettingsDB()
        db.add(settings)

    settings.electricity = str(payload.get("electricity", settings.electricity))
    settings.diesel = str(payload.get("diesel", settings.diesel))
    settings.diesel_km_l = str(payload.get("diesel_km_l", settings.diesel_km_l))
    settings.voltage_protection = int(
        payload.get("voltage_protection", settings.voltage_protection)
    )
    db.commit()
    return {"status": "saved"}


@router.get("/trips")
def get_trips():
    # Placeholder mantenuto per compatibilità. Lo storico reale verrà
    # implementato nel modulo telemetria/trips nel prossimo passaggio.
    return []
