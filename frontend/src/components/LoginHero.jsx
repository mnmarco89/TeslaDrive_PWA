export default function LoginHero() {
  return (
    <div className="login-hero">
      <div className="hero-badge">SECURE OAUTH 2.0</div>
      <h2>La tua Shmersla, <br />senza compromessi.</h2>
      <p>
        Monitoraggio in tempo reale, telemetria avanzata e protezione
        intelligente del voltaggio domestico.
      </p>
      <button
        className="btn-tesla-login"
        onClick={() => { window.location.href = '/auth/tesla/start'; }}
      >
        <span>Accedi con Tesla ID</span>
      </button>
      <span className="security-note">
        🔒 Credenziali gestite direttamente dai server crittografati Tesla.
      </span>
    </div>
  );
}
