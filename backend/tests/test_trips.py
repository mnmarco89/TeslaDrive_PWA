import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ['DATABASE_URL'] = 'sqlite:///' + tempfile.mktemp(suffix='.db')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.dependencies import get_current_token
from app.models import TrackingVehicle, Trip, TripPoint, UserSettingsDB
from app.services import trip_service as service
from app.routers import trips


class Frozen(datetime):
    current = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


class TripTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add_all([TrackingVehicle(vin='A', capacity_kwh=60), TrackingVehicle(vin='B'), UserSettingsDB(electricity='0.25')])
        self.db.commit()
        self.clock = patch.object(service, 'datetime', Frozen)
        self.clock.start()
        self.base = datetime(2026, 10, 3, 8, tzinfo=timezone.utc)

    def tearDown(self):
        self.clock.stop()
        self.db.close()

    def sample(self, seconds, gear, speed=20, odo=100, battery=80, vin='A', gps=True):
        Frozen.current = self.base + timedelta(seconds=seconds)
        data = {'drive_state': {'timestamp': Frozen.current.timestamp()*1000, 'shift_state': gear, 'speed': speed},
                'vehicle_state': {'odometer': odo}, 'charge_state': {'battery_level': battery}}
        if gps:
            data['drive_state'].update(latitude=41.9, longitude=12.5+seconds/100000)
        service.record_sample(self.db, vin, data)

    def test_complete_drive_and_traffic_light(self):
        self.sample(0, 'P', speed=0)
        self.sample(15, 'D', battery=80)
        self.sample(45, 'D', speed=0, odo=102)
        self.assertEqual(self.db.query(Trip).one().status, 'active')
        self.sample(90, 'P', speed=0, odo=110, battery=75)
        trip = self.db.query(Trip).one()
        self.assertEqual(trip.status, 'completed')
        self.assertFalse(trip.partial)
        self.assertAlmostEqual(trip.distance_km, 10*1.609344)
        self.assertAlmostEqual(trip.energy_kwh, 3)
        self.assertAlmostEqual(service.serialize(trip)['energy_cost'], .75)

    def test_duplicate_and_out_of_order_are_ignored(self):
        self.sample(15, 'D')
        self.sample(15, 'D', odo=999)
        self.sample(0, 'P', speed=0)
        self.assertEqual(self.db.query(TripPoint).count(), 1)
        self.assertEqual(self.db.query(Trip).one().status, 'active')

    def test_gap_splits_and_marks_partial(self):
        self.sample(0, 'D')
        self.sample(300, 'D', odo=110)
        rows = self.db.query(Trip).order_by(Trip.id).all()
        self.assertEqual([t.status for t in rows], ['interrupted', 'active'])
        self.assertTrue(all(t.partial for t in rows))
        self.assertEqual(service.serialize(rows[0])['duration_minutes'], 0)

    def test_null_gear_requires_confirmation(self):
        self.sample(0, 'D')
        self.sample(15, None, speed=0)
        self.sample(60, None, speed=0)
        self.assertEqual(self.db.query(Trip).one().status, 'active')
        self.sample(75, None, speed=0)
        self.assertEqual(self.db.query(Trip).one().status, 'completed')

    def test_missing_capacity_does_not_invent_energy(self):
        self.sample(0, 'D', vin='B')
        self.sample(60, 'P', vin='B', speed=0, odo=102, battery=79)
        self.assertIsNone(self.db.query(Trip).one().energy_kwh)

    def test_missing_gps_still_records_odometer(self):
        self.sample(0, 'D', gps=False)
        self.sample(60, 'P', speed=0, gps=False, odo=102)
        self.assertGreater(self.db.query(Trip).one().distance_km, 3)
        self.assertTrue(all(p.latitude is None for p in self.db.query(TripPoint)))

    def test_gps_fallback_and_no_samples_not_zero(self):
        self.sample(0, 'D', odo=None)
        self.assertIsNone(self.db.query(Trip).one().distance_km)
        self.sample(60, 'P', speed=0, odo=None)
        trip = self.db.query(Trip).one()
        self.assertEqual(trip.distance_source, 'gps_estimate')
        self.assertGreater(trip.distance_km, 0)

    def test_capacity_is_snapshotted_and_regeneration_is_net_gain(self):
        self.sample(0, 'D')
        vehicle = self.db.get(TrackingVehicle, 'A')
        vehicle.capacity_kwh = 100
        self.db.commit()
        self.sample(60, 'P', speed=0, battery=81)
        self.assertEqual(self.db.query(Trip).one().capacity_kwh, 60)
        self.assertAlmostEqual(self.db.query(Trip).one().energy_kwh, -.6)

    def test_stale_unknown_timestamp_and_invalid_coordinates(self):
        Frozen.current = self.base
        self.assertIsNone(service.sample_from_data({'drive_state': {}}))
        self.assertIsNone(service.sample_from_data({'drive_state': {'timestamp': (self.base-timedelta(minutes=5)).timestamp()*1000}}))
        data = service.sample_from_data({'drive_state': {'timestamp': self.base.timestamp()*1000, 'latitude': 91, 'longitude': 12}})
        self.assertIsNone(data['latitude'])

    def test_disabled_recording(self):
        self.db.get(TrackingVehicle, 'A').enabled = False
        self.db.commit()
        self.sample(0, 'D')
        self.assertEqual(self.db.query(Trip).count(), 0)

    def test_router_auth_filters_validation_and_detail(self):
        app = FastAPI()
        app.include_router(trips.router)
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        self.assertEqual(client.get('/api/trips/A').status_code, 401)
        app.dependency_overrides[get_current_token] = lambda: object()
        self.sample(0, 'D')
        self.sample(60, 'P', speed=0, odo=102, battery=79)
        response = client.get('/api/trips/A?period=all').json()
        self.assertEqual(response['summary']['trips'], 1)
        trip_id = response['items'][0]['id']
        self.assertEqual(len(client.get(f'/api/trips/A/{trip_id}').json()['points']), 2)
        self.assertEqual(client.get(f'/api/trips/B/{trip_id}').status_code, 404)
        self.assertEqual(client.get('/api/trips/A?period=garbage').status_code, 422)
        self.assertEqual(client.put('/api/trips/A/settings', json={'enabled': True, 'capacity_kwh': 0}).status_code, 422)
        self.assertEqual(client.put('/api/trips/A/settings', json={'enabled': False, 'capacity_kwh': None}).status_code, 200)
        self.assertFalse(client.get('/api/trips/A/settings').json()['enabled'])

    def test_stop_setting_interrupts_active_drive(self):
        self.sample(0, 'D')
        trips.set_settings('A', trips.TrackingSettings(enabled=False, capacity_kwh=60), self.db)
        self.assertEqual(self.db.query(Trip).one().status, 'interrupted')

    def test_background_collection_without_dashboard(self):
        from app.services import trip_collector as collector
        from app.models import UserToken
        from unittest.mock import Mock
        self.db.add(UserToken(access_token='test-token'))
        self.db.commit()
        worker = collector.TripCollector()
        Frozen.current = self.base
        response = Mock(status_code=200)
        response.json.return_value = {'response': [{'vin': 'A', 'state': 'online'}]}
        data = {'drive_state': {'timestamp': self.base.timestamp()*1000, 'shift_state': 'D', 'speed': 20},
                'vehicle_state': {'odometer': 100}, 'charge_state': {'battery_level': 80}}
        def capture(db, vin):
            service.record_sample(db, vin, data)
            worker.stop_event.set()
            return data
        with patch.object(collector, 'SessionLocal', lambda: self.db), patch.object(collector, '_request', return_value=response), patch.object(collector, 'fetch_sample', side_effect=capture):
            worker.run()
        self.assertEqual(self.db.query(Trip).count(), 1)

    def test_rate_limit_backoff_is_shared_with_dashboard(self):
        from app.services import trip_collector as collector
        from unittest.mock import Mock
        response = Mock(status_code=429, headers={'Retry-After': '600'})
        collector._cache.clear()
        collector._backoff.clear()
        with patch.object(collector, '_request', return_value=response) as request:
            for _ in range(2):
                with self.assertRaises(ValueError):
                    collector.fetch_sample(self.db, 'A')
            self.assertEqual(request.call_count, 1)
        collector._backoff.clear()


if __name__ == '__main__':
    unittest.main()
