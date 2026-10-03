"""Explicit historical assumption plus future trip savings, without double counting."""
from datetime import datetime
from ..models import SavingsBaseline, Trip
from .cost_service import summarize
from .trip_service import iso

BASELINE_CUTOFF = datetime(2026,10,3,18,20,50)  # UTC: user's odometer reference


def get_savings(db, vin):
    baseline = db.get(SavingsBaseline, vin)
    # The user's supplied odometer belongs to one vehicle, not every vehicle in the account.
    if baseline is None and db.query(SavingsBaseline).first() is None:
        baseline = SavingsBaseline(vin=vin, cutoff_at=BASELINE_CUTOFF, distance_km=32517,
            electricity_price=.24, diesel_price=2.189, electric_kwh_100km=16, diesel_km_l=15.5)
        db.add(baseline)
        db.commit()
    query = db.query(Trip).filter(Trip.vin == vin, Trip.status != 'active')
    if baseline:
        query = query.filter(Trip.started_at >= baseline.cutoff_at)
    trips = query.all()
    result = summarize(db, trips)
    result['missing_energy_trips'] = sum(t.energy_kwh is None for t in trips)
    result['new_saving'] = result['saving']
    result['historical'] = None
    if baseline:
        energy = baseline.distance_km*baseline.electric_kwh_100km/100
        electricity = energy*baseline.electricity_price
        diesel = baseline.distance_km/baseline.diesel_km_l*baseline.diesel_price
        initial = diesel-electricity
        result['historical'] = dict(distance_km=baseline.distance_km, cutoff_at=iso(baseline.cutoff_at),
            electricity_price=baseline.electricity_price, diesel_price=baseline.diesel_price,
            electric_kwh_100km=baseline.electric_kwh_100km, diesel_km_l=baseline.diesel_km_l,
            energy_kwh=energy, electricity_cost=electricity, diesel_cost=diesel, saving=initial)
        result['saving'] = initial+(result['saving'] or 0)
        result['comparable_electricity_cost'] = electricity+(result['comparable_electricity_cost'] or 0)
        result['comparable_diesel_cost'] = diesel+(result['comparable_diesel_cost'] or 0)
        result['comparable_distance_km'] += baseline.distance_km
    return result
