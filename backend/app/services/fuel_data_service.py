"""Official MIMIT daily CSV data, cached per Rome calendar day."""
import csv
import io
import math
import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

_lock = threading.Lock()
_cache = None


def rows(text):
    lines = text.lstrip('\ufeff').splitlines()
    header_index = next((i for i, line in enumerate(lines[:5]) if 'idimpianto' in line.lower()), None)
    if header_index is None:
        raise ValueError('Intestazione dataset carburanti non valida')
    header = lines[header_index]
    delimiter = '|' if '|' in header else ';'
    reader = csv.DictReader(io.StringIO('\n'.join(lines[header_index:])), delimiter=delimiter)
    extraction = re.search(r'\d{4}-\d{2}-\d{2}', '\n'.join(lines[:header_index]))
    return reader, extraction.group(0) if extraction else None


def parse_data(station_csv, price_csv):
    reader, _ = rows(station_csv)
    stations = {}
    for raw in reader:
        r = {k.strip().lower(): v.strip() for k, v in raw.items() if k and v is not None}
        try:
            lat, lon = float(r['latitudine']), float(r['longitudine'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            stations[r['idimpianto']] = dict(latitude=lat, longitude=lon,
                station=r.get('nome impianto') or r.get('bandiera') or r['idimpianto'], city=r.get('comune', ''))
        except (KeyError, ValueError):
            continue
    reader, extracted = rows(price_csv)
    candidates = []
    for raw in reader:
        r = {k.strip().lower(): v.strip() for k, v in raw.items() if k and v is not None}
        if r.get('desccarburante', '').lower() != 'gasolio' or r.get('isself') != '1':
            continue
        station = stations.get(r.get('idimpianto'))
        if not station:
            continue
        try:
            price = float(r['prezzo'])
            if math.isfinite(price) and 0 < price <= 20:
                candidates.append({**station, 'diesel': price, 'station_id': r['idimpianto'],
                                   'reported_at': r.get('dtcomu'), 'dataset_date': extracted})
        except (KeyError, ValueError):
            continue
    if not candidates:
        raise ValueError('Nessun prezzo gasolio self-service valido nel dataset')
    return candidates


def download(name):
    response = requests.get('https://www.mimit.gov.it/images/exportCSV/'+name, timeout=20, stream=True)
    try:
        response.raise_for_status()
        content = bytearray()
        deadline = time.monotonic()+30
        for block in response.iter_content(65536):
            if time.monotonic() > deadline:
                raise TimeoutError("Download dataset carburanti troppo lento")
            content.extend(block)
            if len(content) > 50 * 1024 * 1024:
                raise ValueError('Dataset carburanti troppo grande')
        return content.decode('utf-8-sig', errors='replace')
    finally:
        response.close()


def nearest_price(latitude, longitude):
    global _cache
    today = datetime.now(ZoneInfo('Europe/Rome')).date().isoformat()
    with _lock:
        if _cache is None or _cache[0] != today:
            values = parse_data(download('anagrafica_impianti_attivi.csv'), download('prezzo_alle_8.csv'))
            _cache = today, values
        values = _cache[1]
    lat1 = math.radians(latitude)
    nearest = None
    best_distance = 10.0
    for item in values:
        lat2 = math.radians(item['latitude'])
        dlat, dlon = lat2-lat1, math.radians(item['longitude']-longitude)
        h = math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        km = 6371*2*math.asin(min(1, math.sqrt(h)))
        if km <= best_distance:
            nearest, best_distance = item, km
    if nearest is None:
        raise ValueError('Nessun distributore con gasolio self-service entro 10 km')
    return {**nearest, 'distance_km': round(best_distance, 2), 'source': 'MIMIT Osservaprezzi Carburanti'}
