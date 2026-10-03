import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Trip, TripPoint, TripContext, TrackingVehicle, BatteryObservation
from app.services import trip_context_service as context
from app.services.battery_service import recover_missing_energy
from app.services.trip_service import serialize


class ContextTests(unittest.TestCase):
    def point(self,offset=0,lat=41.0,lon=12.0):
        return SimpleNamespace(latitude=lat,longitude=lon,recorded_at=datetime(2026,10,3,10)+timedelta(seconds=offset))

    def response(self,payload):
        r=Mock();r.json.return_value=payload;return r

    def test_weather_uses_trip_date_and_exact_hour(self):
        sample=context.route_samples([self.point()])[0]
        payload={'hourly':{'time':['2026-10-03T10:00'], 'temperature_2m':[0], 'precipitation':[0], 'wind_speed_10m':[12], 'wind_direction_10m':[180], 'weather_code':[3]}}
        with patch.object(context.requests,'get',return_value=self.response(payload)) as get:
            data=context.weather_for(sample,datetime(2026,10,3,12))
        self.assertEqual(data['temperature_2m'],0)
        self.assertEqual(data['at'],'2026-10-03T10:00Z')
        self.assertEqual(get.call_args.kwargs['params']['start_date'],'2026-10-03')
        self.assertIn('api.open-meteo.com/v1/forecast',get.call_args.args[0])
        with patch.object(context.requests,'get',return_value=self.response(payload)) as get:
            context.weather_for(sample,datetime(2026,10,20))
        self.assertIn('archive-api',get.call_args.args[0])

    def test_missing_hour_is_not_substituted_with_today(self):
        with patch.object(context.requests,'get',return_value=self.response({'hourly':{'time':['2026-10-03T09:00']}})):
            with self.assertRaises(ValueError):
                context.weather_for(context.route_samples([self.point()])[0])

    def test_sampling_never_exceeds_service_limit(self):
        result=context.route_samples([self.point(i*15,lon=12+i*.00001) for i in range(1000)])
        self.assertEqual(len(result),100)
        self.assertEqual(result[0]['at'],self.point().recorded_at)
        self.assertEqual(result[-1]['at'],self.point(999*15).recorded_at)

    def test_elevation_does_not_join_gps_gaps(self):
        points=[self.point(0),self.point(15,lon=12.001),self.point(30,lat=None),self.point(45,lon=12.1),self.point(60,lon=12.101)]
        samples=context.route_samples(points)
        with patch.object(context.requests,'get',return_value=self.response({'elevation':[10,20,100,90]})):
            result=context.elevation_for(samples)
        self.assertEqual(result['ascent_m'],10)
        self.assertEqual(result['descent_m'],10)
        self.assertTrue(result['partial'])
        self.assertLess(result['profile'][-1]['distance_km'],1)

    def test_provider_failures_are_independent(self):
        samples=context.route_samples([self.point()])
        with patch.object(context,'weather_for',side_effect=RuntimeError('network')),patch.object(context,'elevation_for',return_value={'profile':[]}):
            result=context.enrich(samples)
        self.assertEqual(result['status'],'partial')
        self.assertIsNone(result['weather'])
        self.assertIn('weather',result['errors'])
        self.assertIsNotNone(result['elevation'])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db=sessionmaker(bind=self.engine)()
        self.db.add(TrackingVehicle(vin='A'))
        self.db.commit()

    def tearDown(self):
        self.db.close();self.engine.dispose()

    def trip(self,vin='A',energy=None,battery=98,tariff=.24):
        at=datetime(2026,10,3,10)
        t=Trip(vin=vin,started_at=at,ended_at=at+timedelta(minutes=7),last_sample_at=at+timedelta(minutes=7),status='completed',
            start_battery=battery,end_battery=97,distance_km=2.8,energy_kwh=energy,tariff=tariff)
        self.db.add(t);self.db.commit();return t

    def test_missing_capacity_is_explained_not_zero(self):
        t=self.trip()
        self.assertEqual(recover_missing_energy(self.db,'A'),0)
        self.assertIsNone(t.energy_kwh)
        self.assertIn('calibrata',serialize(t)['energy_missing_reason'])

    def test_later_calibration_recovers_energy_preserving_tariff_and_distance(self):
        t=self.trip()
        known=self.trip(energy=.7)
        missing=self.trip(battery=None)
        other=self.trip(vin='B')
        self.db.add(BatteryObservation(vin='A',recorded_at=datetime(2026,10,4),capacity_kwh=60,soc_delta=20))
        self.db.commit()
        self.assertEqual(recover_missing_energy(self.db,'A'),1)
        self.assertAlmostEqual(t.energy_kwh,.6)
        self.assertAlmostEqual(serialize(t)['energy_cost'],.144)
        self.assertEqual(t.distance_km,2.8)
        self.assertEqual(t.capacity_source,'charging_estimate_retrospective')
        self.assertEqual(known.energy_kwh,.7)
        self.assertIsNone(missing.energy_kwh)
        self.assertIsNone(other.energy_kwh)
        self.db.add(BatteryObservation(vin='A',recorded_at=datetime(2026,10,5),capacity_kwh=70,soc_delta=20));self.db.commit()
        self.assertEqual(recover_missing_energy(self.db,'A'),0)
        self.assertEqual(t.capacity_kwh,60)

    def test_cached_context_and_no_gps_make_no_requests(self):
        t=self.trip()
        self.db.add(TripContext(trip_id=t.id,updated_at=datetime(2026,10,3),payload=json.dumps({'status':'ready','weather':{'temperature_2m':22}})))
        self.db.commit()
        with patch.object(context.threading,'Thread') as thread:
            self.assertEqual(context.context(self.db,t)['status'],'ready')
            other=self.trip()
            self.assertEqual(context.context(self.db,other)['status'],'no_gps')
            thread.assert_not_called()


    def test_manual_retry_bypasses_long_cache_but_keeps_valid_weather(self):
        t=self.trip()
        self.db.add(TripPoint(trip_id=t.id,recorded_at=t.started_at,latitude=41,longitude=12))
        self.db.add(TripContext(trip_id=t.id,updated_at=datetime.utcnow()-timedelta(minutes=2),payload=json.dumps({'status':'partial','weather':{'temperature_2m':22},'errors':{'elevation':'Timeout'}})))
        self.db.commit()
        with patch.object(context.threading,'Thread') as thread:
            self.assertEqual(context.context(self.db,t)['status'],'partial')
            thread.assert_not_called()
            self.assertEqual(context.context(self.db,t,retry=True)['status'],'pending')
            thread.return_value.start.assert_called_once()
        context._pending.discard(t.id)



