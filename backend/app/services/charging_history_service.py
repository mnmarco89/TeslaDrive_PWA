"""Observed charging increments; never infer energy across missing coverage."""
from datetime import datetime, timedelta, timezone, time
from statistics import median
from zoneinfo import ZoneInfo
from ..models import ChargingSession, ChargingIncrement, BatteryObservation
from .trip_service import number, iso
from .battery_service import battery_info

LOCAL = ZoneInfo('Europe/Rome')


def sample_time(value, scale=1000):
    stamp = number(value)
    if stamp is None:
        return None
    try:
        return datetime.fromtimestamp(stamp/scale, timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None


def record_history(db, vin, data):
    charge = data.get('charge_state') or {}
    at = sample_time(charge.get('timestamp'))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if at is None or not -60 <= (now-at).total_seconds() <= 180:
        return
    state = charge.get('charging_state')
    counter = number(charge.get('charge_energy_added'))
    if state not in ('Charging', 'Complete', 'Stopped', 'Disconnected') or counter is None or counter < 0:
        return
    soc = number(charge.get('battery_level'))
    if soc is not None and not 0 <= soc <= 100:
        soc = None
    latest = db.query(ChargingSession).filter_by(vin=vin).order_by(ChargingSession.last_sample_at.desc()).first()
    if latest and at <= latest.last_sample_at:
        return
    session = db.query(ChargingSession).filter_by(vin=vin, status='active').first()
    if session and at <= session.last_sample_at:
        return
    if session and ((at-session.last_sample_at).total_seconds() > 180 or counter < session.last_counter_kwh):
        session.status, session.ended_at, session.partial = 'interrupted', session.last_sample_at, True
        session = None
    if session is None:
        if state != 'Charging':
            return
        session = ChargingSession(vin=vin, started_at=at, last_sample_at=at,
            start_soc=soc, end_soc=soc, last_counter_kwh=counter, energy_kwh=0, partial=counter > 0)
        db.add(session)
        db.flush()
        return
    start = session.last_sample_at.replace(tzinfo=timezone.utc)
    end = at.replace(tzinfo=timezone.utc)
    duration = (end-start).total_seconds()
    delta = counter-session.last_counter_kwh
    crossed = start.astimezone(LOCAL).date() != end.astimezone(LOCAL).date()
    cursor = start
    while cursor < end:
        local_day = cursor.astimezone(LOCAL).date()
        midnight = datetime.combine(local_day+timedelta(days=1), time(), LOCAL).astimezone(timezone.utc)
        stop = min(midnight, end)
        seconds = (stop-cursor).total_seconds()
        if delta > 0:
            db.add(ChargingIncrement(session_id=session.id, day=local_day.isoformat(),
                energy_kwh=delta*seconds/duration, seconds=seconds, midnight_estimate=crossed))
        cursor = stop
    session.energy_kwh += delta
    session.last_counter_kwh, session.last_sample_at, session.end_soc = counter, at, soc
    if state != 'Charging':
        session.status, session.ended_at = 'completed', at
    db.flush()


def history(db, vin, days=30, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    # Close stale observations without inventing a completion sample.
    for session in db.query(ChargingSession).filter_by(vin=vin, status='active').all():
        if (now-session.last_sample_at).total_seconds() > 180:
            session.status, session.ended_at, session.partial = 'interrupted', session.last_sample_at, True
    db.commit()
    today = now.replace(tzinfo=timezone.utc).astimezone(LOCAL).date()
    first = today-timedelta(days=days-1)
    daily = { (first+timedelta(days=i)).isoformat(): dict(day=(first+timedelta(days=i)).isoformat(), energy_kwh=0,
        sessions=0, partial=False, midnight_estimate=False) for i in range(days) }
    covered = {day:set() for day in daily}
    rows = db.query(ChargingIncrement, ChargingSession).join(ChargingSession).filter(
        ChargingSession.vin == vin, ChargingIncrement.day >= first.isoformat(), ChargingIncrement.day <= today.isoformat()).all()
    for item, session in rows:
        entry = daily[item.day]
        entry['energy_kwh'] += item.energy_kwh
        entry['partial'] |= session.partial
        entry['midnight_estimate'] |= item.midnight_estimate
        covered[item.day].add(session.id)
    for session in db.query(ChargingSession).filter_by(vin=vin).filter(ChargingSession.last_sample_at >= datetime.combine(first, time(), LOCAL).astimezone(timezone.utc).replace(tzinfo=None)).all():
        day = session.last_sample_at.replace(tzinfo=timezone.utc).astimezone(LOCAL).date().isoformat()
        if day in covered:
            covered[day].add(session.id)
            daily[day]['partial'] |= session.partial
    for day, entry in daily.items():
        entry['energy_kwh'] = round(entry['energy_kwh'],3)
        entry['sessions'] = len(covered[day])
    observations = db.query(BatteryObservation).filter_by(vin=vin).order_by(BatteryObservation.recorded_at, BatteryObservation.id).all()
    baseline = median([o.capacity_kwh for o in observations[:3]]) if len(observations) >= 3 else None
    comparison = observations[3:][-10:] if len(observations) >= 6 else observations[-10:]
    recent = median([o.capacity_kwh for o in comparison]) if comparison else None
    # Baseline comparison needs three subsequent observations, not an overlapping baseline.
    variation = (recent/baseline-1)*100 if baseline and len(observations) >= 6 else None
    filtered = [o for o in observations if o.recorded_at.replace(tzinfo=timezone.utc).astimezone(LOCAL).date() >= first]
    # Bounded response preserves first and latest points if there are many readings.
    if len(filtered) > 200:
        filtered = [filtered[round(i*(len(filtered)-1)/199)] for i in range(200)]
    all_sessions = db.query(ChargingSession).filter_by(vin=vin).order_by(ChargingSession.started_at).first()
    return dict(timezone='Europe/Rome', days=list(daily.values()),
        total_energy_kwh=round(sum(e['energy_kwh'] for e in daily.values()),3),
        session_count=len(set().union(*covered.values())),
        recording_since=iso(all_sessions.started_at) if all_sessions else None,
        battery=battery_info(db, vin), capacity_baseline_kwh=round(baseline,1) if baseline else None,
        capacity_recent_kwh=round(recent,1) if recent else None,
        capacity_variation_percent=round(variation,1) if variation is not None else None,
        capacity_observations=len(observations), capacity_points=[dict(at=iso(o.recorded_at),
            capacity_kwh=round(o.capacity_kwh,2), soc_delta=o.soc_delta) for o in filtered])
