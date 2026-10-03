import os

import aiohttp
import requests
from tesla_fleet_api import TeslaFleetApi

from ..config import TESLA_AUDIENCE, TESLA_PRIVATE_KEY


def authorization_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def get_vehicles(access_token: str):
    response = requests.get(
        f"{TESLA_AUDIENCE}/api/1/vehicles",
        headers=authorization_headers(access_token),
    )
    return response


def get_vehicle_data(vin: str, access_token: str, timeout=None):
    kwargs = {}
    if timeout is not None:
        kwargs["timeout"] = timeout

    return requests.get(
        f"{TESLA_AUDIENCE}/api/1/vehicles/{vin}/vehicle_data",
        headers=authorization_headers(access_token),
        **kwargs,
    )


async def send_signed_tesla_command(vin: str, token: str, endpoint: str, payload: dict):
    """Invia un comando Tesla firmato tramite Vehicle Command Protocol."""
    private_key_pem = TESLA_PRIVATE_KEY or os.getenv("TESLA_PRIVATE_KEY")
    if not private_key_pem:
        raise Exception(
            "TESLA_PRIVATE_KEY non configurata sul server. "
            "I comandi di ricarica falliranno."
        )

    key_path = "/tmp/tesla_private_key.pem"
    with open(key_path, "w") as key_file:
        key_file.write(private_key_pem)

    async with aiohttp.ClientSession() as session:
        api = TeslaFleetApi(
            access_token=token,
            session=session,
            region="eu",
        )
        await api.get_private_key(key_path)

        print(f"Invio comando firmato VCP '{endpoint}' in corso...")

        try:
            vehicle = api.vehicles.createSigned(vin)
            if endpoint == "set_charging_amps":
                return await vehicle.set_charging_amps(
                    charging_amps=payload.get("charging_amps")
                )
            raise ValueError(f"Comando Tesla non supportato: {endpoint}")
        except Exception as exc:
            print(f"Errore VCP Tesla: {exc}")
            raise
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)
