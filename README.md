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
      trips.py
    services/
      tesla_service.py
      voltage_governor.py
      trip_service.py
      trip_collector.py

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
    TripMap.jsx
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

## Storico viaggi

La sezione Telemetria include ora storico, mappa e stime di energia. Consultare le istruzioni dell’aggiornamento 2.1 qui sotto prima del deploy.

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
openid offline_access user_data vehicle_device_data vehicle_location vehicle_cmds vehicle_charging_cmds
```

## Build locale frontend

```bash
cd frontend
npm ci
npm run build
```

## Avvio backend locale

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```


## Aggiornamento 2.1 — Telemetria e storico dei percorsi

### Installazione sulla versione già funzionante

1. Sostituire il codice del progetto con i file di questo pacchetto e fare il deploy usando il Dockerfile esistente. Conservare tutte le variabili d’ambiente e lo stesso database PostgreSQL: non eliminare il database. Le tabelle `tracking_vehicles` e `telemetry_*` vengono create al primo avvio. Le tabelle precedenti `trips` e `trip_points` rimangono intatte; se compatibili con la versione 2.1 vengono copiate una sola volta nelle nuove tabelle. Se hanno uno schema diverso (es. `started` anziché `started_at`), i dati restano conservati ma non sono importati o mostrati automaticamente nello storico nuovo.
2. Uscire dall’app e ricollegare l’account Tesla. Il consenso ora comprende `vehicle_location`: autorizzare la posizione e verificare che il permesso sia abilitato anche nella configurazione dell’app sul portale Tesla Developer. Senza GPS i viaggi possono contenere distanza/batteria ma non la mappa.
3. Aprire **Telemetria e percorsi** e lasciare vuoto il campo della capacità manuale per usare la stima automatica dalle ricariche. Fino alla prima ricarica valida i kWh dei viaggi restano assenti. Se conosci la capacità utile, puoi inserirla manualmente; il valore manuale ha precedenza. Non usare la capacità nominale lorda. La capacità e la tariffa energia vengono fotografate all’inizio di ogni viaggio e non riscrivono lo storico.
4. Lo storico parte dai campioni ricevuti dopo questo aggiornamento. Fare un breve viaggio e verificare data/ora, batteria, distanza e punti GPS. La mappa usa Leaflet e OpenStreetMap, con attribuzione; non richiede una API key.

### Registrazione e limiti pratici

- Il raccoglitore gira nel backend, anche con il browser chiuso. Il deploy deve avere **un solo processo uvicorn e una sola replica** (come il Dockerfile fornito). Per più repliche servirebbe coordinamento distribuito.
- Il `render.yaml` conserva il piano `free` precedente. **Un servizio sospeso non raccoglie dati**: per registrare durante i viaggi a browser chiuso occorre un backend sempre attivo. Questo pacchetto non cambia automaticamente il piano o le impostazioni dell’account Render. Anche il database deve essere persistente; SQLite su filesystem effimero non garantisce conservazione.
- Raccolta tramite l’API Tesla già presente: circa ogni 15 s in marcia e ogni 60 s da fermo, controllando che il veicolo sia online. Non viene inviato alcun comando di risveglio. Le API Tesla possono avere costi: il polling aumenta le chiamate. Tesla raccomanda **Fleet Telemetry** per raccolta continua più efficiente; non è attivata qui perché richiede un server pubblico di streaming e configurazione firmata del veicolo aggiuntivi.
- Variabili facoltative: `TRIP_DRIVING_INTERVAL` (secondi, minimo 15), `TRIP_IDLE_INTERVAL` (minimo 60). Il cruscotto riusa i campioni recenti del raccoglitore. La sezione ricarica mantiene il suo funzionamento precedente, incluse le proprie richieste API.
- I token del raccoglitore vengono aggiornati con il refresh token dopo una risposta 401. Se non è possibile rinnovarli serve ricollegare Tesla. Il 429 sospende le richieste telemetriche per almeno 5 minuti o per `Retry-After`, se maggiore.
- Non è garantita la copertura di **tutti** i viaggi: partenze/arrivi tra due campioni, viaggi molto brevi, sospensione del server, rete assente o autorizzazioni mancanti possono perdere dati. Una lacuna oltre 180 s chiude il tratto all’ultimo campione ricevuto come **Interrotto / Percorso parziale**; un successivo tratto in marcia parte separatamente. La mappa disegna i punti campionati, senza ricostruire artificialmente le strade o le lacune.
- Marcia D/R/N o velocità positiva avvia il viaggio. P lo termina; marcia sconosciuta e velocità esplicitamente zero richiedono 60 s di conferma. Fermarsi a un semaforo mantenendo D non termina il viaggio. Una partenza già in marcia senza un campione precedente recente è indicata come parziale.
- Ogni campione conserva ora Tesla, coordinate se disponibili, velocità, batteria e odometro. Timestamp duplicati/non ordinati vengono ignorati. Campioni senza timestamp o troppo vecchi non sono registrati come nuovi.
- Distanza da variazione odometro; in assenza, stima tramite GPS e segnalazione esplicita. Energia netta **stimata** = `(SOC iniziale − SOC finale) × capacità utile / 100`; include consumi ausiliari e arrotondamento del SOC. Un guadagno di batteria può produrre un valore negativo: non viene trasformato in un consumo positivo. Non è una misura dell’energia prelevata dalla rete e non include le perdite di ricarica.
- Riepiloghi per oggi, settimana corrente (da lunedì), mese corrente, tutti, con elenco paginato di 50 viaggi. Date mostrate in `Europe/Rome`, archiviate in UTC. Il consumo medio usa solo viaggi con energia e distanza disponibili; il riepilogo mostra quanti viaggi hanno una stima energia.
- L’app conserva l’architettura di autenticazione preesistente per uso personale con un solo account Tesla condiviso dal backend. I nuovi endpoint richiedono lo stesso controllo di autenticazione esistente; questo aggiornamento non introduce isolamento tra più utenti.

