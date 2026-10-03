import { useEffect, useState } from 'react';
import { api } from '../api/client';
const fmt = v => v == null ? '—' : Number(v).toLocaleString('it-IT',{maximumFractionDigits:1});
const weatherLabel = c => c == null ? 'Meteo' : c===0 ? 'Sereno' : c<=3 ? 'Nuvoloso' : c<=48 ? 'Nebbia' : c<=67 ? 'Pioggia' : c<=77 ? 'Neve' : c<=82 ? 'Rovesci' : c<=86 ? 'Neve' : 'Temporali';
export default function TripContext({ vin, tripId }) {
 const [data,setData]=useState(null),[error,setError]=useState('');
 const [attempt,setAttempt]=useState(0);
 useEffect(() => {
  const controller=new AbortController(); let timer;
  const load=async () => { try { const result=await api(`/api/trips/${vin}/${tripId}/context${attempt ? "?retry=true" : ""}`,{signal:controller.signal}); if(controller.signal.aborted)return; setData(result); setError(''); if(result.status==='pending')timer=setTimeout(load,5000); else if(['partial','unavailable'].includes(result.status))timer=setTimeout(load,1800000); } catch(err){if(err.name!=='AbortError')setError('Meteo e quote temporaneamente non disponibili.');} };
  load(); return () => { controller.abort();clearTimeout(timer); };
 },[vin,tripId,attempt]);
 const weather=data?.weather,elevation=data?.elevation;
 const profile=elevation?.profile || [];
 const min=elevation?.min_m ?? 0,max=elevation?.max_m ?? min+1;
 const length=profile.at(-1)?.distance_km || 1;
 const segments=new Map();for(const pt of profile){if(!segments.has(pt.segment))segments.set(pt.segment,[]);segments.get(pt.segment).push(`${30+pt.distance_km/length*500},${110-(pt.elevation_m-min)/(max-min || 1)*80}`);}
 return <section className="trip-context"><h4>Meteo e terreno</h4>
  {weather && <><div className="context-metrics"><span><small>{weatherLabel(weather.weather_code)}</small><strong>{fmt(weather.temperature_2m)} °C</strong></span><span><small>Vento</small><strong>{fmt(weather.wind_speed_10m)} km/h</strong></span><span><small>Precipitazioni</small><strong>{fmt(weather.precipitation)} mm/h</strong></span></div><p className="trip-note">Modello orario alla partenza · {new Date(weather.at).toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'})} · {weather.wind_direction_10m == null ? '' : `Vento da ${fmt(weather.wind_direction_10m)}° · `}<a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a></p></>}
  {elevation && <><div className="context-metrics"><span><small>Salita stimata</small><strong>+{fmt(elevation.ascent_m)} m</strong></span><span><small>Discesa stimata</small><strong>−{fmt(elevation.descent_m)} m</strong></span><span><small>Quote min / max</small><strong>{fmt(elevation.min_m)} / {fmt(elevation.max_m)} m</strong></span></div><svg className="elevation-chart" viewBox="0 0 560 140" role="img" aria-label={`Profilo altimetrico stimato: da ${fmt(elevation.min_m)} a ${fmt(elevation.max_m)} metri`}><path d="M30 20v90h500" fill="none" stroke="#40526b"/><text x="30" y="16">{fmt(max)} m</text><text x="30" y="132">0 km</text><text x="465" y="132">{fmt(profile.at(-1)?.distance_km)} km GPS</text>{[...segments.entries()].map(([key,points])=><polyline key={key} points={points.join(' ')} fill="none" stroke="#77d7d0" strokeWidth="3"/>)}</svg><p className="trip-note">Stima terreno DEM 90 m · <a href="https://open-meteo.com/en/docs/elevation-api" target="_blank" rel="noreferrer">Open-Meteo / Copernicus</a>{elevation.partial ? ' · Traccia con interruzioni' : ''}.</p></>}
  {(!data || data.status==='pending') && <p className="trip-note">Recupero meteo e quote…</p>}
  {data?.message && data.status!=='pending' && <p className="trip-note">{data.message}</p>}
  {Object.entries(data?.errors || {}).map(([key,value])=><p className="trip-note" key={key}>{key==='weather'?'Meteo':'Quote'}: {value}</p>)}
  {error && <p className="trip-note">{error}</p>}
  {(error || ['partial','unavailable'].includes(data?.status)) && <div className="context-retry"><button type="button" className="trip-button" onClick={() => {setData(current=>({...current,status:'pending'}));setAttempt(n=>n+1);}}>Riprova meteo e quote</button><small>{data?.retry_after_seconds > 0 && data.retry_after_seconds <= 30 ? 'Nuovo tentativo disponibile entro 30 secondi.' : 'Ritento solo i dati mancanti; quelli già recuperati restano salvati.'}</small></div>}
  {(weather || elevation) && <details className="disclosure"><summary>Precisione dei dati</summary><p className="trip-note">Il meteo è una ricostruzione del modello alla prima posizione GPS, non una misura lungo tutto il viaggio. La precipitazione è il valore orario del modello. Il profilo campiona fino a 100 punti del terreno: ponti, gallerie, tratti non registrati e piccoli dislivelli possono differire dalla strada reale. Le variazioni sotto 3 m sono filtrate.</p></details>}
 </section>;
}
