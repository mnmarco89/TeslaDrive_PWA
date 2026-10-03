import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import Trip, TrackingVehicle, UserSettingsDB, CostRate, FuelPriceState
from app.services import cost_service as costs, fuel_price_service as fuel, trip_service
from app.routers import settings


class Clock(datetime):
    current = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


class CostsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([TrackingVehicle(vin='A'), TrackingVehicle(vin='B'), UserSettingsDB(electricity='0.2', diesel='9.99', diesel_km_l='20')])
        self.db.commit()
        self.base = datetime(2026, 10, 3, 10)
        self.clock = patch.object(trip_service, 'datetime', Clock)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.db.close()

    def trip(self, offset=0, energy=20, tariff=.2, km=100, vin='A'):
        t = Trip(vin=vin, started_at=self.base+timedelta(seconds=offset), ended_at=self.base+timedelta(seconds=offset+60),
                 last_sample_at=self.base+timedelta(seconds=offset+60), status='completed', distance_km=km, energy_kwh=energy, tariff=tariff)
        self.db.add(t)
        self.db.flush()
        costs.snapshot_trip_cost(self.db, t)
        self.db.commit()
        return t

    def price(self, price, offset=-10, vin='A'):
        costs.add_rate(self.db, .2, price, 20, at=self.base+timedelta(seconds=offset), source='gps_auto', vin=vin)
        self.db.commit()

    def test_price_changes_keep_previous_costs(self):
        self.price(2)
        first = self.trip()
        self.price(3, 100)
        second = self.trip(120, tariff=.3)
        self.db.query(UserSettingsDB).one().diesel_km_l = '5'
        self.price(5, 300)
        result = costs.summarize(self.db, [first, second])
        self.assertAlmostEqual(result['electricity_cost'], 10)
        self.assertAlmostEqual(result['diesel_cost'], 25)
        self.assertAlmostEqual(result['saving'], 15)
        self.assertEqual(result['comparable_distance_km'], 200)

    def test_savings_compare_identical_kilometers(self):
        self.price(2)
        result = costs.summarize(self.db, [self.trip(), self.trip(120, energy=None)])
        self.assertEqual(result['diesel_cost'], 20)
        self.assertEqual(result['electricity_cost'], 4)
        self.assertEqual(result['saving'], 6)
        self.assertEqual(result['comparable_distance_km'], 100)
        self.assertEqual(result['months'][0]['saving'], 6)

    def test_no_today_price_for_old_trips(self):
        old = self.trip(-3600)
        self.price(2)
        result = costs.summarize(self.db, [old])
        self.assertIsNone(result['diesel_cost'])
        self.assertIsNone(result['saving'])
        self.assertEqual(result['electricity_cost'], 4)

    def test_vehicle_specific_prices(self):
        self.price(2, vin='A')
        self.price(4, vin='B')
        self.assertEqual(costs.summarize(self.db, [self.trip(vin='A')])['diesel_cost'], 10)
        self.assertEqual(costs.summarize(self.db, [self.trip(vin='B')])['diesel_cost'], 20)

    def data(self, seconds=0, gps=True):
        Clock.current = (self.base+timedelta(seconds=seconds)).replace(tzinfo=timezone.utc)
        drive = dict(timestamp=Clock.current.timestamp()*1000, shift_state='D', speed=20)
        if gps:
            drive.update(latitude=41.9, longitude=12.5)
        return {'drive_state': drive}

    def test_automatic_price_refresh_cache_and_change_history(self):
        response = {"diesel": 2.01}
        with patch.object(fuel, 'nearest_price', return_value=response) as request, patch.object(fuel, 'now_utc', return_value=self.base):
            fuel.refresh_fuel_price(self.db, 'A', self.data())
            fuel.refresh_fuel_price(self.db, 'A', self.data(60))
            self.assertEqual(request.call_count, 1)
        response = {"diesel": 2.2}
        with patch.object(fuel, 'nearest_price', return_value=response), patch.object(fuel, 'now_utc', return_value=self.base+timedelta(hours=1)):
            fuel.refresh_fuel_price(self.db, 'A', self.data(3600))
        prices = self.db.query(CostRate).filter_by(source='gps_auto').order_by(CostRate.id).all()
        self.assertEqual([r.diesel for r in prices], [2.01, 2.2])
        self.assertEqual(self.db.get(FuelPriceState, 'A').diesel, 2.2)

    def test_missing_gps_or_price_failure_does_not_invent_price(self):
        with patch.object(fuel, 'nearest_price') as request:
            fuel.refresh_fuel_price(self.db, 'A', self.data(gps=False))
            request.assert_not_called()
        with patch.object(fuel, 'nearest_price', side_effect=RuntimeError('offline')), patch.object(fuel, 'now_utc', return_value=self.base):
            fuel.refresh_fuel_price(self.db, 'A', self.data())
        self.assertIsNone(self.db.get(FuelPriceState, 'A').diesel)
        self.assertEqual(self.db.query(CostRate).filter_by(source='gps_auto').count(), 0)

    def test_initial_rate_does_not_use_manual_diesel_default(self):
        costs.initial_rate(self.db)
        self.db.commit()
        self.assertIsNone(self.db.query(CostRate).one().diesel)

    def test_settings_only_change_creates_new_rate_when_needed(self):
        settings.get_settings(self.db)
        settings.save_settings(settings.SettingsPayload(voltage_protection=0), self.db)
        self.assertEqual(self.db.query(CostRate).count(), 1)
        settings.save_settings(settings.SettingsPayload(diesel_km_l=18), self.db)
        self.assertEqual(self.db.query(CostRate).count(), 2)
        settings.save_settings(settings.SettingsPayload(diesel_km_l=18), self.db)
        self.assertEqual(self.db.query(CostRate).count(), 2)
        self.assertIsNone(self.db.query(CostRate).order_by(CostRate.id.desc()).first().diesel)

    def test_mimit_pipe_format_selects_standard_self_service(self):
        from app.services.fuel_data_service import parse_data
        stations = 'Estrazione del 2026-10-03\nidImpianto|Nome Impianto|Comune|Latitudine|Longitudine\n1|Stazione A|Roma|41.9|12.5\n2|Stazione B|Roma|41.95|12.5\n'
        prices = 'Estrazione del 2026-10-03\nidImpianto|descCarburante|prezzo|isSelf|dtComu\n1|Gasolio|1.9|1|02/10/2026 10:00:00\n1|Gasolio|2.1|0|02/10/2026 10:00:00\n2|Gasolio speciale|2.2|1|02/10/2026 10:00:00\n'
        result = parse_data(stations, prices)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['diesel'], 1.9)
        self.assertEqual(result[0]['dataset_date'], '2026-10-03')

    def test_no_station_within_radius_is_an_error(self):
        from app.services import fuel_data_service as source
        today = source.datetime.now(source.ZoneInfo('Europe/Rome')).date().isoformat()
        with patch.object(source, '_cache', (today, [{'latitude': 0, 'longitude': 0}])):
            with self.assertRaises(ValueError):
                source.nearest_price(41.9, 12.5)

    def test_cost_routes_auth_and_active_trip_exclusion(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.database import get_db
        from app.dependencies import get_current_token
        from app.routers import costs as routes
        app = FastAPI()
        app.include_router(routes.router)
        app.dependency_overrides[get_db] = lambda: self.db
        client = TestClient(app)
        self.assertEqual(client.get('/api/costs/summary/A').status_code, 401)
        app.dependency_overrides[get_current_token] = lambda: object()
        self.price(2)
        self.trip()
        active = self.trip(120)
        active.status = 'active'
        active.last_sample_at = Clock.current.replace(tzinfo=None)
        self.db.commit()
        result = client.get('/api/costs/summary/A').json()
        self.assertEqual(result['trips'], 1)
        self.assertEqual(result['saving'], 6)
        self.assertEqual(client.get('/api/costs/summary/A?period=invalid').status_code, 422)
        self.assertEqual(client.get('/api/costs/rates?vin=A').status_code, 200)
