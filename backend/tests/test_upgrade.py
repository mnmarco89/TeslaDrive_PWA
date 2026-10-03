import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Trip, TripPoint, TrackingVehicle, BatteryObservation
from app.schema import initialize_database
from app.services import battery_service as battery
from app.services import trip_collector as collector
from app.routers.auth import tesla_start_login
from urllib.parse import parse_qs, urlparse


class Clock(datetime):
    current = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(TrackingVehicle(vin='A'))
        self.db.commit()
        self.base = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
        self.clock = patch.object(battery, 'datetime', Clock)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.db.close()

    def charge(self, seconds, soc, energy, state='Charging', nominal=None):
        Clock.current = self.base + timedelta(seconds=seconds)
        battery.record_charging_sample(self.db, 'A', {'charge_state': dict(timestamp=Clock.current.timestamp()*1000,
            battery_level=soc, charge_energy_added=energy, charging_state=state, nominal_full_pack_energy=nominal)})
        self.db.commit()

    def test_estimate_automatic_after_twenty_percent_charge(self):
        self.charge(0, 40, 1)
        self.charge(60, 50, 7)
        self.charge(120, 60, 13, state='Complete')
        info = battery.battery_info(self.db, 'A')
        self.assertEqual(info['effective_capacity_kwh'], 60)
        self.assertEqual(info['capacity_source'], 'charging_estimate')
        self.assertEqual(info['calibration_sessions'], 1)

    def test_short_or_gapped_charge_not_estimated(self):
        self.charge(0, 40, 1)
        self.charge(60, 50, 7, state='Complete')
        self.assertIsNone(battery.battery_info(self.db, 'A')['effective_capacity_kwh'])
        self.charge(120, 40, 1)
        self.charge(500, 60, 13, state='Complete')
        self.assertEqual(self.db.query(BatteryObservation).count(), 0)

    def test_manual_override_and_nominal_not_assumed_usable(self):
        self.charge(0, 40, 1, nominal=79)
        self.assertEqual(battery.battery_info(self.db, 'A')['nominal_capacity_kwh'], 79)
        self.assertIsNone(battery.battery_info(self.db, 'A')['effective_capacity_kwh'])
        self.db.get(TrackingVehicle, 'A').capacity_kwh = 73
        self.db.commit()
        self.assertEqual(battery.battery_info(self.db, 'A')['effective_capacity_kwh'], 73)

    def test_reset_counter_finalizes_previous_session(self):
        self.charge(0, 40, 1)
        self.charge(60, 60, 13)
        self.charge(120, 60, 0, state='Disconnected')
        self.assertEqual(battery.battery_info(self.db, 'A')['automatic_capacity_kwh'], 60)

    def test_legacy_trips_schema_preserved_and_new_insert_works(self):
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE trips (id INTEGER PRIMARY KEY, started DATETIME NOT NULL, start_lat FLOAT NOT NULL)'))
            conn.execute(text("INSERT INTO trips VALUES (1, '2026-10-01', 41.9)"))
        initialize_database(self.engine)
        initialize_database(self.engine)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT COUNT(*) FROM trips')).scalar(), 1)
            self.assertEqual({c['name'] for c in inspect(conn).get_columns('trips')}, {'id', 'started', 'start_lat'})
        self.db.add(Trip(vin='A', started_at=self.base, last_sample_at=self.base))
        self.db.commit()
        self.assertEqual(self.db.query(Trip).count(), 1)

    def test_compatible_trips_and_points_imported_once(self):
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE trips AS SELECT * FROM telemetry_trips WHERE 0'))
            conn.execute(text('CREATE TABLE trip_points AS SELECT * FROM telemetry_trip_points WHERE 0'))
            conn.execute(text("INSERT INTO trips (id,vin,started_at,last_sample_at,status,partial) VALUES (7,'A','2026-10-01 10:00:00','2026-10-01 10:00:00','completed',0)"))
            conn.execute(text("INSERT INTO trip_points(id,trip_id,recorded_at,latitude,longitude) VALUES (9,7,'2026-10-01 10:00:00',41.9,12.5)"))
        initialize_database(self.engine)
        initialize_database(self.engine)
        self.assertEqual(self.db.query(Trip).one().id, 7)
        self.assertEqual(self.db.query(TripPoint).one().trip_id, 7)

    def test_missing_gps_scope_falls_back_to_dashboard_data(self):
        collector._cache.clear()
        collector._backoff.clear()
        denied = Mock(status_code=403)
        denied.json.return_value = {'error': 'Unauthorized missing scopes'}
        ok = Mock(status_code=200)
        ok.json.return_value = {'response': {}}
        with patch.object(collector, '_request', side_effect=[denied, ok]) as request:
            result = collector.fetch_sample(self.db, 'A')
            self.assertTrue(result['_location_unavailable'])
            self.assertNotIn('location_data', request.call_args.kwargs['params']['endpoints'])
        collector._cache.clear()

    def test_oauth_prompts_for_missing_permissions(self):
        query = parse_qs(urlparse(tesla_start_login().headers['location']).query)
        self.assertEqual(query['prompt_missing_scopes'], ['true'])
        self.assertEqual(query['require_requested_scopes'], ['true'])
        self.assertIn('vehicle_location', query['scope'][0].split())
