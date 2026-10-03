import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.dependencies import get_current_token
from app.models import ChargingSession, BatteryObservation, TrackingVehicle, Trip, TripAmbient, WeatherProviderState
from app.services import charging_history_service as charging, location_service as gps, trip_context_service as weather, trip_service
from app.routers import charging as charging_router, vehicles

class Clock(datetime):
    current = datetime(2026,10,3,20, tzinfo=timezone.utc)
    @classmethod
    def now(cls,tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.db=sessionmaker(bind=self.engine)()
        self.clock=patch.object(charging,'datetime',Clock);self.clock.start()
        Clock.current=datetime(2026,10,3,20,tzinfo=timezone.utc)
    def tearDown(self):
        self.clock.stop();self.db.close();self.engine.dispose()
    def sample(self,at,energy,soc=50,state='Charging',vin='A'):
        Clock.current=at
        charging.record_history(self.db,vin,{'charge_state':{'timestamp':at.timestamp()*1000,'charge_energy_added':energy,'battery_level':soc,'charging_state':state}})
        self.db.commit()
    def test_daily_totals_multiple_sessions_and_vehicle_isolation(self):
        at=Clock.current
        self.sample(at,0);self.sample(at+timedelta(seconds=60),1,52);self.sample(at+timedelta(seconds=120),2,54,'Complete')
        self.sample(at+timedelta(seconds=180),0);self.sample(at+timedelta(seconds=240),3,60,'Stopped')
        self.sample(at+timedelta(seconds=300),0,vin='B');self.sample(at+timedelta(seconds=360),99,vin='B')
        result=charging.history(self.db,'A')
        self.assertEqual(result['total_energy_kwh'],5);self.assertEqual(result['session_count'],2)
        self.assertFalse(result['days'][-1]['partial'])
    def test_duplicate_completed_sample_does_not_restart(self):
        at=Clock.current
        self.sample(at,0);self.sample(at+timedelta(seconds=60),2,state='Complete');self.sample(at,0)
        self.assertEqual(self.db.query(ChargingSession).count(),1)
        self.assertEqual(charging.history(self.db,'A')['total_energy_kwh'],2)
    def test_missing_interval_is_not_counted(self):
        at=Clock.current
        self.sample(at,4);self.sample(at+timedelta(seconds=60),5)
        self.sample(at+timedelta(seconds=500),20);self.sample(at+timedelta(seconds=560),21,state='Complete')
        result=charging.history(self.db,'A')
        self.assertEqual(result['total_energy_kwh'],2);self.assertTrue(result['days'][-1]['partial'])
        self.assertEqual(result['session_count'],2)
    def test_midnight_rome_splits_increment_without_doubling(self):
        at=datetime(2026,10,3,21,59,30,tzinfo=timezone.utc)
        self.sample(at,0);self.sample(at+timedelta(seconds=60),2,state='Complete')
        result=charging.history(self.db,'A')
        self.assertEqual([d['energy_kwh'] for d in result['days'][-2:]],[1,1])
        self.assertTrue(result['days'][-1]['midnight_estimate']);self.assertEqual(result['session_count'],1)
    def test_restart_retains_energy_and_stale_session_is_partial(self):
        at=Clock.current
        self.sample(at,0);self.sample(at+timedelta(seconds=60),2)
        self.db.close();self.db=sessionmaker(bind=self.engine)()
        Clock.current=at+timedelta(seconds=500)
        result=charging.history(self.db,'A')
        self.assertEqual(result['total_energy_kwh'],2);self.assertEqual(self.db.query(ChargingSession).one().status,'interrupted')
    def test_capacity_reference_does_not_overlap_subsequent_samples(self):
        at=Clock.current.replace(tzinfo=None)
        for i,value in enumerate([60,61,59]):self.db.add(BatteryObservation(vin='A',recorded_at=at+timedelta(seconds=i),capacity_kwh=value,soc_delta=20))
        self.db.commit();self.assertIsNone(charging.history(self.db,'A')['capacity_variation_percent'])
        for i in range(3):self.db.add(BatteryObservation(vin='A',recorded_at=at+timedelta(seconds=10+i),capacity_kwh=57,soc_delta=25))
        self.db.commit();result=charging.history(self.db,'A')
        self.assertEqual(result['capacity_baseline_kwh'],60);self.assertEqual(result['capacity_recent_kwh'],57);self.assertEqual(result['capacity_variation_percent'],-5)
    def test_authenticated_endpoints_and_range_validation(self):
        app=FastAPI();app.include_router(charging_router.router);app.include_router(vehicles.router)
        app.dependency_overrides[get_db]=lambda:self.db;client=TestClient(app)
        self.assertEqual(client.get('/api/charging/A/history').status_code,401)
        self.assertEqual(client.get('/api/vehicles/A/location').status_code,401)
        app.dependency_overrides[get_current_token]=lambda:object()
        self.assertEqual(client.get('/api/charging/A/history?days=366').status_code,422)
        with patch.object(vehicles,'fetch_sample') as fetch:
            self.assertFalse(client.get('/api/vehicles/A/location').json()['available']);fetch.assert_not_called()
    def test_location_retains_zero_coords_and_ignores_invalid_or_older(self):
        now=datetime.now(timezone.utc)
        gps.record_location(self.db,'A',{'drive_state':{'timestamp':now.timestamp()*1000,'latitude':0,'longitude':0}});self.db.commit()
        gps.record_location(self.db,'A',{'_location_unavailable':True})
        gps.record_location(self.db,'A',{'drive_state':{'timestamp':now.timestamp()*1000,'latitude':91,'longitude':12}})
        gps.record_location(self.db,'A',{'drive_state':{'timestamp':(now-timedelta(minutes=5)).timestamp()*1000,'latitude':41,'longitude':12}})
        self.db.commit();self.assertEqual(gps.location(self.db,'A')['latitude'],0);self.assertFalse(gps.location(self.db,'B')['available'])
    def test_provider_429_blocks_other_requests_and_manual_retry(self):
        import requests
        response=Mock(status_code=429,headers={'Retry-After':'3600'})
        response.raise_for_status.side_effect=requests.HTTPError(response=response)
        with patch.object(weather.requests,'get',return_value=response) as get:
            with self.assertRaises(requests.HTTPError):weather.provider_json('https://api.open-meteo.com/v1/forecast',{},db=self.db)
            with self.assertRaises(weather.ProviderLimited):weather.provider_json('https://api.open-meteo.com/v1/elevation',{},db=self.db)
            self.assertEqual(get.call_count,1)
        at=datetime.now(timezone.utc).replace(tzinfo=None)
        trip=Trip(vin='A',started_at=at,last_sample_at=at,status='completed');self.db.add(trip);self.db.commit()
        with patch.object(weather.threading,'Thread') as thread:
            result=weather.context(self.db,trip,retry=True)
            self.assertTrue(result['rate_limited']);self.assertGreater(result['retry_after_seconds'],3500);thread.assert_not_called()
    def test_provider_cache_serves_data_during_pause(self):
        response=Mock();response.json.return_value={'elevation':[21]}
        with patch.object(weather.requests,'get',return_value=response) as get:
            result=weather.provider_json('https://api.open-meteo.com/v1/elevation',{'latitude':41},db=self.db)
            self.db.add(WeatherProviderState(name='free',blocked_until=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(hours=1)));self.db.commit()
            self.assertEqual(weather.provider_json('https://api.open-meteo.com/v1/elevation',{'latitude':41},db=self.db),result)
            self.assertEqual(get.call_count,1)
    def test_temperature_fallback_does_not_invent_wind(self):
        samples=[{'at':datetime(2026,10,3),'latitude':41,'longitude':12}]
        ambient={'temperature_2m':0,'at':'2026-10-03T10:00:00Z','source':'Tesla'}
        with patch.object(weather,'weather_for',side_effect=weather.ProviderLimited('HTTP 429')),patch.object(weather,'elevation_for',side_effect=weather.ProviderLimited('HTTP 429')):
            result=weather.enrich(samples,ambient=ambient)
        self.assertEqual(result['status'],'partial');self.assertEqual(result['weather']['temperature_2m'],0)
        self.assertNotIn('wind_speed_10m',result['weather']);self.assertIn('weather',result['errors'])
    def test_trip_captures_concurrent_temperature(self):
        now=datetime.now(timezone.utc);self.db.add(TrackingVehicle(vin='A'));self.db.commit()
        data={'drive_state':{'timestamp':now.timestamp()*1000,'shift_state':'D','speed':5},'climate_state':{'timestamp':now.timestamp()*1000,'outside_temp':0}}
        trip_service.record_sample(self.db,'A',data)
        self.assertEqual(self.db.query(TripAmbient).one().temperature_c,0)
    def test_customer_key_uses_customer_endpoint(self):
        response=Mock();response.json.return_value={'elevation':[10]}
        with patch.dict('os.environ',{'OPEN_METEO_API_KEY':'private-key'}),patch.object(weather.requests,'get',return_value=response) as get:
            weather.provider_json('https://api.open-meteo.com/v1/elevation',{})
        self.assertEqual(get.call_args.args[0],'https://customer-api.open-meteo.com/v1/elevation')
        self.assertEqual(get.call_args.kwargs['params']['apikey'],'private-key')
