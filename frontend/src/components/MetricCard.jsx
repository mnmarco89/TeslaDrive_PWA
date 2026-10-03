import Icon from './Icon';
export default function MetricCard({ title, value, icon, highlight }) {
  return (
    <div className={`metric-card ${highlight ? 'highlight' : ''}`}>
      <div className="metric-icon"><Icon name={{ '🔋': 'battery', '🛣️': 'route', '🚀': 'speed', '🧭': 'pin', '🚗': 'route', '⚡': 'charge', '⛽': 'fuel', '💶': 'wallet' }[icon]} /></div>
      <div className="metric-content">
        <span className="metric-title">{title}</span>
        <strong className="metric-value">{value}</strong>
      </div>
    </div>
  );
}
