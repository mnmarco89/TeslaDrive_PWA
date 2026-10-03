import { useEffect, useState } from 'react';
import { api } from '../api/client';
import MetricCard from '../components/MetricCard';
import TripMap from '../components/TripMap';

const fmt = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString('it-IT', { maximumFractionDigits: digits });
const date = value => value ? new Date(value).toLocaleDateString('it-IT', { timeZone: 'Europe/Rome' }) : '—';
const time = value => value ? new Date(value).toLocaleTimeString('it-IT', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit' }) : '—';
const status = trip => trip.status === 'active' ? 'In corso' : trip.status === 'interrupted' ? 'Interrotto' : 'Concluso';

export default function TelemetryPage({ vin, dash }) {
  const [period, setPeriod] = useState('all');
  const [page, setPage] = useState(0);
  const [history, setHistory] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [tracking, setTracking] = useState(null);
  const [capacity, setCapacity] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [detailRevision, setDetailRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    api(`/api/trips/${vin}/settings`, { signal: controller.signal }).then(data => {
      setTracking(data); setCapacity(data.capacity_kwh ?? ''); setEnabled(data.enabled);
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [vin, revision]);

  useEffect(() => {
    const controller = new AbortController();
    let busy = false;
    const load = async () => {
      if (busy) return;
      busy = true;
      try {
        const [data, state] = await Promise.all([
          api(`/api/trips/${vin}?period=${period}&offset=${page * 50}`, { signal: controller.signal }),
          api(`/api/trips/${vin}/settings`, { signal: controller.signal }),
        ]);
        if (controller.signal.aborted) return;
        setHistory(data); setTracking(state);
        setSelectedId(current => data.items.some(t => t.id === current) ? current : data.items[0]?.id ?? null);
        setDetailRevision(r => r + 1); setError('');
      } catch (err) { if (err.name !== 'AbortError') setError(err.message); }
      finally { busy = false; }
    };
    setHistory(null); load();
    const timer = setInterval(load, 15000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [vin, period, page, revision]);

  useEffect(() => {
    const controller = new AbortController();
    if (!selectedId) { setDetail(null); return undefined; }
    setDetail(current => current?.id === selectedId ? current : null);
    api(`/api/trips/${vin}/${selectedId}`, { signal: controller.signal }).then(setDetail)
      .catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [vin, selectedId, detailRevision]);

  const save = async event => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const result = await api(`/api/trips/${vin}/settings`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, capacity_kwh: capacity === '' ? null : Number(capacity) }),
      });
      setTracking(result); setRevision(r => r + 1);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };
  const summary = history?.summary;
  return (
    <div className="dashboard-grid">
      <div className="metrics-row">
        <MetricCard title="Autonomia stimata" value={dash?.range_km != null ? `${fmt(dash.range_km, 0)} km` : '—'} icon="🔋" />
        <MetricCard title="Odometro totale" value={dash?.odometer_km != null ? `${fmt(dash.odometer_km, 0)} km` : '—'} icon="🛣️" />
        <MetricCard title="Velocità" value={`${fmt(dash?.speed_kmh ?? 0, 0)} km/h`} icon="🚀" />
        <MetricCard title="Destinazione attiva" value={typeof dash?.navigation === 'string' ? dash.navigation : '—'} icon="🧭" />
      </div>
      <section className="glass-panel full-width">
        <div className="panel-header"><h3>🧭 Telemetria e percorsi</h3><span className="live-badge">{tracking?.enabled ? 'ATTIVA' : 'IN PAUSA'}</span></div>
        <form onSubmit={save} className="trip-settings">
          <label className="trip-toggle"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Registra automaticamente i viaggi</label>
          <label>Capacità utile batteria (kWh)<input aria-label="Capacità utile batteria in kWh" type="number" min="1" max="200" step="0.1" placeholder="Da impostare" value={capacity} onChange={e => setCapacity(e.target.value)} /></label>
          <button type="submit" className="trip-button" disabled={saving}>{saving ? 'Salvataggio…' : 'Salva'}</button>
        </form>
        <p className="trip-note">{tracking?.status || 'Caricamento stato…'} · Ultimo campione: {tracking?.last_sample_at ? `${date(tracking.last_sample_at)} ${time(tracking.last_sample_at)}` : 'nessuno'}</p>
        <p className="trip-note">I kWh sono stimati dalla variazione della batteria e dalla capacità utile impostata; includono i servizi di bordo e risentono dell’arrotondamento della percentuale. La capacità si applica ai nuovi viaggi.</p>
        <p className="trip-note">L’app può essere chiusa, ma il server deve restare attivo. Se Render sospende il servizio o Tesla non invia dati, lo storico può essere incompleto.</p>
        {error && <p role="alert" className="trip-error">{error}</p>}
        <div className="trip-filters" aria-label="Periodo dello storico">
          {[['today', 'Oggi'], ['week', 'Settimana'], ['month', 'Mese'], ['all', 'Tutti']].map(([id, label]) => <button key={id} type="button" aria-pressed={period === id} className={`trip-button ${period === id ? 'selected' : ''}`} onClick={() => { setPeriod(id); setPage(0); }}>{label}</button>)}
        </div>
        <div className="metrics-row trip-summary">
          <MetricCard title="Viaggi nel periodo" value={fmt(summary?.trips, 0)} icon="🚗" />
          <MetricCard title="Distanza registrata" value={`${fmt(summary?.distance_km)} km`} icon="🛣️" />
          <MetricCard title="Energia stimata disponibile" value={`≈ ${fmt(summary?.energy_kwh)} kWh`} icon="⚡" />
          <MetricCard title="Consumo medio stimato" value={`≈ ${fmt(summary?.consumption_kwh_100km)} kWh/100 km`} icon="🔋" />
        </div>
        <p className="trip-note">Energia disponibile per {summary?.energy_trips ?? 0} di {summary?.trips ?? 0} viaggi · Costo energia stimato: {summary?.cost == null ? '—' : `≈ ${fmt(summary.cost, 2)} €`}. I costi usano la tariffa salvata all’inizio di ciascun viaggio.</p>
        <div className="trip-layout">
          <div className="trip-history">
            <h4>Storico viaggi</h4>
            {!history ? <p>Caricamento…</p> : history.items.length === 0 ? <p>Nessun viaggio registrato nel periodo. Lo storico parte da questo aggiornamento.</p> : history.items.map(trip => (
              <button type="button" key={trip.id} className={`trip-row ${trip.id === selectedId ? 'selected' : ''}`} onClick={() => setSelectedId(trip.id)} aria-pressed={trip.id === selectedId}>
                <strong>{date(trip.started_at)} · {time(trip.started_at)} → {trip.ended_at ? `${date(trip.ended_at) !== date(trip.started_at) ? date(trip.ended_at) + ' ' : ''}${time(trip.ended_at)}` : 'in corso'}</strong>
                <span>{fmt(trip.distance_km)} km · {fmt(trip.duration_minutes, 0)} min · ≈ {fmt(trip.energy_kwh)} kWh</span>
                <small>{status(trip)}{trip.partial ? ' · Percorso parziale' : ''}</small>
              </button>
            ))}
            <div className="trip-pagination"><button type="button" className="trip-button" disabled={!page} onClick={() => setPage(p => p - 1)}>Precedenti</button><span>{page + 1}</span><button type="button" className="trip-button" disabled={!history || (page + 1) * 50 >= history.total} onClick={() => setPage(p => p + 1)}>Successivi</button></div>
          </div>
          <div className="trip-detail">
            {detail ? <>
              <h4>{date(detail.started_at)} · {time(detail.started_at)} — {detail.ended_at ? time(detail.ended_at) : 'in corso'}</h4>
              {detail.partial && <p className="trip-note">Percorso parziale: partenza già in marcia o interruzione della raccolta. La mappa unisce solo i punti ricevuti.</p>}
              <TripMap key={detail.id} points={detail.points} />
              <div className="trip-detail-metrics">
                <span><strong>{fmt(detail.distance_km)} km</strong><small>{detail.distance_source === 'gps_estimate' ? 'Distanza GPS stimata' : 'Distanza da odometro'}</small></span>
                <span><strong>{fmt(detail.duration_minutes, 0)} min</strong><small>Durata registrata</small></span>
                <span><strong>{fmt(detail.start_battery, 0)}% → {fmt(detail.end_battery, 0)}%</strong><small>Batteria</small></span>
                <span><strong>≈ {fmt(detail.energy_kwh)} kWh</strong><small>Energia netta stimata</small></span>
                <span><strong>≈ {fmt(detail.consumption_kwh_100km)} kWh/100 km</strong><small>Consumo medio stimato</small></span>
                <span><strong>{detail.energy_cost == null ? '—' : `≈ ${fmt(detail.energy_cost, 2)} €`}</strong><small>Costo energia stimato</small></span>
              </div>
              <p className="trip-note">{detail.points.length} campioni · Orari Europe/Rome · Verde: primo punto · Arancione: ultimo punto</p>
              {detail.destination && <p>Destinazione: {detail.destination}</p>}
            </> : <div className="empty-state-box"><p>{selectedId ? 'Caricamento percorso…' : 'Seleziona un viaggio per vedere la mappa e i consumi.'}</p></div>}
          </div>
        </div>
      </section>
    </div>
  );
}
