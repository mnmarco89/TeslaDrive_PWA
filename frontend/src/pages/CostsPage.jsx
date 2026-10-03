import { useEffect, useState } from 'react';
import { api } from '../api/client';
import MetricCard from '../components/MetricCard';

const fmt = (v, digits = 2) => v == null ? '—' : Number(v).toLocaleString('it-IT', { minimumFractionDigits: 0, maximumFractionDigits: digits });
const money = v => v == null ? '—' : `≈ ${fmt(v)} €`;
const dateTime = v => v ? new Date(v).toLocaleString('it-IT', { timeZone: 'Europe/Rome', dateStyle: 'short', timeStyle: 'short' }) : '—';
const periods = [['today', 'Oggi'], ['week', 'Settimana'], ['month', 'Mese'], ['all', 'Tutti']];

export default function CostsPage({ vin, settings, setSettings, onSave }) {
  const [period, setPeriod] = useState('all');
  const [summary, setSummary] = useState(null);
  const [rates, setRates] = useState(null);
  const [historyPage, setHistoryPage] = useState(0);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let busy = false;
    const load = async () => {
      if (busy) return;
      busy = true;
      try {
        const [totals, history] = await Promise.all([
          api(`/api/costs/summary/${vin}?period=${period}`, { signal: controller.signal }),
          api(`/api/costs/rates?vin=${vin}&offset=${historyPage * 50}`, { signal: controller.signal }),
        ]);
        if (controller.signal.aborted) return;
        setSummary(totals); setRates(history); setError('');
      } catch (err) { if (err.name !== 'AbortError') setError(err.message); }
      finally { busy = false; }
    };
    setSummary(null); load();
    const timer = setInterval(load, 15000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [vin, period, historyPage, revision]);
  const save = async event => {
    event.preventDefault(); setSaving(true);
    try { if (await onSave()) setRevision(r => r + 1); }
    finally { setSaving(false); }
  };
  return <div className="dashboard-grid">
    <section className="glass-panel full-width">
      <div className="panel-header"><h3>Tariffe attuali</h3><span className="live-badge">AUTO</span></div>
      <div className="cost-price-grid">
        <div><span className="metric-title">Elettricità · tariffa fissa</span><strong>{fmt(settings?.electricity, 3)} €/kWh</strong><small>€/kWh applicati ai nuovi viaggi.</small></div>
        <div><span className="metric-title">Gasolio self-service · MIMIT</span><strong>{fmt(summary?.fuel_price?.diesel, 3)} €/L</strong><small>Ultimo rilevamento: {dateTime(summary?.fuel_price?.updated_at)}</small>
          {summary?.fuel_price?.station && <small>{summary.fuel_price.station} · {summary.fuel_price.city} · Dataset {summary.fuel_price.dataset_date || '—'}</small>}</div>
      </div>
      <details className="disclosure"><summary>Fonte prezzi e consumo diesel</summary><div className="disclosure-body"><p className="trip-note">Il diesel usa i dati ufficiali MIMIT, pubblicati ogni giorno. Circa ogni ora, con GPS disponibile, viene scelto il distributore più vicino entro 10 km con gasolio self-service. Le variazioni sono conservate automaticamente. Il listino giornaliero è un riferimento, non un prezzo garantito in tempo reale.</p>
      {summary?.fuel_price?.error && <p className="trip-note">{summary.fuel_price.error}</p>}
      {!summary?.fuel_price?.diesel && <p className="trip-note">In attesa del primo prezzo diesel automatico. Non viene usato un prezzo predefinito.</p>}
      {settings && <form onSubmit={save} className="settings-form cost-consumption-form">
        <div className="input-group"><label htmlFor="diesel-efficiency">Consumo dell’auto diesel di confronto (km/L)</label><input id="diesel-efficiency" type="number" min="0.1" max="100" step="0.1" required value={settings.diesel_km_l} onChange={event => setSettings({ ...settings, diesel_km_l: event.target.value })} /></div>
        <button type="submit" className="btn-save" disabled={saving}>{saving ? 'Salvataggio…' : 'Salva consumo di confronto'}</button>
      </form>}
      <p className="trip-note">Un cambiamento del consumo diesel si applica ai nuovi viaggi; i confronti già registrati mantengono i loro parametri.</p></div></details>
    </section>
    <section className="glass-panel full-width">
      <div className="panel-header"><h3>Il costo dei tuoi viaggi</h3></div>
      <div className="trip-filters">{periods.map(([id, label]) => <button key={id} type="button" className={`trip-button ${period === id ? 'selected' : ''}`} aria-pressed={period === id} onClick={() => setPeriod(id)}>{label}</button>)}</div>
      {error && <p role="alert" className="trip-error">{error}</p>}
      <div className="metrics-row">
        <MetricCard title="Costo elettrico stimato" value={money(summary?.electricity_cost)} icon="⚡" />
        <MetricCard title="Avresti speso in diesel" value={money(summary?.diesel_cost)} icon="⛽" />
        <MetricCard title="Risparmio stimato" value={money(summary?.saving)} icon="💶" />
      </div>
      {summary?.missing_energy_trips > 0 && <p className="energy-explanation">{summary?.battery?.effective_capacity_kwh == null ? 'Costo elettrico in attesa della calibrazione automatica: serve una ricarica osservata di almeno 20 punti percentuali. Nessun prezzo va inserito a mano.' : `${summary.missing_energy_trips} viaggi senza dati batteria sufficienti.`}</p>}
      <p className="trip-note">Stime sui viaggi registrati · Risparmio sugli stessi {fmt(summary?.comparable_distance_km, 1)} km.</p><details className="disclosure"><summary>Copertura e metodo di calcolo</summary><div className="disclosure-body"><div className="cost-coverage">
        <p>Elettrico: {fmt(summary?.electricity_distance_km, 1)} km · {summary?.electricity_trips ?? '—'} viaggi con energia e tariffa disponibili.</p>
        <p>Diesel: {fmt(summary?.diesel_distance_km, 1)} km · {summary?.diesel_trips ?? '—'} viaggi con prezzo storico disponibile.</p>
        <p>Differenza calcolata sugli stessi {fmt(summary?.comparable_distance_km, 1)} km confrontabili: elettrico {money(summary?.comparable_electricity_cost)}, diesel {money(summary?.comparable_diesel_cost)}. Un valore negativo indica che il diesel sarebbe costato meno.</p>
      </div>
      <p className="trip-note">{summary?.trips ?? '—'} viaggi terminati · {fmt(summary?.distance_km, 1)} km registrati · {fmt(summary?.energy_kwh, 1)} kWh stimati disponibili. {summary?.partial_trips ?? 0} percorsi parziali; {summary?.missing_distance_trips ?? 0} viaggi senza distanza utilizzabile. I viaggi in corso non rientrano nei totali.</p>
      <p className="trip-note">Il costo elettrico usa i kWh stimati dal consumo della batteria e la tariffa €/kWh del viaggio. Non è un totale delle bollette o delle ricariche pagate e non include le perdite di ricarica. Diesel = km ÷ km/L × prezzo €/L del periodo.</p>
      <p className="trip-note">I totali disponibili possono coprire distanze diverse; la differenza usa solo i viaggi confrontabili. Lo storico automatico del diesel parte da questo aggiornamento: i prezzi mancanti dei viaggi precedenti restano sconosciuti.</p></div></details>
      <h4>Riepilogo mensile</h4>
      <div className="cost-table-scroll"><table className="cost-table"><thead><tr><th>Mese</th><th>Km registrati</th><th>Elettrico stimato</th><th>Diesel equivalente</th><th>Differenza sugli stessi km</th></tr></thead><tbody>
        {(summary?.months || []).map(row => <tr key={row.month}><td data-label="Mese">{row.month.split('-').reverse().join('/')}</td><td data-label="Km registrati">{fmt(row.distance_km, 1)}</td><td data-label="Elettrico stimato">{money(row.electricity_cost)}<small>su {fmt(row.electricity_distance_km, 1)} km</small></td><td data-label="Diesel equivalente">{money(row.diesel_cost)}<small>su {fmt(row.diesel_distance_km, 1)} km</small></td><td data-label="Risparmio sugli stessi km">{money(row.saving)}<small>su {fmt(row.comparable_distance_km, 1)} km</small></td></tr>)}
        {summary && !summary.months.length && <tr><td colSpan="5">Nessun viaggio terminato nel periodo.</td></tr>}
      </tbody></table></div>
    </section>
    <section className="glass-panel full-width">
      <details className="disclosure"><summary>Storico dei prezzi usati</summary><div className="disclosure-body">
      <p className="trip-note">Ogni rilevamento che cambia il prezzo diesel crea una nuova tariffa per quel veicolo. Gli orari sono Europe/Rome; le tariffe si applicano dal momento rilevato, senza riscrivere i costi precedenti.</p>
      <div className="cost-table-scroll"><table className="cost-table"><thead><tr><th>Dal</th><th>Elettricità €/kWh</th><th>Diesel €/L</th><th>Consumo km/L</th><th>Origine</th></tr></thead><tbody>
        {(rates?.items || []).map(rate => <tr key={rate.id}><td data-label="Dal">{dateTime(rate.effective_from)}</td><td data-label="Elettricità €/kWh">{fmt(rate.electricity, 3)}</td><td data-label="Diesel €/L">{fmt(rate.diesel, 3)}</td><td data-label="Consumo km/L">{fmt(rate.diesel_km_l, 1)}</td><td data-label="Origine">{rate.source === 'gps_auto' ? `MIMIT automatico · ${rate.station || ''}` : rate.source === 'initial' ? 'Configurazione iniziale' : 'Parametri configurati'}</td></tr>)}
        {rates && !rates.items.length && <tr><td colSpan="5">In attesa dei primi rilevamenti.</td></tr>}
      </tbody></table></div>
      <div className="trip-pagination"><button type="button" className="trip-button" disabled={!historyPage} onClick={() => setHistoryPage(p => p - 1)}>Precedenti</button><span>{historyPage + 1}</span><button type="button" className="trip-button" disabled={!rates || (historyPage + 1) * 50 >= rates.total} onClick={() => setHistoryPage(p => p + 1)}>Successivi</button></div>
    </div></details></section>
  </div>;
}
