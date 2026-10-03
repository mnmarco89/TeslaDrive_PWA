import Icon from './Icon';
import JewishSymbol from './JewishSymbol';
const tabs = [['home', 'Home', 'home'], ['ricarica', 'Ricarica', 'charge'], ['telemetria', 'Percorsi', 'route'], ['costi', 'Costi', 'wallet'], ['risparmio', 'Ebreo Status', 'wallet']];
export default function TabsNav({ activeTab, onChange }) {
 return <nav className="tabs-nav" aria-label="Sezioni principali">{tabs.map(([id, label, icon]) => <button key={id} className={`tab-btn ${activeTab === id ? 'active' : ''}`} aria-current={activeTab === id ? 'page' : undefined} onClick={() => onChange(id)}>{id==='risparmio'?<JewishSymbol/>:<Icon name={icon}/>}<span>{label}</span></button>)}</nav>;
}
