export default function VehicleHero({ vehicles, vin, dash, onVehicleChange, compact = false }) {
  return (
    <section className={`car-hero-card ${compact ? "compact-vehicle-hero" : ""}`}>
      <div className="car-info">
        <span className="label-top">VEICOLO ATTIVO</span>
        <h2>{vehicles.find(vehicle => vehicle.vin === vin)?.display_name || 'Model 3 / Y'}</h2>
        <div className="select-wrapper">
          <select aria-label="Veicolo attivo" value={vin} onChange={event => onVehicleChange(event.target.value)}>
            {vehicles.map(vehicle => (
              <option key={vehicle.vin} value={vehicle.vin}>
                {vehicle.display_name || vehicle.vin}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="battery-display">
        <div className="battery-ring" style={{ '--battery': `${Math.min(100, Math.max(0, dash?.battery ?? 0))}%` }}>
          <span className="battery-value">{dash?.battery ?? '—'}</span>
          <span className="battery-unit">%</span>
        </div>
        <span className="battery-label">Batteria</span>
      </div>
    </section>
  );
}
