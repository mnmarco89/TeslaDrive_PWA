import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import VehicleLocation from '../components/VehicleLocation';
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
 return <div className="dashboard-grid home-page home-refreshed">
  <div className="home-welcome"><div><span className="label-top">IL TUO SPAZIO TESLA</span><h2>{name ? `Ciao, ${name}` : 'Bentornato'}<span className="welcome-dot">.</span></h2></div><button className="trip-button" onClick={() => onRefresh().catch(err => setFeedback({ok:false,text:err.message}))}>Aggiorna</button></div>
  <section className="glass-panel home-cockpit">
   <div className="vehicle-overview home-car-scene">
    <div className="panel-header"><h3>La tua Tesla</h3><span className={`live-badge ${dash?.locked == null ? 'neutral-badge' : dash.locked ? '' : 'warning-badge'}`}>{bool(dash?.locked,'BLOCCATA','SBLOCCATA')}</span></div>
    <div className="home-car-summary"><VehicleDiagram doors={doors}/><div className="home-range"><span>Autonomia</span><strong>{fmt(dash?.range_km,0)}<small> km</small></strong><div className="home-battery-track"><i style={{width:`${Math.min(100,Math.max(0,dash?.battery??0))}%`}}/></div><span>{fmt(dash?.battery,0)}% batteria · limite {fmt(dash?.charge_limit_soc,0)}%</span><button className="home-charge-link" onClick={() => onNavigate('ricarica')}>Gestisci ricarica →</button></div></div>
    <p className="home-status-time">{sampleAt ? `Dati auto: ${sampleAt.toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit'})}${old ? ' · Da aggiornare' : ''}` : 'In attesa dei dati dell’auto'}</p>
   </div>
   <VehicleLocation vin={vin} dash={dash}/>
  </section>
  <section className="glass-panel home-command-deck"><div className="panel-header"><h3>A portata di mano</h3><span className="label-top">COMANDI</span></div>
   <div className="quick-actions home-primary-actions">{actions.filter(([a])=>['lock','unlock','rear_trunk','climate_on'].includes(a)).map(([action,label,icon])=><button key={action} type="button" className={`quick-action ${action==='unlock'?'accent-action':''}`} disabled={!!busy||!vin} onClick={()=>confirmations[action]?setPending(action):command(action)}><Icon name={icon}/><span>{busy===action?'Invio…':label}</span></button>)}</div>
   <details className="disclosure home-extra-controls"><summary><span className="expand-icon"><Icon name="car"/></span><span className="expand-copy"><strong>Altri comandi</strong><small>Bagagliaio anteriore, clima e presa</small></span><span className="expand-indicator" aria-hidden="true"/></summary><div className="quick-actions">{actions.filter(([a])=>!['lock','unlock','rear_trunk','climate_on'].includes(a)).map(([action,label,icon])=><button key={action} className="quick-action" disabled={!!busy||!vin} onClick={()=>confirmations[action]?setPending(action):command(action)}><Icon name={icon}/><span>{busy===action?'Invio…':label}</span></button>)}</div></details>
   {pending&&<div className="command-confirm" role="group" aria-label="Conferma comando"><p>{confirmations[pending]}</p><div><button className="trip-button" disabled={!!busy} onClick={()=>command(pending)}>Conferma</button><button className="trip-button" onClick={()=>setPending(null)}>Annulla</button></div></div>}
   {feedback&&<p className={feedback.ok?'command-feedback':'trip-error'} role={feedback.ok?'status':'alert'}>{feedback.text}</p>}
  </section>
  <div className="home-insight-strip"><div><span>Chilometri totali</span><strong>{fmt(dash?.odometer_km,0)} <small>km</small></strong></div><div><span>Abitacolo</span><strong>{fmt(dash?.inside_temp)} <small>°C</small></strong></div><div><span>Esterno</span><strong>{fmt(dash?.outside_temp)} <small>°C</small></strong></div></div>
  <section className="glass-panel home-details-group">
   <details className="disclosure"><summary><span className="expand-icon"><Icon name="lock"/></span><span className="expand-copy"><strong>Portiere e bagagliai</strong><small>Controlla cosa è aperto</small></span><span className="expand-indicator" aria-hidden="true"/></summary><dl className="door-list">{[['df','Anteriore sinistra'],['pf','Anteriore destra'],['dr','Posteriore sinistra'],['pr','Posteriore destra'],['ft','Bagagliaio anteriore'],['rt','Bagagliaio posteriore']].map(([key,label])=><div key={key}><dt>{label}</dt><dd className={doors[key]!=null&&doors[key]!==0?'is-open':''}>{doorState(doors[key])}</dd></div>)}</dl><p className="trip-note">Blocca e Sblocca comandano le serrature. Qui vedi se le portiere sono fisicamente aperte.</p></details>
   <details className="disclosure"><summary><span className="expand-icon"><Icon name="car"/></span><span className="expand-copy"><strong>Pneumatici e stato del veicolo</strong><small>Pressioni, sentinella e software</small></span><span className="expand-indicator" aria-hidden="true"/></summary><div className="tire-grid">{[['fl','Anteriore SX'],['fr','Anteriore DX'],['rl','Posteriore SX'],['rr','Posteriore DX']].map(([key,label])=><div key={key}><span>{label}</span><strong>{fmt(dash?.tpms?.[key],2)} <small>bar</small></strong></div>)}</div><dl className="door-list"><div><dt>Climatizzazione</dt><dd>{bool(dash?.is_climate_on,'Accesa','Spenta')}</dd></div><div><dt>Sentinella</dt><dd>{bool(dash?.sentry_mode,'Attiva','Spenta')}</dd></div><div><dt>Software</dt><dd>{dash?.software_version||'—'}</dd></div></dl></details>
   <details className="disclosure home-profile"><summary><span className="expand-icon"><Icon name="home"/></span><span className="expand-copy"><strong>Il tuo profilo Tesla</strong><small>Account e autorizzazioni</small></span><span className="expand-indicator" aria-hidden="true"/></summary><div className="disclosure-body">{profile?.available?<dl className="door-list"><div><dt>Nome</dt><dd>{profile.name||'—'}</dd></div><div><dt>Email</dt><dd>{profile.email||'—'}</dd></div></dl>:<p className="trip-note">{profile?.message||profileError||'Caricamento profilo…'}</p>}<a href="/auth/tesla/start" className="reconnect-link">Aggiorna autorizzazioni Tesla</a></div></details>
  </section>
 </div>;
}
