const labels = {df:'Anteriore sinistra',pf:'Anteriore destra',dr:'Posteriore sinistra',pr:'Posteriore destra',ft:'Bagagliaio anteriore',rt:'Bagagliaio posteriore'};
export const doorState = value => value == null ? 'Non disponibile' : value === 0 ? 'Chiusa' : 'Aperta';
export default function VehicleDiagram({ doors = {} }) {
 const color = key => doors[key] == null ? '#60718a' : doors[key] === 0 ? '#77d7d0' : '#ffac72';
 return <div className="vehicle-diagram"><svg viewBox="0 0 280 380" role="img" aria-label="Schema stato delle portiere, parte anteriore in alto">
 <defs><linearGradient id="car-body" x1="0" x2="1"><stop stopColor="#354c65"/><stop offset=".5" stopColor="#6b849c"/><stop offset="1" stopColor="#354c65"/></linearGradient></defs>
 <ellipse cx="140" cy="197" rx="75" ry="171" fill="#080f1b" opacity=".6"/>
 <rect x="71" y="94" width="14" height="45" rx="5" fill="#08111c"/><rect x="195" y="94" width="14" height="45" rx="5" fill="#08111c"/><rect x="71" y="252" width="14" height="45" rx="5" fill="#08111c"/><rect x="195" y="252" width="14" height="45" rx="5" fill="#08111c"/>
 <path d="M140 23c-35 0-57 17-59 51l-4 212c0 40 18 68 63 68s63-28 63-68l-4-212c-2-34-24-51-59-51Z" fill="url(#car-body)" stroke="#93aabe" strokeWidth="1.5"/>
 <path d="M93 117c8-18 25-27 47-27s39 9 47 27l-7 30h-80Z" fill="#0e2133" stroke="#adc2d1"/>
 <path d="M100 244h80l7 40c-12 13-30 17-47 17s-35-4-47-17Z" fill="#0e2133" stroke="#adc2d1"/>
 <rect x="99" y="156" width="82" height="78" rx="13" fill="#152a3e" stroke="#7391a9"/>
 <path d="M94 59q46-22 92 0M94 319q46 15 92 0" fill="none" stroke="#cad8e3" strokeWidth="4"/>
 <path d="M86 127v66" stroke={color('df')} strokeWidth="5" strokeLinecap="round"/><path d="M194 127v66" stroke={color('pf')} strokeWidth="5" strokeLinecap="round"/>
 <path d="M86 207v64" stroke={color('dr')} strokeWidth="5" strokeLinecap="round"/><path d="M194 207v64" stroke={color('pr')} strokeWidth="5" strokeLinecap="round"/>
 <path d="M104 77h72" stroke={color('ft')} strokeWidth="4" strokeLinecap="round"/><path d="M104 309h72" stroke={color('rt')} strokeWidth="4" strokeLinecap="round"/>
 {['df','pf','dr','pr'].map((key,i) => <g key={key}><circle cx={i%2?226:54} cy={i<2?165:240} r="5" fill={color(key)}/><title>{labels[key]}: {doorState(doors[key])}</title></g>)}
 </svg><div className="diagram-legend"><span><i className="closed-dot"/>Chiusa</span><span><i className="open-dot"/>Aperta</span><span><i className="unknown-dot"/>N/D</span></div></div>;
}
