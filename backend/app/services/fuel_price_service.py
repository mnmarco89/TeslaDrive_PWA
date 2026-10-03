"""Automatic GPS-based diesel quotes; no hardcoded/manual diesel fallback."""
from .fuel_data_service import nearest_price
from ..models import FuelPriceState
from .trip_service import sample_from_data, capture_lock, number
from .cost_service import now_utc, current_settings, initial_rate, add_rate


def refresh_fuel_price(db, vin, data):
    sample = sample_from_data(data)
    if not sample or sample["latitude"] is None or data.get("_location_unavailable"):
        return
    with capture_lock:
        now = now_utc()
        state = db.get(FuelPriceState, vin)
        if not state:
            state = FuelPriceState(vin=vin)
            db.add(state)
        wait = 3600 if state.diesel is not None and not state.error else 900
        if state.last_attempt_at and (now-state.last_attempt_at).total_seconds() < wait:
            return
        state.last_attempt_at = now
        db.commit()
    # Network work is outside the recording lock so telemetry/history stay responsive.
    try:
        quote = nearest_price(sample["latitude"], sample["longitude"])
        price = number(quote.get("diesel"))
        if price is None or not 0 < price <= 20:
            raise ValueError("Nessun prezzo diesel disponibile")
        with capture_lock:
            db.expire_all()
            state = db.get(FuelPriceState, vin)
            settings = current_settings(db)
            initial_rate(db)
            if state.diesel is None or abs(state.diesel-price) > .000001:
                rate = add_rate(db, float(settings.electricity), price, float(settings.diesel_km_l),
                         at=sample["at"], source="gps_auto", vin=vin)
                rate.station, rate.dataset_date = quote.get("station"), quote.get("dataset_date")
            state.diesel, state.last_success_at, state.error = price, now, None
            state.station, state.city = quote.get("station"), quote.get("city")
            state.dataset_date, state.reported_at = quote.get("dataset_date"), quote.get("reported_at")
            db.commit()
    except Exception:
        db.rollback()
        with capture_lock:
            state = db.get(FuelPriceState, vin)
            state.error = "Prezzo automatico temporaneamente non disponibile; conservato l’ultimo prezzo rilevato"
            db.commit()


import threading
from ..database import SessionLocal
_pending = set()
_pending_lock = threading.Lock()


def schedule_fuel_refresh(db, vin, data):
    sample = sample_from_data(data)
    if not sample or sample["latitude"] is None or data.get("_location_unavailable"):
        return
    state = db.get(FuelPriceState, vin)
    wait = 3600 if state and state.diesel is not None and not state.error else 900
    if state and state.last_attempt_at and (now_utc()-state.last_attempt_at).total_seconds() < wait:
        return
    with _pending_lock:
        if vin in _pending:
            return
        _pending.add(vin)
    def run():
        try:
            with SessionLocal() as session:
                refresh_fuel_price(session, vin, data)
        finally:
            with _pending_lock:
                _pending.discard(vin)
    threading.Thread(target=run, daemon=True, name="fuel-price-update").start()
