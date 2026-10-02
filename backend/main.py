import os
import secrets
import requests
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime

# Configurazione Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tesladrive.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserToken(Base):
    __tablename__ = "user_tokens"
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String)
    refresh_token = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurazione Tesla OAuth
TESLA_CLIENT_ID = os.getenv("TESLA_CLIENT_ID")
TESLA_CLIENT_SECRET = os.getenv("TESLA_CLIENT_SECRET")
TESLA_REDIRECT_URI = os.getenv("TESLA_REDIRECT_URI")
TESLA_AUDIENCE = os.getenv("TESLA_AUDIENCE", "https://fleet-api.prd.eu.vn.cloud.tesla.com")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_token(db: Session = Depends(get_db)):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token

# ==============================================================================
# ROTTA PER SERVIRE LA CHIAVE PUBBLICA TESLA
# ==============================================================================
@app.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
def serve_tesla_public_key():
    possible_paths = [
        "infra/.well-known/appspecific/com.tesla.3p.public-key.pem",
        "static/.well-known/appspecific/com.tesla.3p.public-key.pem",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Public key file not found")

# ==============================================================================
# ROTTE AUTENTICAZIONE
# ==============================================================================
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/auth/tesla/start")
def tesla_start_login():
    state = secrets.token_urlsafe(16)
    auth_url = (
        f"https://auth.tesla.com/oauth2/v3/authorize?"
        f"response_type=code&"
        f"client_id={TESLA_CLIENT_ID}&"
        f"redirect_uri={TESLA_REDIRECT_URI}&"
        f"scope=openid%20offline_access%20vehicle_device_data%20vehicle_cmds%20vehicle_charging_cmds&"
        f"state={state}"
    )
    return RedirectResponse(url=auth_url)

@app.get("/auth/tesla/callback")
def tesla_callback(code: str, db: Session = Depends(get_db)):
    token_url = "https://auth.tesla.com/oauth2/v3/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": TESLA_CLIENT_ID,
        "client_secret": TESLA_CLIENT_SECRET,
        "code": code,
        "redirect_uri": TESLA_REDIRECT_URI,
    }
    
    response = requests.post(token_url, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token from Tesla: {response.text}")
    
    data = response.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    
    user_token = UserToken(access_token=access_token, refresh_token=refresh_token)
    db.add(user_token)
    db.commit()
    
    return RedirectResponse(url="/")

@app.post("/auth/logout")
def logout(db: Session = Depends(get_db)):
    db.query(UserToken).delete()
    db.commit()
    return {"status": "logged_out"}

@app.get("/api/status")
def api_status(db: Session = Depends(get_db)):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    return {"authenticated": token is not None}

# ==============================================================================
# ROTTE API TESLA (Veicoli, Dashboard, Impostazioni, Viaggi)
# ==============================================================================
@app.get("/api/vehicles")
def get_vehicles(token: UserToken = Depends(get_current_token)):
    headers = {"Authorization": f"Bearer {token.access_token}"}
    response = requests.get(f"{TESLA_AUDIENCE}/api/1/vehicles", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()

@app.get("/api/dashboard/{vin}")
def get_dashboard(vin: str, token: UserToken = Depends(get_current_token)):
    headers = {"Authorization": f"Bearer {token.access_token}"}
    response = requests.get(f"{TESLA_AUDIENCE}/api/1/vehicles/{vin}/vehicle_data", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    data = response.json().get("response", {})
    vehicle_state = data.get("vehicle_state", {})
    drive_state = data.get("drive_state", {})
    charge_state = data.get("charge_state", {})
    
    return {
        "battery": charge_state.get("battery_level"),
        "range_km": charge_state.get("battery_range", 0) * 1.60934 if charge_state.get("battery_range") else None,
        "odometer_km": vehicle_state.get("odometer", 0) * 1.60934 if vehicle_state.get("odometer") else None,
        "speed_kmh": drive_state.get("speed", 0) * 1.60934 if drive_state.get("speed") else 0,
        "shift_state": drive_state.get("shift_state", "P"),
        "navigation": drive_state.get("active_route_destination"),
        "updated_at": datetime.utcnow().isoformat()
    }

@app.get("/api/settings")
def get_settings(token: UserToken = Depends(get_current_token)):
    diesel_price = 1.76  # Valore di fallback predefinito
    electricity_price = 0.21
    
    headers = {"Authorization": f"Bearer {token.access_token}"}
    try:
        # 1. Recupera la posizione della Tesla
        res = requests.get(f"{TESLA_AUDIENCE}/api/1/vehicles", headers=headers, timeout=5)
        if res.status_code == 200:
            vehicles = res.json().get("response", [])
            if vehicles:
                vin = vehicles[0].get("vin")
                data_res = requests.get(f"{TESLA_AUDIENCE}/api/1/vehicles/{vin}/vehicle_data", headers=headers, timeout=5)
                if data_res.status_code == 200:
                    drive_state = data_res.json().get("response", {}).get("drive_state", {})
                    lat = drive_state.get("latitude")
                    lon = drive_state.get("longitude")
                    
                    if lat and lon:
                        # 2. Interroga l'API pubblica basata sugli Open Data del MIMIT per trovare i distributori vicini
                        api_url = f"https://prezzi-carburante.onrender.com/api/search?latitude={lat}&longitude={lon}&distance=10&fuel=diesel&results=1"
                        fuel_res = requests.get(api_url, timeout=5)
                        if fuel_res.status_code == 200:
                            stations = fuel_res.json()
                            if stations and isinstance(stations, list):
                                diesel_price = float(stations[0].get("prezzo", diesel_price))
    except Exception as e:
        print(f"Errore recupero prezzi dinamici: {e}")

    return {
        "electricity": electricity_price,
        "diesel": round(diesel_price, 2),
        "diesel_km_l": 16.0
    }

@app.post("/api/settings")
def save_settings(settings: dict):
    return {"status": "saved", "settings": settings}

@app.get("/api/trips")
def get_trips():
    return []

# Servizio dei file statici del frontend React (deve rimanere in fondo)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")