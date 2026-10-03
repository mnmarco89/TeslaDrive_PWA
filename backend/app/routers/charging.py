from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import MAX_CHARGING_AMPS, MIN_CHARGING_AMPS
from ..database import get_db
from ..dependencies import get_current_token
from ..models import UserToken
from ..services.tesla_service import get_vehicle_data, send_signed_tesla_command
from ..services.voltage_governor import check_and_protect_voltage

router = APIRouter(prefix="/api")


@router.get("/charging/{vin}")
def get_charging_status(
    vin: str,
    token: UserToken = Depends(get_current_token),
    db: Session = Depends(get_db),
):
    response = get_vehicle_data(vin, token.access_token)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    charge_state = response.json().get("response", {}).get("charge_state", {})

    try:
        check_and_protect_voltage(vin, token, charge_state, db)
    except Exception as exc:
        print("Errore governor voltaggio:", exc)

    return {
        "charging_state": charge_state.get("charging_state"),
        "charge_amps": charge_state.get("charge_amps"),
        "charge_current_request": charge_state.get("charge_current_request"),
        "charger_voltage": charge_state.get("charger_voltage"),
        "charger_actual_current": charge_state.get("charger_actual_current"),
        "charger_power": charge_state.get("charger_power"),
    }


@router.post("/vehicles/{vin}/set_amps")
async def set_charging_amps(
    vin: str,
    payload: dict,
    token: UserToken = Depends(get_current_token),
):
    amps = payload.get("amps")
    if amps is None:
        raise HTTPException(
            status_code=400,
            detail="Valore di amperaggio non specificato",
        )

    try:
        amps = int(amps)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Amperaggio non valido")

    if amps < MIN_CHARGING_AMPS or amps > MAX_CHARGING_AMPS:
        raise HTTPException(
            status_code=400,
            detail=(
                "L'amperaggio deve essere compreso tra "
                f"{MIN_CHARGING_AMPS} e {MAX_CHARGING_AMPS} A"
            ),
        )

    try:
        response = await send_signed_tesla_command(
            vin,
            token.access_token,
            "set_charging_amps",
            {"charging_amps": amps},
        )
        return {
            "status": "success",
            "charging_amps": amps,
            "tesla_response": response,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
