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
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://tesladrive.onrender.com")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# ROTTA PER SERVIRE LA CHIAVE PUBBLICA TESLA (Senza passare dalla SPA React)
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
# ROTTE APPLICAZIONE ORIGINALI
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

@app.get("/api/status")
def api_status(db: Session = Depends(get_db)):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    return {"authenticated": token is not None}

# Servizio dei file statici del frontend React (deve rimanere in fondo)
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")