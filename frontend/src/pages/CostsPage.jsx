export default function CostsPage({ settings, setSettings, onSave }) {
  return (
    <div className="glass-panel full-width">
      <div className="panel-header">
        <h3>⚡ Parametri di Calcolo Costi</h3>
        <span className="auto-loc-badge">📍 GPS Dinamico</span>
      </div>

      {settings && (
        <div className="settings-form" style={{ maxWidth: '500px' }}>
          <div className="input-group">
            <label>Energia Elettrica (€/kWh)</label>
            <input
              type="number"
              step="0.01"
              value={settings.electricity}
              onChange={event => setSettings({ ...settings, electricity: +event.target.value })}
            />
          </div>

          <div className="input-group">
            <label>Prezzo Diesel (€/L)</label>
            <input
              type="number"
              step="0.01"
              value={settings.diesel}
              onChange={event => setSettings({ ...settings, diesel: +event.target.value })}
            />
          </div>

          <div className="input-group">
            <label>Consumo Termico (km/L)</label>
            <input
              type="number"
              step="0.1"
              value={settings.diesel_km_l}
              onChange={event => setSettings({ ...settings, diesel_km_l: +event.target.value })}
            />
          </div>

          <button className="btn-save" onClick={onSave}>
            Salva Configurazione
          </button>
        </div>
      )}
    </div>
  );
}
