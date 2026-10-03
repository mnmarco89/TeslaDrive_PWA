"""Account presentation and a strict whitelist of signed remote controls."""
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_token
from ..models import UserToken
from ..services.trip_collector import _request, invalidate_sample
from starlette.concurrency import run_in_threadpool
from ..services.tesla_service import send_signed_tesla_command

router = APIRouter(prefix="/api")


@router.get("/profile")
def profile(token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    try:
        response = _request(db, "/api/1/users/me")
    except Exception:
        raise HTTPException(503, "Profilo Tesla temporaneamente non disponibile")
    if response is None:
        raise HTTPException(401, "Ricollega l’account Tesla")
    if response.status_code == 403:
        return {"available": False, "scope_needed": True, "message": "Ricollega Tesla autorizzando le informazioni del profilo."}
    if response.status_code != 200:
        raise HTTPException(503, "Profilo Tesla temporaneamente non disponibile")
    data = response.json().get("response") or {}
    name = data.get("full_name") or " ".join(filter(None, [data.get("first_name"), data.get("last_name")]))
    photo = data.get("profile_image_url")
    if not isinstance(photo, str) or urlparse(photo).scheme != "https" or not urlparse(photo).hostname:
        photo = None
    return {"available": True, "name": name or None, "first_name": data.get("first_name"),
            "email": data.get("email"), "photo_url": photo}


class HomeCommand(BaseModel):
    action: Literal["lock", "unlock", "front_trunk", "rear_trunk", "climate_on", "climate_off", "charge_port_open", "charge_port_close"]


COMMANDS = {
    "lock": ("door_lock", {}), "unlock": ("door_unlock", {}),
    "front_trunk": ("actuate_trunk", {"which_trunk": "front"}),
    "rear_trunk": ("actuate_trunk", {"which_trunk": "rear"}),
    "climate_on": ("auto_conditioning_start", {}), "climate_off": ("auto_conditioning_stop", {}),
    "charge_port_open": ("charge_port_door_open", {}), "charge_port_close": ("charge_port_door_close", {}),
}


@router.post("/vehicles/{vin}/controls")
async def controls(vin: str, payload: HomeCommand, token: UserToken = Depends(get_current_token)):
    endpoint, parameters = COMMANDS[payload.action]
    try:
        result = await send_signed_tesla_command(vin, token.access_token, endpoint, parameters)
        await run_in_threadpool(invalidate_sample, vin)
        return {"status": "accepted", "action": payload.action, "tesla_response": result}
    except Exception as exc:
        message = str(exc)
        if "scope" in message.lower() or "403" in message:
            message = "Permessi comandi mancanti: ricollega Tesla autorizzando il controllo del veicolo."
        elif "key" in message.lower() or "chiave" in message.lower():
            message = "Verifica la chiave virtuale dell’app e la chiave privata configurata sul server."
        raise HTTPException(400, message or "Comando non confermato da Tesla")
