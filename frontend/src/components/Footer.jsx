export default function Footer({ updatedAt }) {
  return (
    <footer className="app-footer">
      <span>Shmersla PWA • Sincronizzazione Cloud</span>
      <span>
        Aggiornato: {updatedAt ? new Date(updatedAt).toLocaleTimeString('it-IT') : '—'}
      </span>
    </footer>
  );
}
