export default function VehicleHero({ vehicles, vin, dash, onVehicleChange }) {
  return (
    <section className="car-hero-card">
      <div className="car-info">
        <span className="label-top">VEICOLO ATTIVO</span>
        <h2>{vehicles.find(vehicle => vehicle.vin === vin)?.display_name || 'Model 3 / Y'}</h2>
        <div className="select-wrapper">
          <select value={vin} onChange={event => onVehicleChange(event.target.value)}>
            {vehicles.map(vehicle => (
              <option key={vehicle.vin} value={vehicle.vin}>
                {vehicle.display_name || vehicle.vin}
              </option>
            ))}
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
  );
}