### Moduli coinvolti

- Frontend: `src/pages/TelemetryPage.jsx`, `src/components/TripMap.jsx`.
- Backend: `app/routers/trips.py`, `app/services/trip_service.py`, `app/services/trip_collector.py` e nuovi modelli. Il limite ricarica resta **10–20 A**.
- `frontend/package-lock.json` è incluso; Docker usa `npm ci` per installare le versioni verificate.

### Verifica locale

Dalla cartella `backend`, dopo aver installato `requirements.txt`:

```bash
python -m unittest discover -s tests -v
```

Dalla cartella `frontend`:

```bash
npm ci
npm run build
```

I test usano campioni simulati e un database SQLite isolato, senza inviare richieste alla tua Tesla. Il collegamento reale all’auto e il deploy Render devono essere verificati dopo l’installazione.

Riferimenti ufficiali:
- https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-endpoints
- https://developer.tesla.com/docs/fleet-api/fleet-telemetry

Validazione di questo pacchetto: 22 test backend superati, import dell’app verificato, build Vite/PWA completata. Interfaccia desktop e mobile, selezione viaggio, filtri e salvataggio verificati con risposte API simulate; nessun errore JavaScript o overflow orizzontale. La cartografia OpenStreetMap esterna non era raggiungibile nell’ambiente di verifica: controllato il messaggio di errore e la conservazione della linea GPS. Nessun test live contro il veicolo o Render.


## Correzione compatibilità e capacità automatica

- Il log `column trips.started_at does not exist` deriva da una tabella `trips` preesistente incompatibile. Ora i nuovi modelli usano `telemetry_trips` e `telemetry_trip_points`; l’avvio (`app/schema.py`) crea le tabelle dedicate senza cancellare o alterare quelle vecchie. La copia da uno schema 2.1 compatibile è transazionale e registrata in `telemetry_migrations`, con riallineamento delle sequenze PostgreSQL. Non è necessario eseguire SQL manuale o eliminare il database. Gli schemi legacy sconosciuti sono conservati e richiedono una conversione dedicata per visualizzare eventuali vecchi record.
- La capacità automatica è una **stima**, non una lettura certificata della capacità utile. La raccolta osserva `charge_state.timestamp`, `battery_level` e il contatore `charge_energy_added`. Al termine di una ricarica con almeno 20 punti percentuali di aumento osservato calcola `delta kWh / delta SOC × 100`. Mantiene la mediana delle ultime 10 ricariche valide. La stima risente di arrotondamento SOC, temperatura, bilanciamento e interpretazione dell’energia aggiunta dal veicolo. Non effettua ipotesi sul modello/VIN.
- La calibrazione richiede il raccoglitore attivo per tutta la parte di sessione osservata e un campione di fine sessione o reset del contatore. Lacune oltre 180 s e aumenti SOC troppo piccoli invalidano la calibrazione. I dati di calibrazione sono persistenti nelle tabelle `telemetry_battery_calibration` e `telemetry_battery_observations` e sopravvivono al riavvio. Il valore manuale, se presente, resta prioritario; cancellarlo e salvare per tornare all’automatico.
- Se `charge_state.nominal_full_pack_energy` viene fornito dal veicolo, lo visualizza come **capacità nominale Tesla** separata; non lo usa come capacità utile. Il campo Fleet Telemetry `NominalFullPackEnergyKwh` è documentato da Tesla per firmware 2026.32, ma lo streaming Fleet Telemetry non è configurato da questo pacchetto. Non viene promessa la disponibilità di quel campo nell’endpoint attuale.
- OAuth ora include `prompt_missing_scopes=true` e `require_requested_scopes=true`; lo scambio del codice usa il dominio `fleet-auth` documentato, con audience europea e form URL encoded. Serve ancora abilitare `vehicle_location` nel portale Developer e ricollegare Tesla. Se una richiesta con GPS riceve `Unauthorized missing scopes`, tenta i dati senza `location_data`: lo stato avvisa di ricollegare per il GPS. Se anche gli scope di base sono mancanti, il consenso va corretto sul portale Tesla.
- Frontend: un errore del cruscotto non scarta una risposta valida della sezione ricarica; lo storico mostra un messaggio di errore invece di restare in caricamento indefinito.

Verifica di questa correzione: 22 test con SQLite isolato, compresi schema legacy intatto, copia idempotente di viaggi/punti compatibili, stima da ricarica, reset contatore, scarto lacune, priorità manuale, capacità nominale separata, fallback scope GPS e parametri OAuth. Import dell’app e build PWA completati. Nessuna modifica effettuata al database remoto e nessuna chiamata live all’auto.
