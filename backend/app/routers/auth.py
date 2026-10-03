import secrets

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import TESLA_CLIENT_ID, TESLA_CLIENT_SECRET, TESLA_REDIRECT_URI
from ..database import get_db
from ..models import UserToken

router = APIRouter()


@router.get("/auth/tesla/start")
def tesla_start_login():
    state = secrets.token_urlsafe(16)
    scopes = (
        "openid offline_access user_data vehicle_device_data "
        "vehicle_cmds vehicle_charging_cmds"
    )
    auth_url = (
        "https://auth.tesla.com/oauth2/v3/authorize?"
        "response_type=code&"
        f"client_id={TESLA_CLIENT_ID}&"
        f"redirect_uri={TESLA_REDIRECT_URI}&"
        f"scope={requests.utils.quote(scopes)}&"
        f"state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/auth/tesla/callback")
def tesla_callback(code: str, db: Session = Depends(get_db)):
    response = requests.post(
        "https://auth.tesla.com/oauth2/v3/token",
        json={
            "grant_type": "authorization_code",
            "client_id": TESLA_CLIENT_ID,
            "client_secret": TESLA_CLIENT_SECRET,
            "code": code,
            "redirect_uri": TESLA_REDIRECT_URI,
        },
    )
    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch token: {response.text}",
        )

    data = response.json()
    db.add(
        UserToken(
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
        )
    )
    db.commit()
    return RedirectResponse(url="/")


@router.post("/auth/logout")
def logout(db: Session = Depends(get_db)):
    db.query(UserToken).delete()
    db.commit()
    return {"status": "logged_out"}


@router.get("/api/status")
def api_status(db: Session = Depends(get_db)):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    return {"authenticated": token is not None}
