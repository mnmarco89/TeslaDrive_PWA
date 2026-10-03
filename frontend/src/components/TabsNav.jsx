const tabs = [
  ['ricarica', '🔌 Ricarica & Voltaggio'],
  ['telemetria', '🧭 Telemetria & Navigazione'],
  ['costi', '⚡ Costi ed Energia'],
];

export default function TabsNav({ activeTab, onChange }) {
  return (
    <div className="tabs-nav">
      {tabs.map(([id, label]) => (
        <button
          key={id}
          className={`tab-btn ${activeTab === id ? 'active' : ''}`}
          onClick={() => onChange(id)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
