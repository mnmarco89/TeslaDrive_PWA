import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const api=(p,o={})=>fetch(p,{credentials:'include',...o}).then(async r=>{const t=await r.text();let d;try{d=JSON.parse(t)}catch{d=t}if(!r.ok)throw new Error(d?.detail||d||`HTTP ${r.status}`);return d});

function App(){
 const [connected,setConnected]=useState(false),[vehicles,setVehicles]=useState([]),[vin,setVin]=useState(localStorage.getItem('tesladrive_vin')||''),[dash,setDash]=useState(null),[settings,setSettings]=useState(null),[trips,setTrips]=useState([]),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 const load=async()=>{setLoading(true);setError('');try{const st=await api('/api/status');setConnected(st.connected);if(!st.connected){setLoading(false);return}const v=await api('/api/vehicles');const list=v.response||v;setVehicles(list);const chosen=vin||list[0]?.vin;if(chosen){setVin(chosen);localStorage.setItem('tesladrive_vin',chosen);setDash(await api('/api/dashboard/'+chosen))}setSettings(await api('/api/settings'));setTrips(await api('/api/trips'))}catch(e){setError(e.message)}finally{setLoading(false)}};
 useEffect(()=>{load()},[]);useEffect(()=>{if(!vin||!connected)return;const t=setInterval(()=>api('/api/dashboard/'+vin).then(setDash).catch(e=>setError(e.message)),30000);return()=>clearInterval(t)},[vin,connected]);
 const save=async()=>{await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)});setError('Impostazioni salvate.')};
 const logout=async()=>{await api('/auth/logout',{method:'POST'});setConnected(false);setDash(null);setVehicles([])};
 return <div className="app"><header><div><strong>TeslaDrive</strong><span> dati Tesla reali</span></div>{connected?<button className="ghost" onClick={logout}>Scollega</button>:<a className="connect" href="/auth/tesla/start">Collega Tesla</a>}</header>
 {error&&<div className="notice">{error}</div>}
 {loading?<main className="empty"><h1>Caricamento…</h1></main>:!connected?<main className="empty"><div className="logo">T</div><h1>La tua Tesla, in una sola schermata. Shemrte</h1><p>Collega il tuo account Tesla. L'autorizzazione avviene direttamente sui server Tesla.</p><a className="button" href="/auth/tesla/start">Accedi con Tesla</a><small>Il client secret non viene mai inviato al telefono.</small></main>:<main>
 <section className="car"><div><label>VEICOLO</label><h1>{vehicles.find(x=>x.vin===vin)?.display_name||vin}</h1><select value={vin} onChange={async e=>{const x=e.target.value;setVin(x);localStorage.setItem('tesladrive_vin',x);setDash(await api('/api/dashboard/'+x))}}>{vehicles.map(x=><option key={x.vin} value={x.vin}>{x.display_name||x.vin}</option>)}</select></div><div className="battery">{dash?.battery??'—'}<em>%</em></div></section>
 <div className="grid"><Card t="Autonomia" v={dash?.range_km!=null?Math.round(dash.range_km)+' km':'—'}/><Card t="Odometro" v={dash?.odometer_km!=null?Math.round(dash.odometer_km)+' km':'—'}/><Card t="Velocità" v={dash?.speed_kmh!=null?Math.round(dash.speed_kmh)+' km/h':'0 km/h'}/><Card t="Marcia" v={dash?.shift_state||'P'}/></div>
 <section className="panel"><div className="panelhead"><h2>🧭 Navigazione</h2><span>Fleet Telemetry</span></div>{dash?.navigation&&Object.keys(dash.navigation).length?<pre>{JSON.stringify(dash.navigation,null,2)}</pre>:<div className="muted">Nessun dato di navigazione ricevuto. La lettura di destinazione e RouteLine verrà attivata con il server Fleet Telemetry e la configurazione del veicolo.</div>}</section>
 <section className="panel"><h2>⚡ Costi e risparmio</h2>{settings&&<div className="settings"><label>Energia €/kWh<input type="number" step="0.01" value={settings.electricity} onChange={e=>setSettings({...settings,electricity:+e.target.value})}/></label><label>Diesel €/L<input type="number" step="0.01" value={settings.diesel} onChange={e=>setSettings({...settings,diesel:+e.target.value})}/></label><label>Diesel km/L<input type="number" step="0.1" value={settings.diesel_km_l} onChange={e=>setSettings({...settings,diesel_km_l:+e.target.value})}/></label><button onClick={save}>Salva</button></div>}</section>
 <section className="panel"><h2>🧾 Storico viaggi</h2>{trips.length?<div>{trips.map(t=><div className="trip" key={t.id}><b>{new Date(t.started*1000).toLocaleString('it-IT')}</b><span>{(t.km||0).toFixed(1)} km</span><span>{(t.energy_kwh||0).toFixed(1)} kWh</span></div>)}</div>:<div className="muted">Lo storico automatico viene alimentato dalla Fleet Telemetry.</div>}</section>
 </main>}
 <footer>Ultimo aggiornamento: {dash?.updated_at?new Date(dash.updated_at).toLocaleTimeString('it-IT'):'—'}</footer></div>
}
function Card({t,v}){return <div className="card"><span>{t}</span><strong>{v}</strong></div>}
createRoot(document.getElementById('root')).render(<App/>);
