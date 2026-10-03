"""Persist optional model weather and terrain estimates without blocking Tesla polling."""
import json
import threading
from datetime import datetime, timedelta, timezone
import requests
from ..database import SessionLocal
from ..models import Trip, TripPoint, TripContext
from .trip_service import haversine, number, iso

_pending = set()
_lock = threading.Lock()


def route_samples(points):
    """Distance follows original segments; no fictitious ascent across a GPS gap."""
    valid = []
    previous = None
    distance = 0
    segment = 0
    for p in points:
        lat, lon = number(p.latitude), number(p.longitude)
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            previous = None
            continue
        if previous:
            dt = (p.recorded_at-previous.recorded_at).total_seconds()
            km = haversine(previous, p)
            if 0 < dt <= 180 and km/dt*3600 <= 250:
                distance += km
            else:
                segment += 1
        elif valid:
            segment += 1
        valid.append(dict(latitude=lat, longitude=lon, at=p.recorded_at, distance_km=distance, segment=segment))
        previous = p
    if len(valid) <= 100:
        return valid
    indexes = {round(i*(len(valid)-1)/99) for i in range(100)}
    return [valid[i] for i in sorted(indexes)]


def weather_for(sample, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    at = sample['at']
    age = (now.date()-at.date()).days
    url = 'https://api.open-meteo.com/v1/forecast' if 0 <= age <= 5 else 'https://archive-api.open-meteo.com/v1/archive'
    response = requests.get(url, params=dict(latitude=sample['latitude'], longitude=sample['longitude'],
        start_date=at.date().isoformat(), end_date=at.date().isoformat(), timezone='GMT',
        hourly='temperature_2m,precipitation,wind_speed_10m,wind_direction_10m,weather_code'), timeout=(5,15))
    response.raise_for_status()
    hourly = response.json().get('hourly') or {}
    times = hourly.get('time') or []
    target = at.replace(minute=0, second=0, microsecond=0).isoformat(timespec='minutes')
    if target not in times:
        raise ValueError('Ora del viaggio non disponibile nel modello meteo')
    index = times.index(target)
    result = {}
    for key in ['temperature_2m','precipitation','wind_speed_10m','wind_direction_10m','weather_code']:
        values = hourly.get(key) or []
        result[key] = number(values[index]) if index < len(values) else None
    if all(v is None for v in result.values()):
        raise ValueError('Dati meteo assenti per l’ora del viaggio')
    return {**result, 'at': target+'Z', 'latitude':sample['latitude'], 'longitude':sample['longitude'],
            'source':'Open-Meteo', 'kind':'model_at_departure'}


def elevation_for(samples):
    response = requests.get('https://api.open-meteo.com/v1/elevation', params={
        'latitude': ','.join(str(p['latitude']) for p in samples),
        'longitude': ','.join(str(p['longitude']) for p in samples)}, timeout=(5,15))
    response.raise_for_status()
    heights = [number(h) for h in response.json().get('elevation') or []]
    if len(heights) != len(samples) or any(number(h) is None for h in heights):
        raise ValueError('Quote del percorso non disponibili')
    profile = [{**p, 'at':iso(p['at']), 'elevation_m':number(h)} for p,h in zip(samples,heights)]
    up = down = 0
    anchor = None
    previous_segment = None
    for p in profile:
        if p['segment'] != previous_segment:
            anchor = p['elevation_m']
        delta = p['elevation_m']-anchor
        # 3 m deadband reduces DEM noise; these remain terrain estimates.
        if abs(delta) >= 3:
            up += max(0,delta)
            down += max(0,-delta)
            anchor = p['elevation_m']
        previous_segment = p['segment']
    paired = any(a['segment'] == b['segment'] for a,b in zip(profile,profile[1:]))
    return dict(profile=profile, ascent_m=round(up) if paired else None, descent_m=round(down) if paired else None,
        min_m=min(heights), max_m=max(heights), source='Open-Meteo · Copernicus DEM GLO-90',
        partial=len({p['segment'] for p in profile}) > 1, resolution_m=90)


def enrich(samples, previous=None):
    previous = previous or {}
    result = {'status':'ready', 'weather':None, 'elevation':None, 'errors':{}}
    for key, function in [('weather',lambda:weather_for(samples[0])),('elevation',lambda:elevation_for(samples))]:
        if previous.get(key):
            result[key] = previous[key]
            continue
        try:
            result[key] = function()
        except Exception:
            result['errors'][key] = 'Servizio temporaneamente non disponibile o dati mancanti. Riprovo dopo 30 minuti.'
    if result['errors']:
        result['status'] = 'partial' if result['weather'] or result['elevation'] else 'unavailable'
    return result


def _worker(trip_id, samples, previous):
    try:
        result = enrich(samples, previous)
        # Keep successful historical data if only the other service needs a retry.
        for key in ['weather','elevation']:
            if previous.get(key):
                result[key] = previous[key]
                result['errors'].pop(key,None)
        result['status'] = 'ready' if not result['errors'] else 'partial' if result['weather'] or result['elevation'] else 'unavailable'
        with SessionLocal() as db:
            if not db.get(Trip,trip_id):
                return
            state = db.get(TripContext,trip_id) or TripContext(trip_id=trip_id)
            state.payload = json.dumps(result,allow_nan=False)
            state.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(state)
            db.commit()
    finally:
        with _lock:
            _pending.discard(trip_id)


def context(db, trip):
    if trip.status == 'active':
        return {'status':'active', 'message':'Meteo e quote saranno elaborati al termine del viaggio.'}
    state = db.get(TripContext,trip.id)
    previous = json.loads(state.payload) if state and state.payload else {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if state and (previous.get('status') == 'ready' or state.updated_at and now-state.updated_at < timedelta(minutes=30)):
        return previous
    points = db.query(TripPoint).filter_by(trip_id=trip.id).order_by(TripPoint.recorded_at).all()
    samples = route_samples(points)
    if not samples:
        return {'status':'no_gps','message':'Meteo e quote richiedono almeno un punto GPS registrato.'}
    with _lock:
        if trip.id not in _pending and len(_pending) < 3:
            _pending.add(trip.id)
            threading.Thread(target=_worker,args=(trip.id,samples,previous),daemon=True,name='trip-context').start()
    return {**previous,'status':'pending','message':'Recupero meteo e quote…'}
