import unittest
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.dependencies import get_current_token
from app.models import TrackingVehicle, Trip, TripCostSnapshot, SavingsBaseline
from app.services.savings_service import get_savings, BASELINE_CUTOFF
from app.routers.costs import router

class SavingsTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
  Base.metadata.create_all(self.engine);self.db=sessionmaker(bind=self.engine)()
  self.db.add_all([TrackingVehicle(vin='A'),TrackingVehicle(vin='B')]);self.db.commit()
 def tearDown(self):
  self.db.close();self.engine.dispose()
 def trip(self,offset,energy=10,vin='A'):
  at=BASELINE_CUTOFF+timedelta(seconds=offset)
  t=Trip(vin=vin,started_at=at,ended_at=at+timedelta(seconds=60),last_sample_at=at+timedelta(seconds=60),status='completed',distance_km=100,energy_kwh=energy,tariff=.24)
  self.db.add(t);self.db.flush();self.db.add(TripCostSnapshot(trip_id=t.id,diesel=2.189,diesel_km_l=15.5));self.db.commit();return t
 def test_initial_estimate_formula_and_idempotent_seed(self):
  r=get_savings(self.db,'A')
  self.assertAlmostEqual(r['historical']['electricity_cost'],1248.6528)
  self.assertAlmostEqual(r['historical']['diesel_cost'],32517/15.5*2.189)
  self.assertAlmostEqual(r['saving'],3343.586748387097)
  get_savings(self.db,'A');self.assertEqual(self.db.query(SavingsBaseline).count(),1)
 def test_past_and_crossing_trips_not_double_counted(self):
  initial=get_savings(self.db,'A')['saving'];self.trip(-600);self.trip(-30)
  self.assertEqual(get_savings(self.db,'A')['saving'],initial)
 def test_only_future_comparable_trips_added(self):
  initial=get_savings(self.db,'A')['saving'];self.trip(60);self.trip(180,energy=None);self.trip(240,vin='B')
  r=get_savings(self.db,'A');self.assertAlmostEqual(r['saving'],initial+100/15.5*2.189-2.4)
  self.assertEqual(r['comparable_trips'],1);self.assertEqual(r['missing_energy_trips'],1)
 def test_baseline_not_copied_to_other_vehicle(self):
  get_savings(self.db,'A');r=get_savings(self.db,'B')
  self.assertIsNone(r['historical']);self.assertIsNone(r['saving'])
 def test_restart_preserves_modified_assumption(self):
  get_savings(self.db,'A');self.db.get(SavingsBaseline,'A').electric_kwh_100km=18;self.db.commit()
  self.db.close();self.db=sessionmaker(bind=self.engine)()
  self.assertEqual(get_savings(self.db,'A')['historical']['electric_kwh_100km'],18)
 def test_auth_validation_and_update_without_rewriting_trips(self):
  app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:self.db;client=TestClient(app)
  self.assertEqual(client.get('/api/costs/savings/A').status_code,401)
  app.dependency_overrides[get_current_token]=lambda:object()
  self.assertEqual(client.get('/api/costs/savings/A').status_code,200)
  t=self.trip(60)
  self.assertEqual(client.patch('/api/costs/savings/A/baseline',json={'electric_kwh_100km':0,'diesel_km_l':15.5}).status_code,422)
  r=client.patch('/api/costs/savings/A/baseline',json={'electric_kwh_100km':18,'diesel_km_l':15.5})
  self.assertEqual(r.status_code,200);self.assertEqual(r.json()['historical']['electric_kwh_100km'],18)
  self.assertEqual(self.db.get(Trip,t.id).tariff,.24)
