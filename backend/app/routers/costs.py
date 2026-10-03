from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..dependencies import get_current_token
from ..models import Trip, TrackingVehicle, CostRate, FuelPriceState
from sqlalchemy import or_
from ..services.trip_service import capture_lock, expire_trip, iso
from ..services.cost_service import initial_rate, summarize, serialize_rate
from .trips import period_start

router = APIRouter(prefix="/api/costs", dependencies=[Depends(get_current_token)])


@router.get("/rates")
def rates(vin: str, offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    with capture_lock:
        initial_rate(db)
        db.commit()
    query = db.query(CostRate).filter(or_(CostRate.vin == vin, CostRate.vin.is_(None))).order_by(CostRate.effective_from.desc(), CostRate.id.desc())
    return dict(items=[serialize_rate(r) for r in query.offset(offset).limit(50).all()], total=query.count())


@router.get("/summary/{vin}")
def summary(vin: str, period: str = Query("all", pattern="^(today|week|month|all)$"), db: Session = Depends(get_db)):
    if not db.get(TrackingVehicle, vin):
        raise HTTPException(404, "Veicolo non disponibile")
    with capture_lock:
        initial_rate(db)
        expire_trip(db, vin)
        db.commit()
    query = db.query(Trip).filter(Trip.vin == vin, Trip.status != "active")
    if period != "all":
        query = query.filter(Trip.started_at >= period_start(period))
    result = summarize(db, query.all())
    state = db.get(FuelPriceState, vin)
    result["fuel_price"] = dict(diesel=state.diesel if state else None,
        updated_at=iso(state.last_success_at) if state else None,
        error=state.error if state else None,
        station=state.station if state else None, city=state.city if state else None,
        dataset_date=state.dataset_date if state else None, reported_at=state.reported_at if state else None,
        source="MIMIT Osservaprezzi Carburanti",
        status="Prezzo diesel rilevato automaticamente vicino all’auto" if state and state.diesel else "In attesa di posizione GPS e prezzo diesel")
    return result
