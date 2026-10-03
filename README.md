# Shmersla / TeslaDrive PWA — struttura modulare

Versione riorganizzata del progetto originale. Il comportamento funzionale corrente è stato mantenuto, ma frontend e backend sono stati separati in moduli per permettere di modificare una sezione senza dover riscrivere tutta l'app.

## Struttura

```text
backend/
  main.py
  app/
    config.py
    database.py
    dependencies.py
    models.py
    routers/
      auth.py
      charging.py
      settings.py
      system.py
      vehicles.py
    services/
      tesla_service.py
      voltage_governor.py

frontend/src/
  main.jsx
  App.jsx
  api/
    client.js
  components/
    Footer.jsx
    Header.jsx
    LoginHero.jsx
    MetricCard.jsx
    TabsNav.jsx
    VehicleHero.jsx
  pages/
    ChargingPage.jsx
    CostsPage.jsx
    TelemetryPage.jsx
  style.css
```

## Limite di ricarica

Il range applicativo è centralizzato lato backend in `backend/app/config.py`:

```python
MIN_CHARGING_AMPS = 10
MAX_CHARGING_AMPS = 20
```

Il frontend mantiene lo slider 10–20 A e i preset 10/16/20 A.

## Prossimo modulo: storico viaggi

La pagina `frontend/src/pages/TelemetryPage.jsx` è ora isolata. Il prossimo sviluppo può aggiungere storico percorsi, mappa e consumi senza toccare la pagina di ricarica.

Il backend mantiene per ora `/api/trips` come placeholder compatibile. Lo storico reale verrà implementato in un modulo dedicato.

## Deploy Render

Il deploy rimane basato sul `render.yaml` esistente. Il `backend/Dockerfile` è stato aggiornato per copiare l'intero backend modulare.

Variabili principali:

```text
TESLA_CLIENT_ID=...
TESLA_CLIENT_SECRET=...
TESLA_REDIRECT_URI=https://<dominio>/auth/tesla/callback
TESLA_AUDIENCE=https://fleet-api.prd.eu.vn.cloud.tesla.com
TESLA_PRIVATE_KEY=<chiave privata VCP>
DATABASE_URL=<fornito da Render/PostgreSQL>
```

Gli scope OAuth usati dal codice corrente sono:

```text
openid offline_access user_data vehicle_device_data vehicle_cmds vehicle_charging_cmds
```

## Build locale frontend

```bash
cd frontend
npm install
npm run build
```

## Avvio backend locale

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
