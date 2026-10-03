import MetricCard from '../components/MetricCard';

export default function TelemetryPage({ dash }) {
  return (
    <div className="dashboard-grid">
      <div className="metrics-row">
        <MetricCard
          title="Autonomia Stimata"
          value={dash?.range_km != null ? `${Math.round(dash.range_km)} km` : '—'}
          icon="🔋"
        />
        <MetricCard
          title="Odometro Totale"
          value={dash?.odometer_km != null ? `${Math.round(dash.odometer_km).toLocaleString()} km` : '—'}
          icon="🛣️"
        />
        <MetricCard
          title="Velocità Istantanea"
          value={dash?.speed_kmh != null ? `${Math.round(dash.speed_kmh)} km/h` : '0 km/h'}
          icon="🚀"
        />
        <MetricCard
          title="Stato Marcia"
          value={dash?.shift_state || 'P'}
          icon="⚙️"
          highlight
        />
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
            <span>
              La rotta e le indicazioni appariranno qui automaticamente durante il viaggio.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
