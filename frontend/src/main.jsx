import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const api = (p, o = {}) => fetch(p, { credentials: 'include', ...o }).then(async r => {
  const t = await r.text();
  let d;
  try { d = JSON.parse(t) } catch { d = t }
  if (!r.ok) throw new Error(d?.detail || d || `HTTP ${r.status}`);
  return d;
});

function App() {
  const [connected, setConnected] = useState(false);
  const [vehicles, setVehicles] = useState([]);
  const [vin, setVin] = useState(localStorage.getItem('tesladrive_vin') || '');
  const [dash, setDash] = useState(null);
  const [settings, setSettings] = useState(null);
  const [trips, setTrips] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const st = await api('/api/status');
      setConnected(st.authenticated);
      if (!st.authenticated) { setLoading(false); return; }
      
      const v = await api('/api/vehicles');
      const list = v.response || v;
      setVehicles(list);
      
      const chosen = vin || list[0]?.vin;
      if (chosen) {
        setVin(chosen);
        localStorage.setItem('tesladrive_vin', chosen);
        setDash(await api('/api/dashboard/' + chosen));
      }
      setSettings(await api('/api/settings'));
      setTrips(await api('/api/trips'));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load() }, []);

  useEffect(() => {
    if (!vin || !connected) return;
    const t = setInterval(() => api('/api/dashboard/' + vin).then(setDash).catch(e => setError(e.message)), 15000);
    return () => clearInterval(t);
  }, [vin, connected]);

  const save = async () => {
    await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
    setError('✨ Impostazioni salvate con successo.');
    setTimeout(() => setError(''), 3000);
  };

  const logout = async () => {
    await api('/auth/logout', { method: 'POST' });
    setConnected(false); setDash(null); setVehicles([]);
  };

  return (
    <div className="tesla-app">
      <header className="app-header">
        <div className="brand">
          <div className="brand-logo">T</div>
          <div>
            <h1>TeslaDrive</h1>
            <span className="subtitle">Fleet Telemetry & Real-Time Data</span>
          </div>
        </div>
        {connected && <button className="btn-logout" onClick={logout}>Scollega Account</button>}
      </header>

      {error && <div className={`notice ${error.includes('✨') ? 'success' : ''}`}>{error}</div>}

      {loading ? (
        <div className="loader-container">
          <div className="tesla-spinner"></div>
          <p>Connessione ai server Tesla in corso...</p>
        </div>
      ) : !connected ? (
        <div className="login-hero">
          <div className="hero-badge">SECURE OAUTH 2.0</div>
          <h2>La tua Tesla, <br/>senza compromessi.</h2>
          <p>Monitoraggio in tempo reale, telemetria avanzata e gestione energetica direttamente integrata con la tua vettura.</p>
          <button className="btn-tesla-login" onClick={() => window.location.href = "/auth/tesla/start"}>
            <span>Accedi con Tesla ID</span>
          </button>
          <span className="security-note">🔒 Credenziali gestite direttamente dai server crittografati Tesla.</span>
        </div>
      ) : (
        <main className="dashboard-grid">
          {/* Box Principale Veicolo */}
          <section className="car-hero-card">
            <div className="car-info">
              <span className="label-top">VEICOLO ATTIVO</span>
              <h2>{vehicles.find(x => x.vin === vin)?.display_name || 'Model 3 / Y'}</h2>
              <div className="select-wrapper">
                <select value={vin} onChange={async e => {
                  const x = e.target.value;
                  setVin(x);
                  localStorage.setItem('tesladrive_vin', x);
                  setDash(await api('/api/dashboard/' + x));
                }}>
                  {vehicles.map(x => <option key={x.vin} value={x.vin}>{x.display_name || x.vin}</option>)}
                </select>
              </div>
            </div>
            <div className="battery-display">
              <div className="battery-ring">
                <span className="battery-value">{dash?.battery ?? '—'}</span>
                <span className="battery-unit">%</span>
              </div>
              <span className="battery-label">Batteria Residua</span>
            </div>
          </section>

          {/* Metric Cards */}
          <div className="metrics-row">
            <MetricCard title="Autonomia Stimata" value={dash?.range_km != null ? Math.round(dash.range_km) + ' km' : '—'} icon="🔋" />
            <MetricCard title="Odometro Totale" value={dash?.odometer_km != null ? Math.round(dash.odometer_km).toLocaleString() + ' km' : '—'} icon="🛣️" />
            <MetricCard title="Velocità Istantanea" value={dash?.speed_kmh != null ? Math.round(dash.speed_kmh) + ' km/h' : '0 km/h'} icon="🚀" />
            <MetricCard title="Stato Marcia" value={dash?.shift_state || 'P'} icon="⚙️" highlight={true} />
          </div>

          {/* Pannelli Inferiori */}
          <div className="panels-split">
            <div className="glass-panel">
              <div className="panel-header">
                <h3>🧭 Navigazione & Telemetria</h3>
                <span className="live-badge">LIVE</span>
              </div>
              {dash?.navigation && Object.keys(dash.navigation).length ? (
                <pre className="code-box">{JSON.stringify(dash.navigation, null, 2)}</pre>
              ) : (
                <div className="empty-state-box">
                  <p>Nessuna destinazione attiva al momento.</p>
                  <span>La rotta e le indicazioni appariranno qui automaticamente durante il viaggio.</span>
                </div>
              )}
            </div>

            <div className="glass-panel">
              <div className="panel-header">
                <h3>⚡ Costi ed Energia</h3>
                <span className="auto-loc-badge">📍 Prezzi Nazionali</span>
              </div>
              {settings && (
                <div className="settings-form">
                  <div className="input-group">
                    <label>Energia Elettrica (€/kWh)</label>
                    <input type="number" step="0.01" value={settings.electricity} onChange={e => setSettings({ ...settings, electricity: +e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label>Prezzo Diesel (€/L)</label>
                    <input type="number" step="0.01" value={settings.diesel} onChange={e => setSettings({ ...settings, diesel: +e.target.value })} />
                  </div>
                  <div className="input-group">
                    <label>Consumo Termico (km/L)</label>
                    <input type="number" step="0.1" value={settings.diesel_km_l} onChange={e => setSettings({ ...settings, diesel_km_l: +e.target.value })} />
                  </div>
                  <button className="btn-save" onClick={save}>Salva Configurazione</button>
                </div>
              )}
            </div>
          </div>
        </main>
      )}

      <footer className="app-footer">
        <span>TeslaDrive PWA • Sincronizzazione Cloud</span>
        <span>Aggiornato: {dash?.updated_at ? new Date(dash.updated_at).toLocaleTimeString('it-IT') : '—'}</span>
      </footer>
    </div>
  );
}

function MetricCard({ title, value, icon, highlight }) {
  return (
    <div className={`metric-card ${highlight ? 'highlight' : ''}`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-content">
        <span className="metric-title">{title}</span>
        <strong className="metric-value">{value}</strong>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);