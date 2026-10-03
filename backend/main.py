import os
from contextlib import asynccontextmanager
from app.services.trip_collector import TripCollector

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.schema import initialize_database
from app.routers import auth, charging, settings, system, vehicles, trips

initialize_database(engine)

@asynccontextmanager
async def lifespan(app):
    collector = TripCollector()
    collector.start()
    try:
        yield
    finally:
        collector.stop()


app = FastAPI(title="Shmersla / TeslaDrive API", lifespan=lifespan)

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
app.include_router(trips.router)

# Il frontend compilato viene montato per ultimo per non intercettare /api e /auth.
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
