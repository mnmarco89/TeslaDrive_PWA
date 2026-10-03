import os
import tempfile

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
        timeout=20,
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
            "I comandi remoti richiedono la chiave privata."
        )

    allowed = {
        "door_lock", "door_unlock", "actuate_trunk", "auto_conditioning_start",
        "auto_conditioning_stop", "charge_port_door_open", "charge_port_door_close",
        "set_charging_amps",
    }
    if endpoint not in allowed:
        raise ValueError(f"Comando Tesla non supportato: {endpoint}")
    # A unique, owner-only file prevents concurrent commands sharing a key path.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as key_file:
        key_file.write(private_key_pem)
        key_path = key_file.name
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            api = TeslaFleetApi(access_token=token, session=session, region="eu")
            await api.get_private_key(key_path)
            vehicle = api.vehicles.createSigned(vin)
            if endpoint == "set_charging_amps":
                result = await vehicle.set_charging_amps(charging_amps=payload.get("charging_amps"))
            elif endpoint == "actuate_trunk":
                if payload.get("which_trunk") not in {"front", "rear"}:
                    raise ValueError("Bagagliaio non valido")
                result = await vehicle.actuate_trunk(which_trunk=payload["which_trunk"])
            else:
                result = await getattr(vehicle, endpoint)()
            reply = result.get("response", result) if isinstance(result, dict) else None
            if not isinstance(reply, dict) or reply.get("result") is not True:
                reason = reply.get("reason") if isinstance(reply, dict) else None
                raise ValueError(reason or "Tesla non ha confermato il comando")
            return result
    finally:
        if os.path.exists(key_path):
            os.remove(key_path)
