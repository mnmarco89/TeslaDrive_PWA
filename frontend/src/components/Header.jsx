export default function Header({ connected, onLogout }) {
  return (
    <header className="app-header">
      <div className="brand">
        <img src="/logo.png" alt="Shmersla Logo" className="brand-logo-img" />
        <div>
          <h1>Shmersla</h1>
          <span className="subtitle">La tua Tesla, a colpo d’occhio</span>
        </div>
      </div>
      {connected && (
        <button className="btn-logout" onClick={onLogout}>
          Scollega
        </button>
      )}
    </header>
  );
}
