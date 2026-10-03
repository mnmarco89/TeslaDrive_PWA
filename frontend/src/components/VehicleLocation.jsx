import { useEffect, useState } from 'react';
import { api } from '../api/client';
import TripMap from './TripMap';
export default function VehicleLocation({vin,dash}) {
 const [saved,setSaved]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let cancelled=false;const load=()=>api(`/api/vehicles/${vin}/location`).then(d=>{if(!cancelled){setSaved(d);setError('');}}).catch(e=>{if(!cancelled)setError(e.message);});load();const t=setInterval(load,60000);return()=>{cancelled=true;clearInterval(t);};},[vin]);
 const current=dash?.location;
 const location=current?.available&&(!saved?.available||Date.parse(current.recorded_at)>=Date.parse(saved.recorded_at))?current:saved;
 const available=location?.available;
 const stale=available&&(Date.now()-Date.parse(location.recorded_at)>180000);
 return <section className="glass-panel full-width home-location"><div className="panel-header"><h3>Dove si trova</h3><span className={`live-badge ${stale?'neutral-badge':''}`}>{available?(stale?'ULTIMA POSIZIONE':'GPS RILEVATO'):'GPS IN ATTESA'}</span></div>
 {available?<><TripMap tripId={`${vin}:${location.recorded_at}`} positionMode points={[{latitude:location.latitude,longitude:location.longitude,recorded_at:location.recorded_at}]}/><div className="location-info"><div><strong>{Number(location.latitude).toFixed(5)}, {Number(location.longitude).toFixed(5)}</strong><span>Rilevata il {new Date(location.recorded_at).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})}</span></div><a className="trip-button" href={`https://www.google.com/maps/dir/?api=1&destination=${location.latitude},${location.longitude}`} target="_blank" rel="noopener noreferrer">Raggiungi l’auto ↗</a></div>{stale&&<p className="trip-note">La posizione potrebbe essere cambiata. Si aggiornerà quando Tesla invierà nuovi dati.</p>}</>:<div className="empty-state-box"><p>Posizione non ancora disponibile</p><span>{error||'Ricollega Tesla con il permesso di posizione e attendi un rilevamento. L’auto non viene svegliata automaticamente.'}</span></div>}
 </section>;
}
