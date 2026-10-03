import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.dependencies import get_current_token
from app.models import UserToken
from app.routers import home, vehicles
from app.services import tesla_service, trip_collector


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.app = FastAPI()
        self.app.include_router(home.router)
        self.app.include_router(vehicles.router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def login(self):
        self.db.add(UserToken(access_token='test-token'))
        self.db.commit()

    def test_profile_and_controls_require_auth(self):
        self.assertEqual(self.client.get('/api/profile').status_code, 401)
        with patch.object(home, 'send_signed_tesla_command', new_callable=AsyncMock) as sender:
            self.assertEqual(self.client.post('/api/vehicles/A/controls', json={'action': 'unlock'}).status_code, 401)
            sender.assert_not_awaited()

    def test_profile_is_filtered_and_https_only(self):
        self.login()
        response = Mock(status_code=200)
        response.json.return_value = {'response': {'first_name':'Marco','last_name':'Nanni','email':'sample@example.com',
            'profile_image_url':'https://images.example.com/avatar.png', 'access_token':'should-not-appear','home_address':'private'}}
        with patch.object(home, '_request', return_value=response):
            result = self.client.get('/api/profile').json()
        self.assertEqual(result['name'], 'Marco Nanni')
        self.assertEqual(result['photo_url'], 'https://images.example.com/avatar.png')
        self.assertNotIn('access_token', result)
        self.assertNotIn('home_address', result)
        response.json.return_value['response']['profile_image_url'] = 'javascript:alert(1)'
        with patch.object(home, '_request', return_value=response):
            self.assertIsNone(self.client.get('/api/profile').json()['photo_url'])

    def test_missing_profile_scope_does_not_block_home(self):
        self.login()
        with patch.object(home, '_request', return_value=Mock(status_code=403)):
            result = self.client.get('/api/profile')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['scope_needed'])

    def test_only_allowed_actions_are_forwarded_and_cache_invalidated(self):
        self.login()
        with patch.object(home, 'send_signed_tesla_command', new_callable=AsyncMock, return_value={'response':{'result':True}}) as sender, patch.object(home, 'invalidate_sample') as invalidate:
            self.assertEqual(self.client.post('/api/vehicles/A/controls', json={'action':'erase_user_data'}).status_code,422)
            sender.assert_not_awaited()
            for action, (endpoint, payload) in home.COMMANDS.items():
                reply = self.client.post('/api/vehicles/A/controls', json={'action':action})
                self.assertEqual(reply.status_code,200)
                sender.assert_awaited_with('A','test-token',endpoint,payload)
            self.assertEqual(invalidate.call_count,8)

    def test_command_rejection_remains_failure(self):
        self.login()
        with patch.object(home, 'send_signed_tesla_command', new_callable=AsyncMock, side_effect=ValueError('Unauthorized missing scopes')), patch.object(home,'invalidate_sample') as invalidate:
            result = self.client.post('/api/vehicles/A/controls', json={'action':'unlock'})
        self.assertEqual(result.status_code,400)
        self.assertIn('Permessi', result.json()['detail'])
        invalidate.assert_not_called()

    def test_dashboard_preserves_unknown_and_maps_doors(self):
        self.login()
        data = {'vehicle_state':{'df':0,'pr':1,'locked':False,'tpms_pressure_fl':2.9,'car_version':'2026.1'},
                'climate_state':{'inside_temp':22,'outside_temp':0,'is_climate_on':False}}
        with patch.object(vehicles,'fetch_sample', return_value=data):
            result = self.client.get('/api/dashboard/A').json()
        self.assertIsNone(result['doors']['pf'])
        self.assertEqual(result['doors']['pr'],1)
        self.assertFalse(result['locked'])
        self.assertEqual(result['outside_temp'],0)
        self.assertEqual(result['tpms']['fl'],2.9)
        self.assertIsNone(result['shift_state'])

    def test_invalidation_preserves_other_vehicle(self):
        trip_collector._cache['A']=(0,{'locked':True})
        trip_collector._cache['B']=(0,{'locked':False})
        trip_collector.invalidate_sample('A')
        self.assertNotIn('A',trip_collector._cache)
        self.assertIn('B',trip_collector._cache)
        trip_collector._cache.clear()


class SigningTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_reply_is_not_success_and_key_is_removed(self):
        vehicle = SimpleNamespace(door_unlock=AsyncMock(return_value={'response':{'result':False,'reason':'vehicle unavailable'}}))
        fake_api = Mock()
        paths=[]
        async def key(path):
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(os.stat(path).st_mode & 0o777,0o600)
            paths.append(path)
        fake_api.get_private_key=AsyncMock(side_effect=key)
        fake_api.vehicles.createSigned.return_value=vehicle
        with patch.object(tesla_service,'TESLA_PRIVATE_KEY','test-key'), patch.object(tesla_service,'TeslaFleetApi',return_value=fake_api):
            with self.assertRaisesRegex(ValueError,'vehicle unavailable'):
                await tesla_service.send_signed_tesla_command('A','test-token','door_unlock',{})
        self.assertTrue(paths)
        self.assertFalse(os.path.exists(paths[0]))

    async def test_key_is_removed_even_when_loading_fails(self):
        fake_api=Mock()
        paths=[]
        async def key(path):
            paths.append(path)
            raise ValueError('invalid key')
        fake_api.get_private_key=AsyncMock(side_effect=key)
        with patch.object(tesla_service,'TESLA_PRIVATE_KEY','test-key'), patch.object(tesla_service,'TeslaFleetApi',return_value=fake_api):
            with self.assertRaisesRegex(ValueError,'invalid key'):
                await tesla_service.send_signed_tesla_command('A','test-token','door_lock',{})
        self.assertFalse(os.path.exists(paths[0]))

    async def test_charging_command_still_uses_signed_path(self):
        vehicle=SimpleNamespace(set_charging_amps=AsyncMock(return_value={'response':{'result':True}}))
        fake_api=Mock(get_private_key=AsyncMock())
        fake_api.vehicles.createSigned.return_value=vehicle
        with patch.object(tesla_service,'TESLA_PRIVATE_KEY','test-key'), patch.object(tesla_service,'TeslaFleetApi',return_value=fake_api):
            await tesla_service.send_signed_tesla_command('A','test-token','set_charging_amps',{'charging_amps':16})
        vehicle.set_charging_amps.assert_awaited_once_with(charging_amps=16)
