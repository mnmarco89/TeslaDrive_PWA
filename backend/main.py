import os
import secrets
import requests
import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime

# ============================================================
# TESLA FLEET API
# ============================================================
from tesla_fleet_api import TeslaFleetApi

# ============================================================
# DATABASE
# ============================================================

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

class UserSettingsDB(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    electricity = Column(String, default="0.24")
    diesel = Column(String, default="2.19")
    diesel_km_l = Column(String, default="15.5")
    voltage_protection = Column(Integer, default=1)

Base.metadata.create_all(bind=engine)

# ============================================================
# FASTAPI
# ============================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# TESLA CONFIGURATION
# ============================================================

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

# ============================================================
# TESLA VEHICLE COMMAND PROTOCOL (Firma Crittografica)
# ============================================================

async def send_signed_tesla_command(vin: str, token: str, endpoint: str, payload: dict):
    """
    Implementazione reale del Vehicle Command Protocol.
    Utilizza tesla_fleet_api passando il file della chiave privata.
    """
    private_key_pem = os.getenv("TESLA_PRIVATE_KEY")
    
    if not private_key_pem:
        raise Exception("TESLA_PRIVATE_KEY non configurata sul server. I comandi di ricarica falliranno.")

    # Salviamo temporaneamente la chiave in un file, come richiesto dalla libreria
    key_path = "/tmp/tesla_private_key.pem"
    with open(key_path, "w") as f:
        f.write(private_key_pem)

    async with aiohttp.ClientSession() as session:
        # Inizializza il client API di Tesla corretto
        api = TeslaFleetApi(
            access_token=token,
            session=session,
            region="eu"
        )
        
        # Carica la chiave privata crittografica dal file
        await api.get_private_key(key_path)

        print(f"Invio comando firmato VCP '{endpoint}' in corso...")
        
        try:
            if endpoint == "set_charging_amps":
                # CORREZIONE: Utilizzo di api.vehicles (al plurale)
                response = await api.vehicles.set_charging_amps(
                    vin, 
                    charging_amps=payload.get("charging_amps")
                )
                return response
        except Exception as e:
            print(f"Errore VCP Tesla: {str(e)}")
            raise e
        finally:
            # Pulizia opzionale della chiave temporanea per sicurezza
            if os.path.exists(key_path):
                os.remove(key_path)
# ============================================================
# SMART VOLTAGE GOVERNOR
# ============================================================

def check_and_protect_voltage(vin: str, token: UserToken, charge_state: dict, db: Session):
    st = db.query(UserSettingsDB).first()
    if not st:
        st = UserSettingsDB()
        db.add(st)
        db.commit()

    if st.voltage_protection == 0:
        return

    voltage = charge_state.get("charger_voltage")
    current_amps = charge_state.get("charge_amps")
    charging_state = charge_state.get("charging_state")

    if charging_state == "Charging" and voltage and current_amps:
        # Tensione bassa
        if voltage <= 208 and current_amps > 6:
            new_amps = max(6, current_amps - 2)
            try:
                asyncio.run(send_signed_tesla_command(
                    vin,
                    token.access_token,
                    "set_charging_amps",
                    {"charging_amps": new_amps}
                ))
            except Exception as e:
                print("Errore invio comando riduzione ampere:", e)

        # Tensione alta
        elif voltage >= 218 and current_amps < 32:
            new_amps = min(32, current_amps + 1)
            try:
                asyncio.run(send_signed_tesla_command(
                    vin,
                    token.access_token,
                    "set_charging_amps",
                    {"charging_amps": new_amps}
                ))
            except Exception as e:
                print("Errore invio comando aumento ampere:", e)

# ============================================================
# TESLA PUBLIC KEY
# ============================================================

@app.get("/.well-known/appspecific/com.tesla.3p.public-key.pem")
def serve_tesla_public_key():
    possible_paths = [
        "static/.well-known/appspecific/com.tesla.3p.public-key.pem"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Public key file not found")

# ============================================================
# HEALTH CHECK & OAUTH
# ============================================================

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/auth/tesla/start")
def tesla_start_login():
    state = secrets.token_urlsafe(16)
    scopes = "openid offline_access user_data vehicle_device_data vehicle_cmds vehicle_charging_cmds"
    auth_url = (
        f"https://auth.tesla.com/oauth2/v3/authorize?"
        f"response_type=code&"
        f"client_id={TESLA_CLIENT_ID}&"
        f"redirect_uri={TESLA_REDIRECT_URI}&"
        f"scope={requests.utils.quote(scopes)}&"
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
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {response.text}")
    
    data = response.json()
    user_token = UserToken(
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token")
    )
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

# ============================================================
# API VEICOLI E DASHBOARD
# ============================================================

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
        "range_km": (charge_state.get("battery_range", 0) * 1.60934 if charge_state.get("battery_range") else None),
        "odometer_km": (vehicle_state.get("odometer", 0) * 1.60934 if vehicle_state.get("odometer") else None),
        "speed_kmh": (drive_state.get("speed", 0) * 1.60934 if drive_state.get("speed") else 0),
        "shift_state": drive_state.get("shift_state", "P"),
        "navigation": drive_state.get("active_route_destination"),
        "updated_at": datetime.utcnow().isoformat()
    }

# ============================================================
# IMPOSTAZIONI
# ============================================================

@app.get("/api/settings")
def get_settings(token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    st = db.query(UserSettingsDB).first()
    if not st:
        st = UserSettingsDB()
        db.add(st)
        db.commit()

    diesel_price = 2.19
    electricity_price = float(st.electricity)
    headers = {"Authorization": f"Bearer {token.access_token}"}
    
    try:
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
                        api_url = f"https://prezzi-carburante.onrender.com/api/distributori?latitude={lat}&longitude={lon}&distance=10&fuel=gasolio&results=1"
                        fuel_res = requests.get(api_url, timeout=5)
                        if fuel_res.status_code == 200:
                            stations = fuel_res.json()
                            if stations and isinstance(stations, list) and len(stations) > 0:
                                live_price = stations[0].get("prezzo")
                                if live_price:
                                    diesel_price = float(live_price)
    except Exception as e:
        print("Errore aggiornamento GPS prezzi:", e)

    return {
        "electricity": electricity_price,
        "diesel": round(diesel_price, 2),
        "diesel_km_l": float(st.diesel_km_l),
        "voltage_protection": st.voltage_protection
    }

@app.post("/api/settings")
def save_settings(payload: dict, db: Session = Depends(get_db)):
    st = db.query(UserSettingsDB).first()
    if not st:
        st = UserSettingsDB()
        db.add(st)
    st.electricity = str(payload.get("electricity", st.electricity))
    st.diesel = str(payload.get("diesel", st.diesel))
    st.diesel_km_l = str(payload.get("diesel_km_l", st.diesel_km_l))
    st.voltage_protection = int(payload.get("voltage_protection", st.voltage_protection))
    db.commit()
    return {"status": "saved"}

@app.get("/api/trips")
def get_trips():
    return []

# ============================================================
# STATO RICARICA E COMANDI
# ============================================================

@app.get("/api/charging/{vin}")
def get_charging_status(vin: str, token: UserToken = Depends(get_current_token), db: Session = Depends(get_db)):
    headers = {"Authorization": f"Bearer {token.access_token}"}
    response = requests.get(f"{TESLA_AUDIENCE}/api/1/vehicles/{vin}/vehicle_data", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    charge_state = response.json().get("response", {}).get("charge_state", {})
    
    try:
        check_and_protect_voltage(vin, token, charge_state, db)
    except Exception as e:
        print("Errore governor voltaggio:", e)

    return {
        "charging_state": charge_state.get("charging_state"),
        "charge_amps": charge_state.get("charge_amps"),
        "charge_current_request": charge_state.get("charge_current_request"),
        "charger_voltage": charge_state.get("charger_voltage"),
        "charger_actual_current": charge_state.get("charger_actual_current"),
        "charger_power": charge_state.get("charger_power"),
    }

@app.post("/api/vehicles/{vin}/set_amps")
async def set_charging_amps(vin: str, payload: dict, token: UserToken = Depends(get_current_token)):
    amps = payload.get("amps")
    if amps is None:
        raise HTTPException(status_code=400, detail="Valore di amperaggio non specificato")

    try:
        amps = int(amps)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Amperaggio non valido")

    if amps < 5 or amps > 32:
        raise HTTPException(status_code=400, detail="L'amperaggio deve essere compreso tra 5 e 32 A")

    try:
        response = await send_signed_tesla_command(
            vin,
            token.access_token,
            "set_charging_amps",
            {"charging_amps": amps}
        )
        return {"status": "success", "charging_amps": amps, "tesla_response": response}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================
# STATIC FRONTEND
# ============================================================

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")