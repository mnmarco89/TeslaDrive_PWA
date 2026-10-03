import { useEffect, useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
const GOAL = 22000;
const euro = n => Number(n).toLocaleString('it-IT', { style:'currency', currency:'EUR', maximumFractionDigits:2 });
const fmt = n => Number(n || 0).toLocaleString('it-IT', { maximumFractionDigits:1 });
export default function SavingsPage({vin,onNavigate}) {
 const [summary,setSummary]=useState(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let busy=false;
  const load=async()=>{
   if(busy)return;busy=true;
   try {const result=await api(`/api/costs/summary/${vin}?period=all`,{signal:controller.signal});if(!controller.signal.aborted){setSummary(result);setError('');}}
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
   <div className="panel-header"><div><span className="label-top">IL TUO OBIETTIVO</span><h2>Ebreo Status</h2></div><span className="savings-emblem"><Icon name="wallet"/></span></div>
   <p className="savings-caption">Il risparmio stimato, viaggio dopo viaggio.</p>
   {error&&<div className="trip-error" role="alert">{error}<button type="button" className="trip-button" onClick={()=>setRevision(r=>r+1)}>Riprova</button>{summary&&<small>Mostro l’ultimo totale ricevuto.</small>}</div>}
   <div className="savings-amount"><span>Risparmio totale stimato</span><strong>{available?euro(saving):'In attesa dei dati'}</strong><small>su tutti i percorsi confrontabili del veicolo selezionato</small></div>
   <div className="savings-progress-heading"><strong>{available?`${fmt(progress)}%`:'—'}</strong><span>Obiettivo <b>{euro(GOAL)}</b></span></div>
   <div className="savings-track" role={available?'progressbar':undefined} aria-label="Risparmio verso l’obiettivo di 22.000 euro" aria-valuemin={available?0:undefined} aria-valuemax={available?GOAL:undefined} aria-valuenow={available?Math.min(GOAL,Math.max(0,saving)):undefined} aria-valuetext={available?`${euro(saving)} di risparmio stimato, obiettivo ${euro(GOAL)}`:undefined}><div className="savings-fill" style={{width:`${progress}%`}}/></div>
   <div className="savings-scale"><span>0 €</span><span>22.000 €</span></div>
   <div className="savings-milestones" aria-label="Traguardi di risparmio">{[5500,11000,16500].map(n=><span key={n} className={available&&saving>=n?'achieved':''}>{saving>=n&&available?'✓ ':''}{euro(n)}</span>)}</div>
   {available?<p className="savings-remaining" role="status">{saving>=GOAL?'Obiettivo raggiunto! Il risparmio continua a crescere.':<>Mancano <strong>{euro(Math.max(0,GOAL-saving))}</strong> all’obiettivo.</>}</p>:<p className="energy-explanation" role="status">{!summary&&!error?'Caricamento risparmio…':summary?.missing_energy_trips>0?'La barra si riempirà quando sarà disponibile anche il costo elettrico stimato dei percorsi.':'In attesa di percorsi con costo elettrico e prezzo diesel disponibili.'}</p>}
   {available&&saving<0&&<p className="trip-note">Al momento il costo elettrico stimato supera quello diesel: il saldo è negativo e la barra resta a zero.</p>}
  </section>
  <section className="glass-panel savings-comparison"><div className="panel-header"><h3>Da dove arriva il risparmio</h3><button type="button" className="trip-button" onClick={()=>onNavigate('costi')}>Apri Costi →</button></div>
   <div className="savings-costs"><div><span>Diesel equivalente</span><strong>{summary?.comparable_diesel_cost==null?'—':euro(summary.comparable_diesel_cost)}</strong></div><div><span>Costo elettrico stimato</span><strong>{summary?.comparable_electricity_cost==null?'—':euro(summary.comparable_electricity_cost)}</strong></div></div>
   <p className="trip-note">Confronto sugli stessi {fmt(summary?.comparable_distance_km)} km · {summary?.comparable_trips??0} percorsi confrontabili.</p>
   {missing>0&&<p className="energy-explanation">{missing} {missing===1?'percorso ancora escluso':'percorsi ancora esclusi'} dal confronto. Entreranno nel totale quando energia e tariffe saranno disponibili.</p>}
   <details className="disclosure"><summary>Come si riempie la barra</summary><div className="disclosure-body"><p className="trip-note">Il totale è lo stesso Risparmio stimato della sezione Costi, selezionando Tutti. Usa le tariffe storiche registrate e sottrae il costo elettrico stimato dal diesel equivalente sugli stessi percorsi. Il costo elettrico non viene considerato zero se mancano i dati.</p><p className="trip-note">La barra va da 0 a 22.000 €; il totale continua a essere mostrato anche oltre l’obiettivo. Le stime possono aumentare o diminuire quando arrivano nuovi dati. Si tratta di un confronto energetico, non di denaro incassato: non comprende acquisto, manutenzione, assicurazione o perdite di ricarica.</p></div></details>
  </section>
 </div>;
}
