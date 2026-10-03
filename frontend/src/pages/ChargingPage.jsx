import ChargingHistory from '../components/ChargingHistory';
export default function ChargingPage({
  vin,
  charging,
  targetAmps,
  setTargetAmps,
  changeAmps,
  settings,
  onVoltageProtectionChange,
}) {
  return (
    <>
    <section className="glass-panel full-width">
      <div className="panel-header">
        <h3>Ricarica</h3>
        <span className={`live-badge ${charging?.charging_state === 'Charging' ? 'active-charging' : ''}`}>
          {charging?.charging_state === 'Charging'
            ? 'IN CARICA'
            : ({ Complete: 'COMPLETA', Stopped: 'FERMA', Disconnected: 'SCOLLEGATA' }[charging?.charging_state] || 'IN ATTESA')}
        </span>
      </div>

      <div className="charging-control-grid">
        <div className="charge-stat-box">
          <span>Potenza Attuale</span>
          <strong>
            {charging?.charger_power != null ? `${charging.charger_power} kW` : '0 kW'}
          </strong>
        </div>

        <div className="charge-stat-box">
          <span>Tensione / Corrente</span>
          <strong
            style={{
              color: charging?.charger_voltage && charging.charger_voltage < 210
                ? '#ff9500'
                : 'inherit',
            }}
          >
            {charging?.charger_voltage
              ? `${charging.charger_voltage}V / ${charging.charger_actual_current || 0}A`
              : '—'}
          </strong>
        </div>

        <div className="charge-control-slider-box">
          <label>Corrente di ricarica ({targetAmps} A)</label>
          <div className="slider-row">
            <input
              aria-label="Corrente di ricarica"
              type="range"
              min="10"
              max="20"
              step="1"
              value={targetAmps}
              onChange={event => setTargetAmps(+event.target.value)}
              onMouseUp={event => changeAmps(+event.target.value)}
              onTouchEnd={event => changeAmps(+event.target.value)}
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
          <span>Protezione tensione</span>
          <small>
            Riduce la corrente sotto 208 V, la rialza da 218 V.
          </small>
        </div>
        <label className="switch">
          <input
            type="checkbox"
            aria-label="Protezione automatica tensione"
            checked={settings?.voltage_protection === 1}
            onChange={event => onVoltageProtectionChange(event.target.checked)}
          />
          <span className="slider round"></span>
        </label>
      </div>
    </section>
    <ChargingHistory key={vin} vin={vin}/>
    </>
  );
}
