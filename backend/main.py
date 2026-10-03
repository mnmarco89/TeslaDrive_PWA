import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import auth, charging, settings, system, vehicles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shmersla / TeslaDrive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(charging.router)
app.include_router(settings.router)

# Il frontend compilato viene montato per ultimo per non intercettare /api e /auth.
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
