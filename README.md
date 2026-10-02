# TeslaDrive – Deploy Render

Versione PWA + FastAPI + PostgreSQL pensata per essere pubblicata su Render.

## Cosa fa già

- OAuth Tesla reale
- refresh token automatico
- lettura veicoli Tesla
- batteria, autonomia, odometro, velocità, marcia
- posizione disponibile dai dati di guida quando Tesla la restituisce
- impostazioni €/kWh, €/L diesel e km/L diesel
- database PostgreSQL per token, impostazioni, telemetria e viaggi
- PWA installabile da Safari su iPhone
- HTTPS tramite Render
- frontend React compilato e servito direttamente da FastAPI

## Cosa richiede Fleet Telemetry

Destinazione navigazione, RouteLine e raccolta continua dei tragitti richiedono il server Fleet Telemetry ufficiale Tesla. Non vengono simulati da questa app.

Tesla descrive Fleet Telemetry come un server pubblico che riceve direttamente i dati dal veicolo. La configurazione richiede anche chiavi/virtual key e configurazione del veicolo.

## Deploy consigliato

1. Carica tutti i file di questa cartella nel repository GitHub già collegato a Render.
2. Fai commit sul branch collegato a Render, normalmente `main`.
3. In Render verifica il Web Service `tesladrive`.
4. Crea un database PostgreSQL Free chiamato `tesladrive-db` se il tuo servizio non è stato creato tramite Blueprint. Collegalo tramite `DATABASE_URL`.
5. Imposta le variabili:

```text
TESLA_CLIENT_ID=...
TESLA_CLIENT_SECRET=...
APP_BASE_URL=https://tesladrive.onrender.com
TESLA_REDIRECT_URI=https://tesladrive.onrender.com/auth/tesla/callback
TESLA_AUDIENCE=https://fleet-api.prd.eu.vn.cloud.tesla.com
SESSION_SECRET=<casuale e lungo>
DATABASE_URL=<fornito da Render Postgres>
```

Se usi il `render.yaml` come Blueprint, Render può creare Web Service e Postgres insieme.

## Tesla Developer

Nella tua app Tesla devi registrare esattamente:

- Allowed origin: `https://tesladrive.onrender.com`
- Redirect URI: `https://tesladrive.onrender.com/auth/tesla/callback`

Sostituisci `tesladrive.onrender.com` con il dominio effettivamente assegnato da Render.

Gli scope richiesti da questa versione sono:

```text
openid offline_access vehicle_device_data vehicle_location
```

Non vengono richiesti comandi veicolo o comandi di ricarica.

## Test

Apri:

```text
https://tesladrive.onrender.com/health
```

Deve rispondere con `ok: true`.

Poi apri la home e premi `Collega Tesla`.

## iPhone

Safari -> apri l'URL -> Condividi -> Aggiungi alla schermata Home.

## Nota sul piano Free

Render offre Web Service e PostgreSQL Free per test/hobby, ma il Web Service può andare in sleep e il PostgreSQL Free scade dopo 30 giorni. Per lo storico permanente bisogna poi passare il database a un piano a pagamento.
