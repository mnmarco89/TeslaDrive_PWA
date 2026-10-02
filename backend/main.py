import os, secrets, time, json, base64, hashlib
from urllib.parse import urlencode
from datetime import datetime, timezone

import httpx
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from cryptography.fernet import Fernet

CLIENT_ID = os.getenv('TESLA_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('TESLA_CLIENT_SECRET', '')
REDIRECT_URI = os.getenv('TESLA_REDIRECT_URI', '')
APP_BASE_URL = os.getenv('APP_BASE_URL', '')
DATABASE_URL = os.getenv('DATABASE_URL', '')
AUDIENCE = os.getenv('TESLA_AUDIENCE', 'https://fleet-api.prd.eu.vn.cloud.tesla.com')
AUTH_BASE = 'https://auth.tesla.com/oauth2/v3'
TOKEN_URL = 'https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token'
SCOPE = 'openid offline_access vehicle_device_data vehicle_location'
SESSION_SECRET = os.getenv('SESSION_SECRET', 'change-me')
COOKIE_SECURE = APP_BASE_URL.startswith('https://')

app = FastAPI(title='TeslaDrive', version='2.0.0')

FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SESSION_SECRET.encode()).digest()))


def conn():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL non configurato')
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS oauth (
            id INTEGER PRIMARY KEY CHECK (id=1), access TEXT NOT NULL, refresh TEXT NOT NULL,
            expires BIGINT NOT NULL, token_type TEXT NOT NULL DEFAULT 'Bearer'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id=1), electricity DOUBLE PRECISION NOT NULL DEFAULT 0.25,
            diesel DOUBLE PRECISION NOT NULL DEFAULT 1.70, diesel_km_l DOUBLE PRECISION NOT NULL DEFAULT 20.0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS telemetry (
            id BIGSERIAL PRIMARY KEY, ts BIGINT NOT NULL, vin TEXT NOT NULL, payload JSONB NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS trips (
            id BIGSERIAL PRIMARY KEY, vin TEXT NOT NULL, started BIGINT, ended BIGINT,
            start_lat DOUBLE PRECISION, start_lon DOUBLE PRECISION, end_lat DOUBLE PRECISION, end_lon DOUBLE PRECISION,
            km DOUBLE PRECISION, energy_kwh DOUBLE PRECISION, diesel_price DOUBLE PRECISION,
            electricity_price DOUBLE PRECISION, destination TEXT, route_line TEXT
        )''')
        c.execute("INSERT INTO settings(id) VALUES(1) ON CONFLICT (id) DO NOTHING")


@app.on_event('startup')
def startup():
    init_db()


def oauth_row():
    with conn() as c:
        return c.execute('SELECT * FROM oauth WHERE id=1').fetchone()


def encrypt(v: str) -> str:
    return FERNET.encrypt(v.encode()).decode()


def decrypt(v: str) -> str:
    return FERNET.decrypt(v.encode()).decode()


async def get_access_token():
    r = oauth_row()
    if not r:
        raise HTTPException(401, 'Tesla non collegata')
    if r['expires'] > int(time.time()) + 90:
        return decrypt(r['access'])
    refresh = decrypt(r['refresh'])
    async with httpx.AsyncClient(timeout=30) as x:
        z = await x.post(TOKEN_URL, data={
            'grant_type': 'refresh_token', 'client_id': CLIENT_ID,
            'refresh_token': refresh, 'audience': AUDIENCE, 'scope': SCOPE
        })
    if z.status_code >= 400:
        raise HTTPException(401, 'Token Tesla scaduto: ricollega Tesla')
    d = z.json()
    with conn() as c:
        c.execute('UPDATE oauth SET access=%s, refresh=%s, expires=%s, token_type=%s WHERE id=1',
                  (encrypt(d['access_token']), encrypt(d.get('refresh_token', refresh)),
                   int(time.time()) + int(d.get('expires_in', 3600)), d.get('token_type', 'Bearer')))
    return d['access_token']


async def tesla(method, path, **kwargs):
    tok = await get_access_token()
    async with httpx.AsyncClient(timeout=30) as x:
        r = await x.request(method, AUDIENCE + path, headers={'Authorization': f'Bearer {tok}'}, **kwargs)
    if r.status_code == 401:
        raise HTTPException(401, 'Autorizzazione Tesla non valida')
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:1000])
    return r.json() if r.content else {}


def response_list(data):
    if isinstance(data, dict) and 'response' in data:
        return data['response']
    return data if isinstance(data, list) else []


@app.get('/health')
def health():
    try:
        with conn() as c:
            c.execute('SELECT 1')
        return {'ok': True, 'tesla_connected': oauth_row() is not None}
    except Exception as e:
        return JSONResponse(status_code=503, content={'ok': False, 'error': str(e)})


@app.get('/auth/tesla/start')
async def auth_start():
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(500, 'Configura TESLA_CLIENT_ID, TESLA_CLIENT_SECRET e TESLA_REDIRECT_URI')
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    params = {
        'client_id': CLIENT_ID, 'locale': 'it-IT', 'redirect_uri': REDIRECT_URI,
        'response_type': 'code', 'scope': SCOPE, 'state': state, 'nonce': nonce,
        'prompt_missing_scopes': 'true', 'require_requested_scopes': 'true'
    }
    out = RedirectResponse(AUTH_BASE + '/authorize?' + urlencode(params))
    out.set_cookie('tesla_oauth_state', state, httponly=True, secure=COOKIE_SECURE, samesite='lax', max_age=600)
    return out


@app.get('/auth/tesla/callback')
async def auth_callback(request: Request, code: str = '', state: str = ''):
    if not code or state != request.cookies.get('tesla_oauth_state'):
        raise HTTPException(400, 'OAuth state non valido')
    async with httpx.AsyncClient(timeout=30) as x:
        r = await x.post(TOKEN_URL, data={
            'grant_type': 'authorization_code', 'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET, 'code': code,
            'audience': AUDIENCE, 'redirect_uri': REDIRECT_URI, 'scope': SCOPE
        })
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:1000])
    d = r.json()
    with conn() as c:
        c.execute('DELETE FROM oauth')
        c.execute('INSERT INTO oauth(id,access,refresh,expires,token_type) VALUES(1,%s,%s,%s,%s)',
                  (encrypt(d['access_token']), encrypt(d.get('refresh_token', '')),
                   int(time.time()) + int(d.get('expires_in', 3600)), d.get('token_type', 'Bearer')))
    out = RedirectResponse(APP_BASE_URL + '/?connected=1')
    out.delete_cookie('tesla_oauth_state')
    return out


@app.post('/auth/logout')
def logout():
    with conn() as c:
        c.execute('DELETE FROM oauth')
    return {'ok': True}


@app.get('/api/status')
def status():
    return {'connected': oauth_row() is not None}


@app.get('/api/vehicles')
async def vehicles():
    return await tesla('GET', '/api/1/vehicles')


@app.get('/api/vehicle/{vin}')
async def vehicle(vin: str):
    return await tesla('GET', f'/api/1/vehicles/{vin}')


@app.get('/api/vehicle/{vin}/data')
async def vehicle_data(vin: str):
    return await tesla('GET', f'/api/1/vehicles/{vin}/vehicle_data', params={
        'endpoints': 'drive_state;charge_state;vehicle_state;vehicle_config;climate_state;gui_settings'
    })


class Settings(BaseModel):
    electricity: float
    diesel: float
    diesel_km_l: float


@app.get('/api/settings')
def settings():
    with conn() as c:
        return c.execute('SELECT * FROM settings WHERE id=1').fetchone()


@app.post('/api/settings')
def save_settings(s: Settings):
    if min(s.electricity, s.diesel, s.diesel_km_l) <= 0:
        raise HTTPException(400, 'Valori non validi')
    with conn() as c:
        c.execute('UPDATE settings SET electricity=%s,diesel=%s,diesel_km_l=%s WHERE id=1',
                  (s.electricity, s.diesel, s.diesel_km_l))
    return {'ok': True}


@app.post('/api/telemetry')
async def telemetry(request: Request):
    # Endpoint applicativo per record già decodificati. Il server Fleet Telemetry ufficiale
    # riceve il protocollo Tesla/WebSocket e va installato separatamente.
    body = await request.json()
    vin = request.headers.get('x-tesla-vin', body.get('vin', ''))
    if not vin:
        raise HTTPException(400, 'VIN mancante')
    with conn() as c:
        c.execute('INSERT INTO telemetry(ts,vin,payload) VALUES(%s,%s,%s)',
                  (int(time.time()), vin, json.dumps(body)))
    return {'ok': True}


@app.get('/api/telemetry/latest/{vin}')
def telemetry_latest(vin: str):
    with conn() as c:
        return c.execute('SELECT ts,vin,payload FROM telemetry WHERE vin=%s ORDER BY ts DESC LIMIT 1', (vin,)).fetchone()


@app.get('/api/trips')
def trips():
    with conn() as c:
        return c.execute('SELECT * FROM trips ORDER BY started DESC LIMIT 200').fetchall()


@app.get('/api/dashboard/{vin}')
async def dashboard(vin: str):
    data = await vehicle_data(vin)
    charge = data.get('charge_state', {})
    drive = data.get('drive_state', {})
    state = data.get('vehicle_state', {})
    s = settings()
    latest = telemetry_latest(vin)
    nav = latest['payload'] if latest else {}
    return {
        'vin': vin,
        'battery': charge.get('battery_level'),
        'range_km': charge.get('battery_range'),
        'odometer_km': state.get('odometer'),
        'speed_kmh': drive.get('speed'),
        'shift_state': drive.get('shift_state'),
        'latitude': drive.get('latitude'),
        'longitude': drive.get('longitude'),
        'electricity_eur_kwh': s['electricity'],
        'diesel_eur_l': s['diesel'],
        'diesel_km_l': s['diesel_km_l'],
        'navigation': nav,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }


# Serve the compiled PWA from the same origin.
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
if os.path.isdir(STATIC_DIR):
    app.mount('/assets', StaticFiles(directory=os.path.join(STATIC_DIR, 'assets')), name='assets')


@app.get('/{path:path}')
def spa(path: str):
    if path.startswith(('api/', 'auth/', 'health')):
        raise HTTPException(404)
    index = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index):
        return FileResponse(index)
    return {'message': 'TeslaDrive backend attivo', 'frontend': 'non compilato'}
