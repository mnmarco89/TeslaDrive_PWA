import asyncio

from sqlalchemy.orm import Session

from ..config import MAX_CHARGING_AMPS, MIN_CHARGING_AMPS
from ..models import UserSettingsDB, UserToken
from .tesla_service import send_signed_tesla_command


def check_and_protect_voltage(
    vin: str,
    token: UserToken,
    charge_state: dict,
    db: Session,
):
    settings = db.query(UserSettingsDB).first()
    if not settings:
        settings = UserSettingsDB()
        db.add(settings)
        db.commit()

    if settings.voltage_protection == 0:
        return

    voltage = charge_state.get("charger_voltage")
    current_amps = charge_state.get("charge_amps")
    charging_state = charge_state.get("charging_state")

    if charging_state != "Charging" or not voltage or not current_amps:
        return

    if voltage <= 208 and current_amps > MIN_CHARGING_AMPS:
        new_amps = max(MIN_CHARGING_AMPS, current_amps - 2)
        try:
            asyncio.run(
                send_signed_tesla_command(
                    vin,
                    token.access_token,
                    "set_charging_amps",
                    {"charging_amps": new_amps},
                )
            )
        except Exception as exc:
            print("Errore invio comando riduzione ampere:", exc)

    elif voltage >= 218 and current_amps < MAX_CHARGING_AMPS:
        new_amps = min(MAX_CHARGING_AMPS, current_amps + 1)
        try:
            asyncio.run(
                send_signed_tesla_command(
                    vin,
                    token.access_token,
                    "set_charging_amps",
                    {"charging_amps": new_amps},
                )
            )
        except Exception as exc:
            print("Errore invio comando aumento ampere:", exc)
