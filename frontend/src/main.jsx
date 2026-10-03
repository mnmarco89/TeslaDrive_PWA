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
  const [vin, setVin] = useState(localStorage.getItem('shmersla_vin') || '');
  const [dash, setDash] = useState(null);
  const [charging, setCharging] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [targetAmps, setTargetAmps] = useState(16);
  
  // Nuovo stato per la navigazione a schede
  const [activeTab, setActiveTab] = useState('ricarica'); // 'ricarica', 'telemetria', 'costi'

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
        localStorage.setItem('shmersla_vin', chosen);
        setDash(await api('/api/dashboard/' + chosen));
        try {
          const chData = await api('/api/charging/' + chosen);
          setCharging(chData);
          if (chData.charge_amps) setTargetAmps(chData.charge_amps);
        } catch (e) { console.error(e); }
      }
      setSettings(await api('/api/settings'));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load() }, []);

  useEffect(() => {
    if (!vin || !connected) return;
    const t = setInterval(async () => {
      try {
        setDash(await api('/api/dashboard/' + vin));
        setCharging(await api('/api/charging/' + vin));
      } catch (e) { setError(e.message); }
    }, 15000);
    return () => clearInterval(t);
  }, [vin, connected]);

  const saveSettings = async () => {
    await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
    setError('✨ Impostazioni salvate con successo.');
    setTimeout(() => setError(''), 3000);
  };

  const changeAmps = async (newAmps) => {
    try {
      setTargetAmps(newAmps);
      await api(`/api/vehicles/${vin}/set_amps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amps: newAmps })
      });
      setError(`⚡ Amperaggio impostato a ${newAmps}A`);
      setTimeout(() => setError(''), 3000);
    } catch (e) {
      setError('Errore comando ampere: ' + e.message);
    }
  };

  const logout = async () => {
    await api('/auth/logout', { method: 'POST' });
    setConnected(false); setDash(null); setVehicles([]);
  };

  return (
    <div className="tesla-app">
      <header className="app-header">
        <div className="brand">
          <img src="/logo.png" alt="Shmersla Logo" className="brand-logo-img" />
          <div>
            <h1>Shmersla</h1>
            <span className="subtitle">Fleet Telemetry & Voltage Control</span>
          </div>
        </div>
        {connected && <button className="btn-logout" onClick={logout}>Scollega Account</button>}
      </header>

      {error && <div className={`notice ${error.includes('✨') || error.includes('⚡') ? 'success' : ''}`}>{error}</div>}

      {loading ? (
        <div className="loader-container">
          <div className="tesla-spinner"></div>
          <p>Connessione ai server in corso...</p>
        </div>
      ) : !connected ? (
        <div className="login-hero">
          <div className="hero-badge">SECURE OAUTH 2.0</div>
          <h2>La tua Shmersla, <br/>senza compromessi.</h2>
          <p>Monitoraggio in tempo reale, telemetria avanzata e protezione intelligente del voltaggio domestico.</p>
          <button className="btn-tesla-login" onClick={() => window.location.href = "/auth/tesla/start"}>
            <span>Accedi con Tesla ID</span>
          </button>
          <span className="security-note">🔒 Credenziali gestite direttamente dai server crittografati Tesla.</span>
        </div>
      ) : (
        <main className="dashboard-grid">
          
          {/* CRUSCOTTO PRINCIPALE SEMPRE VISIBILE */}
          <section className="car-hero-card">
            <div className="car-info">
              <span className="label-top">VEICOLO ATTIVO</span>
              <h2>{vehicles.find(x => x.vin === vin)?.display_name || 'Model 3 / Y'}</h2>
              <div className="select-wrapper">
                <select value={vin} onChange={async e => {
                  const x = e.target.value;
                  setVin(x);
                  localStorage.setItem('shmersla_vin', x);
                  setDash(await api('/api/dashboard/' + x));
                  setCharging(await api('/api/charging/' + x));
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

          {/* MENU A SCHEDE */}
          <div className="tabs-nav">
            <button 
              className={`tab-btn ${activeTab === 'ricarica' ? 'active' : ''}`} 
              onClick={() => setActiveTab('ricarica')}
            >
              🔌 Ricarica & Voltaggio
            </button>
            <button 
              className={`tab-btn ${activeTab === 'telemetria' ? 'active' : ''}`} 
              onClick={() => setActiveTab('telemetria')}
            >
              🧭 Telemetria & Navigazione
            </button>
            <button 
              className={`tab-btn ${activeTab === 'costi' ? 'active' : ''}`} 
              onClick={() => setActiveTab('costi')}
            >
              ⚡ Costi ed Energia
            </button>
          </div>

          <div className="tab-content">
            {/* TAB: RICARICA & VOLTAGGIO */}
            {activeTab === 'ricarica' && (
              <section className="glass-panel full-width">
                <div className="panel-header">
                  <h3>🔌 Gestione Ricarica & Smart Voltage Governor</h3>
                  <span className={`live-badge ${charging?.charging_state === 'Charging' ? 'active-charging' : ''}`}>
                    {charging?.charging_state === 'Charging' ? 'IN CARICA' : (charging?.charging_state || 'STANDBY')}
                  </span>
                </div>
                
                <div className="charging-control-grid">
                  <div className="charge-stat-box">
                    <span>Potenza Attuale</span>
                    <strong>{charging?.charger_power != null ? charging.charger_power + ' kW' : '0 kW'}</strong>
                  </div>
                  <div className="charge-stat-box">
                    <span>Tensione / Corrente</span>
                    <strong style={{ color: (charging?.charger_voltage && charging.charger_voltage < 210) ? '#ff9500' : 'inherit' }}>
                      {charging?.charger_voltage ? `${charging.charger_voltage}V / ${charging.charger_actual_current || 0}A` : '—'}
                    </strong>
                  </div>
                  <div className="charge-control-slider-box">
                    <label>Limitazione Amperaggio ({targetAmps} A)</label>
                    <div className="slider-row">
                      <input 
                        type="range" min="10" max="20" step="1" 
                        value={targetAmps} 
                        onChange={e => setTargetAmps(+e.target.value)}
                        onMouseUp={e => changeAmps(+e.target.value)}
                        onTouchEnd={e => changeAmps(+e.target.value)}
                      />
                      <div className="amp-preset-buttons">
                        <button onClick={() => changeAmps(10)}>10A</button>
                        <button onClick={() => changeAmps(16)}>16A</button>
                        <button onClick={() => changeAmps(20)}>20A</button>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="voltage-guard-box">
                  <div className="guard-info">
                    <span>🛡️ Protezione Automatica Voltaggio (Target 207V - 220V)</span>
                    <small>Riduce gli Ampere se la tensione scende a 207V e li rialza quando si stabilizza sopra i 218V.</small>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={settings?.voltage_protection === 1} 
                      onChange={async (e) => {
                        const val = e.target.checked ? 1 : 0;
                        const updated = { ...settings, voltage_protection: val };
                        setSettings(updated);
                        await api('/api/settings', { 
                          method: 'POST', 
                          headers: { 'Content-Type': 'application/json' }, 
                          body: JSON.stringify(updated) 
                        });
                      }} 
                    />
                    <span className="slider round"></span>
                  </label>
                </div>
              </section>
            )}

            {/* TAB: TELEMETRIA & NAVIGAZIONE */}
            {activeTab === 'telemetria' && (
              <div className="dashboard-grid">
                <div className="metrics-row">
                  <MetricCard title="Autonomia Stimata" value={dash?.range_km != null ? Math.round(dash.range_km) + ' km' : '—'} icon="🔋" />
                  <MetricCard title="Odometro Totale" value={dash?.odometer_km != null ? Math.round(dash.odometer_km).toLocaleString() + ' km' : '—'} icon="🛣️" />
                  <MetricCard title="Velocità Istantanea" value={dash?.speed_kmh != null ? Math.round(dash.speed_kmh) + ' km/h' : '0 km/h'} icon="🚀" />
                  <MetricCard title="Stato Marcia" value={dash?.shift_state || 'P'} icon="⚙️" highlight={true} />
                </div>

                <div className="glass-panel full-width mt-4">
                  <div className="panel-header">
                    <h3>🧭 Navigazione Attiva</h3>
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
              </div>
            )}

            {/* TAB: COSTI ED ENERGIA */}
            {activeTab === 'costi' && (
              <div className="glass-panel full-width">
                <div className="panel-header">
                  <h3>⚡ Parametri di Calcolo Costi</h3>
                  <span className="auto-loc-badge">📍 GPS Dinamico</span>
                </div>
                {settings && (
                  <div className="settings-form" style={{ maxWidth: '500px' }}>
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
                    <button className="btn-save" onClick={saveSettings}>Salva Configurazione</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      )}

      <footer className="app-footer">
        <span>Shmersla PWA • Sincronizzazione Cloud</span>
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