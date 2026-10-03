import { useEffect, useRef, useState } from 'react';

import { api } from './api/client';
import Footer from './components/Footer';
import Header from './components/Header';
import LoginHero from './components/LoginHero';
import TabsNav from './components/TabsNav';
import VehicleHero from './components/VehicleHero';
import HomePage from './pages/HomePage';
import ChargingPage from './pages/ChargingPage';
import CostsPage from './pages/CostsPage';
import SavingsPage from './pages/SavingsPage';
import TelemetryPage from './pages/TelemetryPage';

export default function App() {
  const [connected, setConnected] = useState(false);
  const [vehicles, setVehicles] = useState([]);
  const [vin, setVin] = useState(localStorage.getItem('shmersla_vin') || '');
  const [profile, setProfile] = useState(null);
  const [profileError, setProfileError] = useState('');
  const currentVin = useRef(vin);
  const [dash, setDash] = useState(null);
  const [charging, setCharging] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [targetAmps, setTargetAmps] = useState(16);
  const [activeTab, setActiveTab] = useState('home');

  const loadVehicleData = async vehicleVin => {
    const [dashboardResult, chargingResult] = await Promise.allSettled([
      api(`/api/dashboard/${vehicleVin}`),
      api(`/api/charging/${vehicleVin}`),
    ]);
    if (currentVin.current !== vehicleVin) return;
    if (dashboardResult.status === 'fulfilled') setDash(dashboardResult.value);
    if (chargingResult.status === 'fulfilled') {
      const chargingData = chargingResult.value;
      setCharging(chargingData);
      if (chargingData.charge_amps) setTargetAmps(Math.min(20, Math.max(10, chargingData.charge_amps)));
    }
    const failure = [dashboardResult, chargingResult].find(r => r.status === 'rejected');
    if (failure) throw failure.reason;
  };

  const load = async () => {
    setLoading(true);
    setError('');

    try {
      const status = await api('/api/status');
      setConnected(status.authenticated);
      if (!status.authenticated) return;

      const vehiclesResponse = await api('/api/vehicles');
      const vehicleList = vehiclesResponse.response || vehiclesResponse;
      setVehicles(vehicleList);

      api('/api/profile').then(setProfile).catch(err => setProfileError(err.message));
      const selectedVin = vehicleList.some(v => v.vin === vin) ? vin : vehicleList[0]?.vin;
      if (selectedVin) {
        currentVin.current = selectedVin;
        setVin(selectedVin);
        localStorage.setItem('shmersla_vin', selectedVin);
        try { await loadVehicleData(selectedVin); } catch (err) { setError(err.message); }
      } else {
        currentVin.current = ''; setVin(''); setDash(null); setCharging(null);
        localStorage.removeItem('shmersla_vin');
      }

      setSettings(await api('/api/settings'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!vin || !connected) return undefined;

    const timer = setInterval(async () => {
      try {
        await loadVehicleData(vin);
      } catch (err) {
        setError(err.message);
      }
    }, 15000);

    return () => clearInterval(timer);
  }, [vin, connected]);

  const showSuccess = message => {
    setError(message);
    setTimeout(() => setError(''), 3000);
  };

  const saveSettings = async () => {
    try {
      await api('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      showSuccess('✨ Impostazioni salvate con successo.');
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  const changeAmps = async newAmps => {
    try {
      const safeAmps = Math.min(20, Math.max(10, Number(newAmps)));
      setTargetAmps(safeAmps);
      await api(`/api/vehicles/${vin}/set_amps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amps: safeAmps }),
      });
      showSuccess(`⚡ Amperaggio impostato a ${safeAmps}A`);
    } catch (err) {
      setError(`Errore comando ampere: ${err.message}`);
    }
  };

  const changeVoltageProtection = async enabled => {
    const updated = { ...settings, voltage_protection: enabled ? 1 : 0 };
    setSettings(updated);

    try {
      await api('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
    } catch (err) {
      setError(err.message);
    }
  };

  const changeVehicle = async selectedVin => {
    currentVin.current = selectedVin;
    setDash(null); setCharging(null);
    setVin(selectedVin);
    localStorage.setItem('shmersla_vin', selectedVin);

    try {
      await loadVehicleData(selectedVin);
    } catch (err) {
      setError(err.message);
    }
  };

  const logout = async () => {
    await api('/auth/logout', { method: 'POST' });
    setConnected(false);
    currentVin.current = '';
    setProfile(null); setProfileError('');
    setDash(null);
    setCharging(null);
    setVehicles([]);
  };

  return (
    <div className="tesla-app">
      <Header profile={profile} connected={connected} onLogout={logout} />

      {error && (
        <div className={`notice ${error.includes('✨') || error.includes('⚡') ? 'success' : ''}`}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="loader-container">
          <div className="tesla-spinner"></div>
          <p>Connessione ai server in corso...</p>
        </div>
      ) : !connected ? (
        <LoginHero />
      ) : (
        <main className="dashboard-grid">
          <VehicleHero
            compact={activeTab === 'home'}
            vehicles={vehicles}
            vin={vin}
            dash={dash}
            onVehicleChange={changeVehicle}
          />

          <TabsNav activeTab={activeTab} onChange={setActiveTab} />

          <div className="tab-content">
            {activeTab === 'home' && <HomePage key={vin} vin={vin} dash={dash} profile={profile} profileError={profileError} onRefresh={() => loadVehicleData(vin).catch(err => { setError(err.message); throw err; })} onNavigate={setActiveTab} />}

            {activeTab === 'ricarica' && (
              <ChargingPage
                vin={vin}
                charging={charging}
                targetAmps={targetAmps}
                setTargetAmps={setTargetAmps}
                changeAmps={changeAmps}
                settings={settings}
                onVoltageProtectionChange={changeVoltageProtection}
              />
            )}

            {activeTab === 'telemetria' && <TelemetryPage key={vin} vin={vin} dash={dash} />}

            {activeTab === 'risparmio' && <SavingsPage key={vin} vin={vin} onNavigate={setActiveTab}/>}

            {activeTab === 'costi' && (
              <CostsPage
                key={vin}
                vin={vin}
                settings={settings}
                setSettings={setSettings}
                onSave={saveSettings}
              />
            )}
          </div>
        </main>
      )}

      <Footer updatedAt={dash?.updated_at} />
    </div>
  );
}
