"""Capacity estimate from observed charging deltas, never model/VIN guesses."""
from datetime import datetime, timezone
from statistics import median
from ..models import BatteryCalibration, BatteryObservation, TrackingVehicle
from .trip_service import number, iso


def battery_info(db, vin):
    v = db.get(TrackingVehicle, vin)
    readings = db.query(BatteryObservation).filter_by(vin=vin).order_by(BatteryObservation.recorded_at.desc()).limit(10).all()
    estimate = median([r.capacity_kwh for r in readings]) if readings else None
    return dict(capacity_kwh=v.capacity_kwh if v else None,
                automatic_capacity_kwh=round(estimate, 1) if estimate else None,
                effective_capacity_kwh=v.capacity_kwh if v and v.capacity_kwh is not None else estimate,
                capacity_source="manual" if v and v.capacity_kwh is not None else "charging_estimate" if estimate else None,
                calibration_sessions=len(readings), calibration_updated_at=iso(readings[0].recorded_at) if readings else None,
                nominal_capacity_kwh=db.get(BatteryCalibration, vin).nominal_kwh if db.get(BatteryCalibration, vin) else None)


def _finish(db, state):
    if state.start_soc is not None and state.last_soc is not None and state.start_energy is not None and state.last_energy is not None:
        ds, de = state.last_soc-state.start_soc, state.last_energy-state.start_energy
        if ds >= 20 and de > 0:
            capacity = de/ds*100
            if 10 <= capacity <= 200:
                db.add(BatteryObservation(vin=state.vin, recorded_at=state.last_sample_at, capacity_kwh=capacity, soc_delta=ds))
    state.started_at = None
    state.start_soc = state.start_energy = state.last_soc = state.last_energy = None


def record_charging_sample(db, vin, data):
    charge = data.get("charge_state") or {}
    stamp = number(charge.get("timestamp"))
    if stamp is None:
        return
    try:
        at = datetime.fromtimestamp(stamp/1000, timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not -60 <= (now-at).total_seconds() <= 180:
        return
    state = db.get(BatteryCalibration, vin)
    if not state:
        state = BatteryCalibration(vin=vin)
        db.add(state)
    if state.last_sample_at and at <= state.last_sample_at:
        return
    if state.last_sample_at and (at-state.last_sample_at).total_seconds() > 180:
        # Don't join separate charging sessions across an unobserved interval.
        state.started_at = None
    nominal = number(charge.get("nominal_full_pack_energy"))
    if nominal is not None and 10 <= nominal <= 200:
        state.nominal_kwh = nominal  # informational; nominal is not usable capacity
    soc = number(charge.get("battery_level"))
    energy = number(charge.get("charge_energy_added"))
    valid = soc is not None and 0 <= soc <= 100 and energy is not None and energy >= 0
    charging = charge.get("charging_state") == "Charging"
    if state.started_at and valid and state.last_energy is not None and energy < state.last_energy:
        _finish(db, state)
    if charging and valid:
        if state.started_at is None:
            state.started_at, state.start_soc, state.start_energy = at, soc, energy
        state.last_soc, state.last_energy = soc, energy
    elif charge.get("charging_state") in ("Complete", "Stopped", "Disconnected") and state.started_at:
        if valid and energy >= (state.last_energy or 0):
            state.last_soc, state.last_energy = soc, energy
        _finish(db, state)
    state.last_sample_at = at
    db.flush()
