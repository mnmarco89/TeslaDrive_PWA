import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function TripMap({ points = [] }) {
  const container = useRef(null);
  const instance = useRef(null);
  const layers = useRef(null);
  const fitted = useRef(false);
  const bounds = useRef(null);
  const [tileError, setTileError] = useState(false);
  const hasGps = points.some(p => p.latitude != null && p.longitude != null);
  useEffect(() => {
    if (!hasGps || !container.current) return undefined;
    setTileError(false);
    const map = L.map(container.current, { scrollWheelZoom: false });
    instance.current = map;
    layers.current = L.layerGroup().addTo(map);
    fitted.current = false;
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).on('tileerror', () => setTileError(true)).addTo(map);
    let previousSize = null;
    const observer = new ResizeObserver(([entry]) => {
      const size = `${entry.contentRect.width}:${entry.contentRect.height}`;
      map.invalidateSize({ pan: false });
      if (previousSize && previousSize !== size && bounds.current) map.fitBounds(bounds.current, { padding: [30, 30], maxZoom: 16, animate: false });
      previousSize = size;
    });
    observer.observe(container.current);
    return () => { observer.disconnect(); map.remove(); instance.current = null; layers.current = null; };
  }, [hasGps]);

  useEffect(() => {
    const map = instance.current, group = layers.current;
    if (!map || !group || !hasGps) return;
    group.clearLayers();
    const valid = points.filter(p => p.latitude != null && p.longitude != null);
    const segments = [];
    let segment = [], previous = null;
    for (const point of points) {
      if (point.latitude == null || point.longitude == null) {
        if (segment.length) segments.push(segment);
        segment = []; previous = null; continue;
      }
      const dt = previous ? (new Date(point.recorded_at)-new Date(previous.recorded_at))/1000 : 0;
      const gap = previous && (dt <= 0 || dt > 180 || L.latLng(previous.latitude, previous.longitude).distanceTo(L.latLng(point.latitude, point.longitude))/dt*3.6 > 250);
      if (gap) { if (segment.length) segments.push(segment); segment = []; }
      segment.push([point.latitude, point.longitude]); previous = point;
    }
    if (segment.length) segments.push(segment);
    segments.forEach(path => L.polyline(path, { color: '#60a5fa', weight: 5 }).addTo(group));
    bounds.current = L.latLngBounds(valid.map(pt => [pt.latitude, pt.longitude]));
    const first = valid[0], last = valid[valid.length - 1];
    L.circleMarker([first.latitude, first.longitude], { radius: 8, color: '#22c55e', fillOpacity: 1 }).bindTooltip('Primo punto rilevato').addTo(group);
    if (valid.length > 1) L.circleMarker([last.latitude, last.longitude], { radius: 8, color: '#f97316', fillOpacity: 1 }).bindTooltip('Ultimo punto rilevato').addTo(group);
    if (!fitted.current) {
      if (valid.length === 1) map.setView([first.latitude, first.longitude], 15);
      else map.fitBounds(L.latLngBounds(valid.map(pt => [pt.latitude, pt.longitude])), { padding: [30, 30], maxZoom: 16 });
      fitted.current = true;
    }
  }, [points, hasGps]);

  if (!hasGps) return <div className="empty-state-box"><p>Nessun punto GPS disponibile.</p><span>Ricollega Tesla autorizzando l’accesso alla posizione. Distanza e batteria restano disponibili se ricevute.</span></div>;
  return <><div className="map-tools"><span><i className="map-start" />Partenza <i className="map-end" />Arrivo</span><button type="button" className="trip-button" onClick={() => { if (instance.current && bounds.current) instance.current.fitBounds(bounds.current, { padding: [30, 30], maxZoom: 16 }); }}>Inquadra percorso</button></div><div ref={container} className="trip-map" aria-label="Mappa del percorso registrato" />{tileError && <p className="trip-note">Cartografia non raggiungibile. I punti del viaggio sono conservati.</p>}</>;
}
