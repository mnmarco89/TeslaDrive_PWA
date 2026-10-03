import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import MetricCard from '../components/MetricCard';
import TripContext from '../components/TripContext';
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
  const [detailLoading, setDetailLoading] = useState(false);
  const detailPanel = useRef(null);
  const [tracking, setTracking] = useState(null);
  const [capacity, setCapacity] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const [detailRevision, setDetailRevision] = useState(0);

  useEffect(() => {
    const panel = detailPanel.current;
    if (!panel) return undefined;
    let width = panel.clientWidth;
    let height = panel.clientHeight;
    // Keep the reading surface stable even while asynchronous context is empty.
    const observer = new ResizeObserver(() => {
      if (panel.clientWidth !== width) {
        width = panel.clientWidth;
        panel.style.minHeight = '';
        height = panel.scrollHeight;
      }
      height = Math.max(height, panel.scrollHeight);
      panel.style.minHeight = `${height}px`;
    });
    observer.observe(panel);
    return () => observer.disconnect();
  }, []);

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
    setDetailLoading(true);
    api(`/api/trips/${vin}/${selectedId}`, { signal: controller.signal }).then(data => { if(!controller.signal.aborted) { setDetail(data); setDetailLoading(false); } })
      .catch(err => { if (err.name !== 'AbortError') { setError(err.message); setDetailLoading(false); } });
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
  const selectedIndex = history?.items.findIndex(t => t.id === selectedId) ?? -1;
  return (
    <div className="dashboard-grid">
      <div className="metrics-row">
        <MetricCard title="Autonomia" value={dash?.range_km != null ? `${fmt(dash.range_km, 0)} km` : '—'} icon="🔋" />
        <MetricCard title="Chilometri totali" value={dash?.odometer_km != null ? `${fmt(dash.odometer_km, 0)} km` : '—'} icon="🛣️" />
        <MetricCard title="Velocità" value={`${fmt(dash?.speed_kmh ?? 0, 0)} km/h`} icon="🚀" />
        <MetricCard title="Destinazione" value={typeof dash?.navigation === 'string' ? dash.navigation : '—'} icon="🧭" />
      </div>
      <section className="glass-panel full-width">
        <div className="panel-header"><h3>I tuoi percorsi</h3><span className="live-badge">{tracking?.enabled ? 'ATTIVA' : 'IN PAUSA'}</span></div>
        <details className="disclosure"><summary>Registrazione e batteria <span>{tracking?.effective_capacity_kwh != null ? `${fmt(tracking.effective_capacity_kwh)} kWh` : 'Automatico'}</span></summary><div className="disclosure-body"><form onSubmit={save} className="trip-settings">
          <label className="trip-toggle"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} /> Registra automaticamente i viaggi</label>
          <label>Capacità utile · override opzionale (kWh)<input aria-label="Capacità utile batteria in kWh" type="number" min="1" max="200" step="0.1" placeholder="Automatico dalle ricariche" value={capacity} onChange={e => setCapacity(e.target.value)} /></label>
          <button type="submit" className="trip-button" disabled={saving}>{saving ? 'Salvataggio…' : 'Salva'}</button>
        </form>
        <p className="trip-note">{tracking?.status || 'Caricamento stato…'} · Ultimo campione: {tracking?.last_sample_at ? `${date(tracking.last_sample_at)} ${time(tracking.last_sample_at)}` : 'nessuno'}</p>
        <p className="trip-note">Capacità usata per i nuovi viaggi: {tracking?.effective_capacity_kwh != null ? `${fmt(tracking.effective_capacity_kwh)} kWh` : 'in attesa di una ricarica valida'} · {tracking?.capacity_source === 'manual' ? 'Valore manuale' : tracking?.capacity_source === 'charging_estimate' ? `Stima automatica da ${tracking.calibration_sessions} ricariche` : 'Automatico: lascia vuoto il campo manuale e salva'}.</p>
        {tracking?.nominal_capacity_kwh != null && <p className="trip-note">Capacità nominale comunicata da Tesla: {fmt(tracking.nominal_capacity_kwh)} kWh. È mostrata separatamente e non viene usata come capacità utile.</p>}
        <p className="trip-note">La stima automatica richiede una ricarica osservata con aumento di almeno 20 punti percentuali, dati regolari e fine ricarica rilevata. I kWh del viaggio sono stimati dalla variazione di carica: risentono dell’arrotondamento della percentuale e dei servizi di bordo. Una calibrazione valida recupera anche le stime mancanti dei viaggi conclusi con percentuali batteria registrate; le stime già disponibili restano invariate.</p>
        <p className="trip-note">L’app può essere chiusa, ma il server deve restare attivo. Se Render sospende il servizio o Tesla non invia dati, lo storico può essere incompleto. Sono necessari i permessi posizione Tesla per disegnare i percorsi.</p></div></details>
        {error && <p role="alert" className="trip-error">{error}</p>}
        <div className="trip-filters" aria-label="Periodo dello storico">
          {[['today', 'Oggi'], ['week', 'Settimana'], ['month', 'Mese'], ['all', 'Tutti']].map(([id, label]) => <button key={id} type="button" aria-pressed={period === id} className={`trip-button ${period === id ? 'selected' : ''}`} onClick={() => { setPeriod(id); setPage(0); }}>{label}</button>)}
        </div>
        <div className="metrics-row trip-summary">
          <MetricCard title="Viaggi" value={fmt(summary?.trips, 0)} icon="🚗" />
          <MetricCard title="Distanza" value={`${fmt(summary?.distance_km)} km`} icon="🛣️" />
          <MetricCard title="Energia stimata" value={summary?.energy_kwh == null ? 'In attesa' : `≈ ${fmt(summary.energy_kwh)} kWh`} icon="⚡" />
          <MetricCard title="Consumo stimato" value={summary?.consumption_kwh_100km == null ? '—' : `≈ ${fmt(summary.consumption_kwh_100km)} kWh/100 km`} icon="🔋" />
        </div>
        <p className="trip-note">Energia disponibile per {summary?.energy_trips ?? 0} di {summary?.trips ?? 0} viaggi · Costo energia stimato: {summary?.cost == null ? '—' : `≈ ${fmt(summary.cost, 2)} €`} · Tariffe del viaggio.</p>
        {summary?.trips > (summary?.energy_trips ?? 0) && <p className="energy-explanation">{tracking?.effective_capacity_kwh == null ? 'Energia in attesa: serve una ricarica osservata di almeno 20 punti percentuali per calibrare la batteria. Poi recupereremo anche i viaggi con SOC iniziale e finale salvati.' : 'Alcuni viaggi non hanno le percentuali iniziali/finali della batteria. Il dato mancante non è un consumo pari a zero.'}</p>}
        <div className="trip-layout">
          <details className="trip-history" open><summary>Storico viaggi</summary><div className="trip-history-list">
            {!history ? <p>{error ? 'Storico non disponibile: correggi l’errore indicato sopra e riprova.' : 'Caricamento…'}</p> : history.items.length === 0 ? <p>Nessun viaggio registrato nel periodo. Lo storico parte da questo aggiornamento.</p> : history.items.map(trip => (
              <button type="button" key={trip.id} className={`trip-row ${trip.id === selectedId ? 'selected' : ''}`} onClick={() => setSelectedId(trip.id)} aria-pressed={trip.id === selectedId}>
                <strong>{date(trip.started_at)} · {time(trip.started_at)} → {trip.ended_at ? `${date(trip.ended_at) !== date(trip.started_at) ? date(trip.ended_at) + ' ' : ''}${time(trip.ended_at)}` : 'in corso'}</strong>
                <span>{fmt(trip.distance_km)} km · {fmt(trip.duration_minutes, 0)} min · {trip.energy_kwh == null ? 'Energia in attesa' : `≈ ${fmt(trip.energy_kwh)} kWh`}</span>
                <small>{status(trip)}{trip.partial ? ' · Percorso parziale' : ''}</small>
              </button>
            ))}
            <div className="trip-pagination"><button type="button" className="trip-button" disabled={!page} onClick={() => setPage(p => p - 1)}>Precedenti</button><span>{page + 1}</span><button type="button" className="trip-button" disabled={!history || (page + 1) * 50 >= history.total} onClick={() => setPage(p => p + 1)}>Successivi</button></div>
          </div></details>
          <div className="trip-detail" ref={detailPanel}>
            <div className="trip-browser"><button type="button" className="trip-button" aria-label="Viaggio precedente nella lista" disabled={selectedIndex <= 0} onClick={() => setSelectedId(history.items[selectedIndex-1].id)}>←</button><select aria-label="Seleziona viaggio" value={selectedId ?? ''} onChange={e => setSelectedId(Number(e.target.value))}>{(history?.items || []).map(t=><option key={t.id} value={t.id}>{date(t.started_at)} · {time(t.started_at)} · {fmt(t.distance_km)} km</option>)}</select><button type="button" className="trip-button" aria-label="Viaggio successivo nella lista" disabled={selectedIndex < 0 || selectedIndex >= (history?.items.length ?? 0)-1} onClick={() => setSelectedId(history.items[selectedIndex+1].id)}>→</button></div>
            <div className="trip-load-status" role="status">{detailLoading ? 'Aggiornamento percorso…' : ''}</div>
            {detail ? <>
              <h4 className="trip-detail-title">{date(detail.started_at)} · {time(detail.started_at)} — {detail.ended_at ? time(detail.ended_at) : 'in corso'}</h4>
              {detail.partial && <p className="trip-note">Percorso parziale: partenza già in marcia o interruzione della raccolta. La mappa unisce solo i punti ricevuti.</p>}
              <div className={detailLoading && detail.id !== selectedId ? "trip-detail-loading" : ""}><TripMap tripId={detail.id} points={detail.points} /></div>
              <div className="trip-detail-metrics">
                <span><strong>{fmt(detail.distance_km)} km</strong><small>{detail.distance_source === 'gps_estimate' ? 'Distanza GPS stimata' : 'Distanza da odometro'}</small></span>
                <span><strong>{fmt(detail.duration_minutes, 0)} min</strong><small>Durata registrata</small></span>
                <span><strong>{fmt(detail.start_battery, 0)}% → {fmt(detail.end_battery, 0)}%</strong><small>Batteria</small></span>
                <span><strong>{detail.energy_kwh == null ? 'In attesa' : `≈ ${fmt(detail.energy_kwh)} kWh`}</strong><small>Energia netta stimata</small></span>
                <span><strong>{detail.consumption_kwh_100km == null ? '—' : `≈ ${fmt(detail.consumption_kwh_100km)} kWh/100 km`}</strong><small>Consumo stimato</small></span>
                <span><strong>{detail.energy_cost == null ? '—' : `≈ ${fmt(detail.energy_cost, 2)} €`}</strong><small>Costo energia stimato</small></span>
              </div>
              {detail.energy_kwh == null && <p className="energy-explanation">{detail.energy_missing_reason || 'Energia non disponibile: manca la capacità calibrata o il SOC iniziale/finale.'}</p>}
              <TripContext key={detail.id} vin={vin} tripId={detail.id}/>
              <details className="disclosure"><summary>Dettagli del viaggio</summary><div className="disclosure-body"><p className="trip-note">Capacità del viaggio: {fmt(detail.capacity_kwh)} kWh · {detail.capacity_source === 'charging_estimate_retrospective' ? 'stima recuperata con calibrazione successiva' : detail.capacity_source === 'manual_retrospective' ? 'stima recuperata con capacità manuale' : detail.capacity_source === 'charging_estimate' ? 'stima automatica dalle ricariche' : detail.capacity_source === 'manual' ? 'valore manuale' : 'non disponibile'}</p>
              <p className="trip-note">{detail.points.length} campioni · Orari Europe/Rome · Verde: primo punto · Arancione: ultimo punto</p>
              {detail.destination && <p>Destinazione: {detail.destination}</p>}</div></details>
            </> : <div className="empty-state-box"><p>{selectedId ? 'Caricamento percorso…' : 'Seleziona un viaggio per vedere la mappa e i consumi.'}</p></div>}
          </div>
        </div>
      </section>
    </div>
  );
}