class ProviderRetryTests(unittest.TestCase):
    def test_timeout_retries_once_then_returns_data(self):
        import requests
        response=Mock();response.json.return_value={'elevation':[21]}
        with patch.object(context.requests,'get',side_effect=[requests.Timeout(),response]) as get:
            self.assertEqual(context.provider_json('https://api.open-meteo.com/v1/elevation',{}),{'elevation':[21]})
        self.assertEqual(get.call_count,2)

    def test_rate_limit_is_not_retried_immediately(self):
        import requests
        response=Mock(status_code=429)
        response.raise_for_status.side_effect=requests.HTTPError(response=response)
        with patch.object(context.requests,'get',return_value=response) as get:
            with self.assertRaises(requests.HTTPError) as caught:
                context.provider_json('https://api.open-meteo.com/v1/elevation',{})
        self.assertEqual(get.call_count,1)
        self.assertIn('HTTP 429',context.error_message(caught.exception))

    def test_two_failures_remain_timeout_error(self):
        import requests
        with patch.object(context.requests,'get',side_effect=requests.Timeout()) as get:
            with self.assertRaises(requests.Timeout) as caught:
                context.provider_json('https://api.open-meteo.com/v1/elevation',{})
        self.assertEqual(get.call_count,2)
        self.assertIn('timeout',context.error_message(caught.exception))

    def test_invalid_date_reason_is_visible_without_request_url(self):
        import requests
        response=Mock(status_code=400)
        response.json.return_value={'reason':'start_date fuori intervallo'}
        message=context.error_message(requests.HTTPError('URL with private coordinates',response=response))
        self.assertIn('start_date fuori intervallo',message)
        self.assertNotIn('private coordinates',message)
