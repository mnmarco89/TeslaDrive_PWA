import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import MetricCard from '../components/MetricCard';
import VehicleDiagram, { doorState } from '../components/VehicleDiagram';
const fmt = (v,d=1) => v == null ? '—' : Number(v).toLocaleString('it-IT',{maximumFractionDigits:d});
const bool = (v,on,off) => v == null ? 'Non disponibile' : v ? on : off;
const actions = [
 ['lock','Blocca','lock'], ['unlock','Sblocca','unlock'],
 ['front_trunk','Bagagliaio anteriore','car'], ['rear_trunk','Bagagliaio posteriore','car'],
 ['climate_on','Accendi clima','climate'], ['climate_off','Spegni clima','climate'],
 ['charge_port_open','Apri presa','charge'], ['charge_port_close','Chiudi presa','charge'],
];
const confirmations = {unlock:'Sbloccare le serrature della tua Tesla?',front_trunk:'Azionare il bagagliaio anteriore?',rear_trunk:'Azionare il bagagliaio posteriore?'};
export default function HomePage({ vin, dash, profile, profileError, onRefresh, onNavigate }) {
 const [busy,setBusy]=useState(null), [pending,setPending]=useState(null), [feedback,setFeedback]=useState(null);
 const refreshTimer=useRef(null), mounted=useRef(true);
 useEffect(() => { mounted.current=true; return () => { mounted.current=false; clearTimeout(refreshTimer.current); }; },[]);
 const command = async action => {
  if(busy) return;
  clearTimeout(refreshTimer.current);
  setPending(null); setBusy(action); setFeedback(null);
  try {
   await api(`/api/vehicles/${vin}/controls`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
   if(!mounted.current) return;
   setFeedback({ok:true,text:'Comando confermato da Tesla. Stato in aggiornamento…'});
   refreshTimer.current=setTimeout(async () => {
    if(!mounted.current) return;
    try { await onRefresh(); if(mounted.current) setFeedback({ok:true,text:'Comando confermato. Dati aggiornati.'}); }
    catch { if(mounted.current) setFeedback({ok:true,text:'Comando confermato. Stato temporaneamente non aggiornabile.'}); }
   },3000);
  } catch(err) { if(mounted.current) setFeedback({ok:false,text:err.message}); }
  finally { if(mounted.current) setBusy(null); }
 };
 const doors=dash?.doors || {};
 const name=profile?.first_name || profile?.name?.split(' ')[0];
 const sampleAt=dash?.vehicle_timestamp ? new Date(dash.vehicle_timestamp) : null;
 const old=sampleAt && Date.now()-sampleAt.getTime()>180000;
 return <div className="dashboard-grid home-page">
  <div className="home-welcome"><div><span className="label-top">IL TUO SPAZIO TESLA</span><h2>{name ? `Ciao, ${name}` : 'Bentornato'}<span className="welcome-dot">.</span></h2><p>La tua auto, tutto a portata di mano.</p></div><button className="trip-button" onClick={() => onRefresh().catch(err => setFeedback({ok:false,text:err.message}))}>Aggiorna</button></div>
  <div className="home-grid">
   <section className="glass-panel vehicle-overview"><div className="panel-header"><h3>La tua Tesla</h3><span className={`live-badge ${dash?.locked == null ? 'neutral-badge' : dash.locked ? '' : 'warning-badge'}`}>{bool(dash?.locked,'BLOCCATA','SBLOCCATA')}</span></div>
    <VehicleDiagram doors={doors}/>
    <p className="home-status-time">{sampleAt ? `Dati auto: ${sampleAt.toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'})}${old ? ' · Da aggiornare' : ''}` : 'In attesa dei dati dell’auto'}</p>
    <details className="disclosure"><summary>Stato portiere e bagagliai</summary><dl className="door-list">{[['df','Anteriore sinistra'],['pf','Anteriore destra'],['dr','Posteriore sinistra'],['pr','Posteriore destra'],['ft','Bagagliaio anteriore'],['rt','Bagagliaio posteriore']].map(([key,label])=><div key={key}><dt>{label}</dt><dd className={doors[key] != null && doors[key] !== 0 ? 'is-open' : ''}>{doorState(doors[key])}</dd></div>)}</dl></details>
   </section>
   <section className="glass-panel home-controls"><div className="panel-header"><h3>Comandi rapidi</h3><span className="label-top">REMOTO</span></div>
    <div className="quick-actions">{actions.map(([action,label,icon]) => <button key={action} type="button" className={`quick-action ${action==='unlock'?'accent-action':''}`} disabled={!!busy || !vin} onClick={() => confirmations[action] ? setPending(action) : command(action)}><Icon name={icon}/><span>{busy===action?'Invio…':label}</span></button>)}</div>
    {pending && <div className="command-confirm" role="group" aria-label="Conferma comando"><p>{confirmations[pending]}</p><div><button className="trip-button" disabled={!!busy} onClick={() => command(pending)}>Conferma</button><button className="trip-button" onClick={() => setPending(null)}>Annulla</button></div></div>}
    {feedback && <p className={feedback.ok?'command-feedback':'trip-error'} role={feedback.ok?'status':'alert'}>{feedback.text}</p>}
    <p className="trip-note">Blocca e Sblocca comandano le serrature. Lo stato delle portiere indica se sono fisicamente aperte.</p>
   </section>
  </div>
  <div className="metrics-row home-metrics">
   <MetricCard title="Autonomia" value={`${fmt(dash?.range_km,0)} km`} icon="🔋"/>
   <MetricCard title="Chilometri totali" value={`${fmt(dash?.odometer_km,0)} km`} icon="🛣️"/>
   <MetricCard title="Temperatura interna" value={`${fmt(dash?.inside_temp)} °C`} icon="temp"/>
   <MetricCard title="Temperatura esterna" value={`${fmt(dash?.outside_temp)} °C`} icon="temp"/>
  </div>
  <div className="home-secondary-grid">
   <section className="glass-panel"><div className="panel-header"><h3>Pneumatici</h3><span className="metric-title">bar · ultimo rilevamento</span></div><div className="tire-grid">{[['fl','Anteriore SX'],['fr','Anteriore DX'],['rl','Posteriore SX'],['rr','Posteriore DX']].map(([key,label])=><div key={key}><span>{label}</span><strong>{fmt(dash?.tpms?.[key],2)}</strong></div>)}</div></section>
   <section className="glass-panel"><div className="panel-header"><h3>A colpo d’occhio</h3></div><dl className="door-list"><div><dt>Climatizzazione</dt><dd>{bool(dash?.is_climate_on,'Accesa','Spenta')}</dd></div><div><dt>Sentinella</dt><dd>{bool(dash?.sentry_mode,'Attiva','Spenta')}</dd></div><div><dt>Limite ricarica</dt><dd>{fmt(dash?.charge_limit_soc,0)}%</dd></div><div><dt>Software</dt><dd>{dash?.software_version || '—'}</dd></div></dl><button className="home-charge-link" onClick={() => onNavigate('ricarica')}>Vai alla ricarica →</button></section>
  </div>
  <details className="glass-panel home-profile disclosure"><summary>Il tuo profilo Tesla</summary><div className="disclosure-body">{profile?.available ? <dl className="door-list"><div><dt>Nome</dt><dd>{profile.name || '—'}</dd></div><div><dt>Email</dt><dd>{profile.email || '—'}</dd></div></dl> : <p className="trip-note">{profile?.message || profileError || 'Caricamento profilo…'}</p>}<a href="/auth/tesla/start" className="reconnect-link">Aggiorna autorizzazioni Tesla</a><p className="trip-note">Foto e dati dipendono dalle informazioni condivise dal tuo account. I comandi richiedono il permesso di controllo e la chiave virtuale dell’app.</p></div></details>
 </div>;
}
