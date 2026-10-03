"""Single-process background collector; never sends a wake-up command."""
import logging
import os
import threading
import time
from datetime import datetime, timezone
import requests
from ..config import TESLA_AUDIENCE, TESLA_CLIENT_ID, TESLA_CLIENT_SECRET
from ..database import SessionLocal
from ..models import TrackingVehicle, UserToken
from .trip_service import capture_lock, expire_trip, record_sample
from .tesla_service import authorization_headers

logger = logging.getLogger(__name__)
DRIVING_INTERVAL = max(15, int(os.getenv("TRIP_DRIVING_INTERVAL", "15")))
IDLE_INTERVAL = max(60, int(os.getenv("TRIP_IDLE_INTERVAL", "60")))
_cache = {}
_backoff = {}
_data_lock = threading.RLock()


def register_vehicles(db, items):
    with capture_lock:
        for item in items:
            vin = item.get("vin")
            if vin and db.get(TrackingVehicle, vin) is None:
                db.add(TrackingVehicle(vin=vin))
        db.commit()


def _request(db, path, params=None):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    if not token:
        return None
    response = requests.get(TESLA_AUDIENCE + path, headers=authorization_headers(token.access_token),
                            params=params, timeout=20)
    if response.status_code == 401 and token.refresh_token:
        refreshed = requests.post("https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token", data={
            "grant_type": "refresh_token", "client_id": TESLA_CLIENT_ID,
            "refresh_token": token.refresh_token}, timeout=20)
        if refreshed.status_code == 200:
            payload = refreshed.json()
            token.access_token = payload["access_token"]
            token.refresh_token = payload.get("refresh_token") or token.refresh_token
            db.commit()
            response = requests.get(TESLA_AUDIENCE + path, headers=authorization_headers(token.access_token),
                                    params=params, timeout=20)
    return response


def fetch_sample(db, vin):
    with _data_lock:
        if time.monotonic() < _backoff.get(vin, 0):
            raise ValueError("Limite API Tesla raggiunto: raccolta in pausa")
        cached = _cache.get(vin)
        if cached and time.monotonic()-cached[0] < DRIVING_INTERVAL:
            return cached[1]
        response = _request(db, f"/api/1/vehicles/{vin}/vehicle_data", params={
            "endpoints": "location_data;drive_state;charge_state;vehicle_state;climate_state"})
        location_unavailable = False
        if response is not None and response.status_code == 403:
            try:
                missing_scope = response.json().get("error") == "Unauthorized missing scopes"
            except (ValueError, AttributeError):
                missing_scope = False
            if missing_scope:
                response = _request(db, f"/api/1/vehicles/{vin}/vehicle_data", params={
                    "endpoints": "drive_state;charge_state;vehicle_state;climate_state"})
                location_unavailable = True
        if response is None:
            raise ValueError("Collega nuovamente l’account Tesla")
        if response.status_code != 200:
            if response.status_code == 429:
                try:
                    delay = max(300, int(response.headers.get("Retry-After", "300")))
                except (ValueError, TypeError):
                    delay = 300
                _backoff[vin] = time.monotonic() + delay
            messages = {401: "Autorizzazione scaduta: ricollega Tesla", 403: "Permessi Tesla mancanti: ricollega con accesso alla posizione",
                        408: "Auto non raggiungibile", 429: "Limite API Tesla raggiunto: raccolta in pausa"}
            raise ValueError(messages.get(response.status_code, f"API Tesla: HTTP {response.status_code}"))
        data = response.json().get("response") or {}
        if location_unavailable:
            data["_location_unavailable"] = True
        _cache[vin] = (time.monotonic(), data)
    from .fuel_price_service import schedule_fuel_refresh
    schedule_fuel_refresh(db, vin, data)
    record_sample(db, vin, data)
    return data


def invalidate_sample(vin):
    """After a confirmed command, the next read must request vehicle state again."""
    with _data_lock:
        _cache.pop(vin, None)


class TripCollector:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name="trip-collector")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1)

    def run(self):
        online = set()
        next_list = 0
        due = {}
        while not self.stop_event.is_set():
            try:
                with SessionLocal() as db:
                    if not db.query(UserToken).first():
                        online = set()
                        _cache.clear()
                        _backoff.clear()
                        next_list = 0
                    else:
                        now = time.monotonic()
                        if now >= next_list:
                            next_list = now + IDLE_INTERVAL
                            response = _request(db, "/api/1/vehicles")
                            if response is not None and response.status_code == 200:
                                items = response.json().get("response") or []
                                register_vehicles(db, items)
                                online = {v["vin"] for v in items if v.get("vin") and v.get("state") == "online"}
                            else:
                                online = None
                                for vehicle in db.query(TrackingVehicle).filter_by(enabled=True):
                                    vehicle.last_status = "Accesso API non disponibile: controlla autorizzazione Tesla"
                                db.commit()
                        vins = [v.vin for v in db.query(TrackingVehicle).filter_by(enabled=True)]
                        for vin in vins:
                            if self.stop_event.is_set():
                                break
                            with capture_lock:
                                expire_trip(db, vin)
                            if online is None:
                                continue
                            if vin not in online:
                                db.get(TrackingVehicle, vin).last_status = "Auto offline o addormentata"
                                db.commit()
                                continue
                            if now < due.get(vin, 0):
                                continue
                            due[vin] = now + IDLE_INTERVAL
                            try:
                                data = fetch_sample(db, vin)
                                drive = data.get("drive_state") or {}
                                moving = drive.get("shift_state") in ("D", "R", "N") or (drive.get("speed") or 0) > 0
                                due[vin] = time.monotonic() + (DRIVING_INTERVAL if moving else IDLE_INTERVAL)
                            except Exception as exc:
                                db.rollback()
                                vehicle = db.get(TrackingVehicle, vin)
                                vehicle.last_status = str(exc) if isinstance(exc, ValueError) else "Connessione Tesla non disponibile"
                                db.commit()
                                due[vin] = time.monotonic() + (300 if "429" in str(exc) or "Limite API" in str(exc) else IDLE_INTERVAL)
            except Exception:
                logger.warning("Raccolta viaggi temporaneamente non disponibile", exc_info=False)
            self.stop_event.wait(5)
