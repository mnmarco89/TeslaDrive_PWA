import { useState } from 'react';
export default function Header({ connected, onLogout, profile }) {
 const [failedPhoto, setFailedPhoto] = useState(null);
 const name = profile?.name || 'Il tuo account';
 const initial = name.trim().charAt(0).toUpperCase();
 return <header className="app-header">
  <div className="brand"><img src="/logo.png" alt="Shmersla" className="brand-logo-img"/><div><h1>Shmersla</h1><span className="subtitle">La tua Tesla, a colpo d’occhio</span></div></div>
  {connected && <div className="header-account"><div className="account-identity">
   {profile?.photo_url && failedPhoto !== profile.photo_url ? <img className="profile-avatar" src={profile.photo_url} alt="Foto profilo Tesla" referrerPolicy="no-referrer" onError={() => setFailedPhoto(profile.photo_url)}/> : <span className="profile-avatar profile-initial" aria-hidden="true">{initial}</span>}
   <div className="account-name"><strong>{name}</strong><span>Account Tesla</span></div>
  </div><button className="btn-logout" onClick={onLogout}>Scollega</button></div>}
 </header>;
}
