import { useEffect, useState } from 'react';
import { api } from '../api/client';
import JewishSymbol from '../components/JewishSymbol';
const GOAL = 22000;
const euro = n => Number(n).toLocaleString('it-IT', { style:'currency', currency:'EUR', maximumFractionDigits:2, useGrouping:'always' });
const fmt = n => Number(n || 0).toLocaleString('it-IT', { maximumFractionDigits:1 });
export default function SavingsPage({vin,onNavigate}) {
 const [summary,setSummary]=useState(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 const [consumption,setConsumption]=useState(null),[savingForm,setSavingForm]=useState(false);
 const saveBaseline=async event=>{event.preventDefault();setSavingForm(true);try{const d=await api(`/api/costs/savings/${vin}/baseline`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(consumption)});setSummary(d);setConsumption(null);setError('');}catch(e){setError(e.message);}finally{setSavingForm(false);}};
 useEffect(()=>{
  const controller=new AbortController();let busy=false;
  const load=async()=>{
   if(busy)return;busy=true;
   try {const result=await api(`/api/costs/savings/${vin}`,{signal:controller.signal});if(!controller.signal.aborted){setSummary(result);setError('');}}
   catch(e){if(e.name!=='AbortError')setError(e.message);}
   finally{busy=false;}
  };
  load();const timer=setInterval(load,15000);return()=>{controller.abort();clearInterval(timer);};
 },[vin,revision]);
 const available=typeof summary?.saving==='number'&&Number.isFinite(summary.saving);
 const saving=available?summary.saving:0;
 const progress=Math.min(100,Math.max(0,saving/GOAL*100));
 const missing=Math.max(0,(summary?.trips||0)-(summary?.comparable_trips||0));
 return <div className="dashboard-grid savings-page">
  <section className="glass-panel savings-goal">
   <div className="panel-header"><div><span className="label-top">IL TUO OBIETTIVO</span><h2>Ebreo Status</h2><span className="savings-hebrew" lang="he" dir="rtl" aria-hidden="true">חיסכון</span></div><span className="savings-emblem"><JewishSymbol/></span></div>
   <p className="savings-caption">Il risparmio stimato, viaggio dopo viaggio.</p>
   {error&&<div className="trip-error" role="alert">{error}<button type="button" className="trip-button" onClick={()=>setRevision(r=>r+1)}>Riprova</button>{summary&&<small>Mostro l’ultimo totale ricevuto.</small>}</div>}
   <div className="savings-amount"><span>Risparmio totale stimato</span><strong>{available?euro(saving):'In attesa dei dati'}</strong><small>stima iniziale + risparmio dei nuovi percorsi confrontabili</small></div>
   <div className="savings-progress-heading"><strong>{available?`${fmt(progress)}%`:'—'}</strong><span>Obiettivo <b>{euro(GOAL)}</b></span></div>
   <div className="savings-progress-stage"><div className="savings-track" role={available?'progressbar':undefined} aria-label="Risparmio verso l’obiettivo di 22.000 euro" aria-valuemin={available?0:undefined} aria-valuemax={available?GOAL:undefined} aria-valuenow={available?Math.min(GOAL,Math.max(0,saving)):undefined} aria-valuetext={available?`${euro(saving)} di risparmio stimato, obiettivo ${euro(GOAL)}`:undefined}><div className="savings-fill" style={{width:`${progress}%`}}/></div>{available&&<span className="savings-pointer" style={{left:`clamp(26px, ${progress}%, calc(100% - 26px))`}}><JewishSymbol name="menorah"/></span>}</div>
   <div className="savings-scale"><span>0 €</span><span>22.000 €</span></div>
   <div className="savings-milestones" aria-label="Traguardi di risparmio">{[5500,11000,16500].map(n=><span key={n} className={available&&saving>=n?'achieved':''}>{saving>=n&&available?'✓ ':''}{euro(n)}</span>)}</div>
   {available?<p className="savings-remaining" role="status">{saving>=GOAL?'Obiettivo raggiunto! Il risparmio continua a crescere.':<>Mancano <strong>{euro(Math.max(0,GOAL-saving))}</strong> all’obiettivo.</>}</p>:<p className="energy-explanation" role="status">{!summary&&!error?'Caricamento risparmio…':summary?.missing_energy_trips>0?'La barra si riempirà quando sarà disponibile anche il costo elettrico stimato dei percorsi.':'In attesa di percorsi con costo elettrico e prezzo diesel disponibili.'}</p>}
   {available&&saving<0&&<p className="trip-note">Al momento il costo elettrico stimato supera quello diesel: il saldo è negativo e la barra resta a zero.</p>}
  </section>
  <section className="glass-panel savings-comparison"><div className="panel-header"><h3>Da dove arriva il risparmio</h3><button type="button" className="trip-button" onClick={()=>onNavigate('costi')}>Apri Costi →</button></div>
   <div className="savings-costs"><div><span>Diesel equivalente</span><strong>{summary?.comparable_diesel_cost==null?'—':euro(summary.comparable_diesel_cost)}</strong></div><div><span>Costo elettrico stimato</span><strong>{summary?.comparable_electricity_cost==null?'—':euro(summary.comparable_electricity_cost)}</strong></div></div>
   <p className="trip-note">Confronto sugli stessi {fmt(summary?.comparable_distance_km)} km · stima storica{summary?.historical?` + ${summary.comparable_trips} nuovi percorsi confrontabili`:" assente"}.</p>
   {missing>0&&<p className="energy-explanation">{missing} {missing===1?'percorso ancora escluso':'percorsi ancora esclusi'} dal confronto. Entreranno nel totale quando energia e tariffe saranno disponibili.</p>}
   {summary?.historical&&<div className="historical-estimate"><div><span className="label-top">PUNTO DI PARTENZA</span><h3>{fmt(summary.historical.distance_km)} km già percorsi</h3></div><div className="historical-split"><span>Stima iniziale <strong>{euro(summary.historical.saving)}</strong></span><span>Nuovi percorsi <strong>{summary.new_saving==null?'In attesa':euro(summary.new_saving)}</strong></span></div><p className="trip-note">Stima provvisoria su {fmt(summary.historical.electric_kwh_100km)} kWh/100 km e {fmt(summary.historical.diesel_km_l)} km/L. Medie storiche: {summary.historical.electricity_price.toLocaleString('it-IT',{maximumFractionDigits:3})} €/kWh e {summary.historical.diesel_price.toLocaleString('it-IT',{maximumFractionDigits:3})} €/L.</p><details className="disclosure"><summary>Verifica i consumi della stima iniziale</summary><form onSubmit={saveBaseline} className="settings-form"><label className="input-group">Consumo elettrico medio (kWh/100 km)<input aria-label="Consumo elettrico storico" type="number" min="1" max="100" step="0.1" required value={consumption?.electric_kwh_100km??summary.historical.electric_kwh_100km} onChange={e=>setConsumption(c=>({...c,electric_kwh_100km:Number(e.target.value),diesel_km_l:c?.diesel_km_l??summary.historical.diesel_km_l}))}/></label><label className="input-group">Consumo diesel di confronto (km/L)<input aria-label="Consumo diesel storico" type="number" min="1" max="100" step="0.1" required value={consumption?.diesel_km_l??summary.historical.diesel_km_l} onChange={e=>setConsumption(c=>({...c,diesel_km_l:Number(e.target.value),electric_kwh_100km:c?.electric_kwh_100km??summary.historical.electric_kwh_100km}))}/></label><button className="trip-button" disabled={savingForm||!consumption}>{savingForm?'Salvataggio…':'Aggiorna stima'}</button></form></details></div>}
   <details className="disclosure"><summary>Come si riempie la barra</summary><div className="disclosure-body"><p className="trip-note">Il totale comprende la stima iniziale sui 32.517 km indicati e il risparmio dei viaggi iniziati dopo il 3 ottobre 2026 alle 20:20 (ora italiana). I percorsi precedenti sono già compresi nella stima iniziale e non vengono aggiunti di nuovo. Per i nuovi viaggi uso gli stessi calcoli e le tariffe storiche di Costi. La stima iniziale resta distinta dai consumi ricavati dai dati Tesla. Il costo elettrico non viene considerato zero se mancano i dati.</p><p className="trip-note">La barra va da 0 a 22.000 €; il totale continua a essere mostrato anche oltre l’obiettivo. Le stime possono aumentare o diminuire quando arrivano nuovi dati. Si tratta di un confronto energetico, non di denaro incassato: non comprende acquisto, manutenzione, assicurazione o perdite di ricarica.</p></div></details>
  </section>
 </div>;
}
