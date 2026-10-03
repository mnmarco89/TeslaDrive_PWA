from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_token
from ..services.trip_service import capture_lock
from ..services.cost_service import current_settings, initial_rate, add_rate

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_token)])


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    with capture_lock:
        settings = current_settings(db)
        initial_rate(db)
        db.commit()
        return dict(electricity=float(settings.electricity), diesel=float(settings.diesel),
                    diesel_km_l=float(settings.diesel_km_l), voltage_protection=settings.voltage_protection)


class SettingsPayload(BaseModel):
    electricity: float | None = Field(default=None, ge=0, le=10)
    diesel_km_l: float | None = Field(default=None, gt=0, le=100)
    voltage_protection: Literal[0, 1] | None = None


@router.post("/settings")
def save_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    with capture_lock:
        settings = current_settings(db)
        initial_rate(db)
        previous = tuple(float(getattr(settings, k)) for k in ("electricity", "diesel", "diesel_km_l"))
        values = payload.model_dump(exclude_none=True)
        for key in ("electricity", "diesel_km_l"):
            if key in values:
                setattr(settings, key, str(values[key]))
        if "voltage_protection" in values:
            settings.voltage_protection = values["voltage_protection"]
        updated = tuple(float(getattr(settings, k)) for k in ("electricity", "diesel", "diesel_km_l"))
        if updated != previous:
            add_rate(db, updated[0], None, updated[2])
        db.commit()
    return {"status": "saved"}
