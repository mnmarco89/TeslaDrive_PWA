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


## Costi ed Energia — prezzi automatici e confronto storico

Per questo aggiornamento basta fare il deploy del codice mantenendo lo stesso database. Le nuove tabelle `telemetry_cost_rates`, `telemetry_trip_cost_snapshots`, `telemetry_fuel_price_state` vengono create all’avvio senza alterare le tabelle esistenti. Non servono chiavi API aggiuntive o conferme dei prezzi.

### Parametri e prezzi

- **Elettricità:** tariffa fissa €/kWh già configurata, come richiesto. Il costo viaggio è la stima dei kWh netti dalla batteria moltiplicata per la tariffa fotografata all’inizio del viaggio. Non rappresenta la somma delle bollette o degli importi realmente pagati ai caricatori e non include le perdite di ricarica. Il pannello mostra la tariffa configurata in sola lettura.
- **Diesel:** completamente automatico, da **MIMIT / Osservaprezzi Carburanti**. Si incrociano i dataset pubblici giornalieri dei prezzi e dell’anagrafica impianti e si sceglie il distributore geograficamente più vicino entro 10 km con **Gasolio standard self-service**. Non viene usato il gasolio speciale/premium né il servito. Non viene usato un prezzo manuale o un valore fisso di fallback. Il prezzo è un riferimento di confronto, non un pagamento effettuato né un preventivo in tempo reale.
- Il dataset MIMIT è pubblicato quotidianamente e rappresenta una fotografia dei prezzi; il pannello mostra distributore, comune, data del dataset e ultimo rilevamento. Il dataset viene tenuto in memoria e scaricato al massimo una volta per giorno Rome, per processo. Il parser usa il separatore `|` introdotto dal MIMIT il 10 febbraio 2026 e supporta anche il precedente `;`.
- Una posizione GPS recente avvia in background l’aggiornamento del diesel, circa ogni ora. I prezzi uguali non producono righe duplicate; una variazione crea una nuova tariffa per il VIN. Il download non blocca il raccoglitore viaggi. In caso di errore riprova dopo circa 15 minuti e conserva l’ultimo prezzo già rilevato con un avviso. Senza alcun rilevamento valido il prezzo resta sconosciuto. Servono backend attivo, GPS autorizzato e accesso di rete al sito MIMIT; l’auto non viene risvegliata per aggiornare il carburante.
- Il consumo dell’auto diesel di confronto, in km/L, è l’unico parametro modificabile nella nuova pagina: non è un prezzo e non è deducibile dalla Tesla. Il valore già configurato viene conservato. Ogni nuovo viaggio conserva quel consumo e, se disponibile, il prezzo diesel rilevato al momento.

### Totali

Il pannello comprende totale elettrico stimato in euro, diesel equivalente in euro, differenza a favore dell’elettrico, filtri oggi/settimana/mese/tutti, riepilogo mensile e storico paginato dei prezzi. I dati sono riferiti al veicolo selezionato e ai viaggi terminati; sono inclusi i percorsi parziali con indicazione della loro presenza.

Formule:
- Elettrico: `kWh netti stimati del viaggio × €/kWh del viaggio`.
- Diesel: `km del viaggio ÷ km/L memorizzati × €/L del periodo`.
- Differenza: `diesel − elettrico`, soltanto sui viaggi per cui entrambi i costi sono disponibili. Un valore negativo indica un costo elettrico stimato maggiore.

Ogni totale mostra i km e il numero di viaggi coperti. La differenza non confronta totali riferiti a distanze diverse. I viaggi senza capacità batteria/stima energetica non contribuiscono al totale elettrico; i viaggi precedenti al primo prezzo storico noto non ricevono il prezzo attuale retroattivamente. La tariffa elettrica già fotografata nei vecchi viaggi resta prioritaria. Il costo elettrico dello storico Telemetria continua a usare quella tariffa in euro.

L’API di salvataggio delle impostazioni ora richiede autenticazione e valida i parametri; le letture non cambiano il prezzo diesel né effettuano richieste GPS/carburante. La sola modifica della protezione voltaggio non crea una variazione di tariffa.

Moduli dedicati: `frontend/src/pages/CostsPage.jsx`, `backend/app/routers/costs.py`, `backend/app/services/cost_service.py`, `fuel_price_service.py`, `fuel_data_service.py` e i nuovi modelli. L’aggiornamento mantiene limite ricarica 10–20 A, telemetria e calibrazione automatica della batteria.

Verifica: **33 test backend**, build Vite/PWA e import applicazione superati. Controlli UI desktop/mobile con API simulate per filtri, tabelle e salvataggio consumo. Verificata anche la lettura dei dataset MIMIT reali e l’abbinamento di un impianto per coordinate di esempio a Roma, senza chiamare la tua auto. Deploy remoto e aggiornamento al cambio reale di listino restano da verificare dopo installazione.

Fonte dati e attribuzione (MIMIT, licenza IODL 2.0):
https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti
https://www.mimit.gov.it/images/stories/documenti/Metadati_prezzi_carburanti_20260128.pdf


## Interfaccia compatta e percorsi su mappa

Questa versione aggiorna la grafica con schede blu scuro, accenti turchesi, indicatore circolare della batteria e icone SVG. Su telefono le tre sezioni Ricarica, Percorsi e Costi si aprono dalla barra fissa inferiore. Le spiegazioni, la configurazione della registrazione e lo storico prezzi sono espandibili; i riepiloghi mensili diventano schede leggibili senza scorrimento orizzontale.

In Percorsi viene selezionato automaticamente il primo viaggio del periodo; selezionare un altro viaggio nello storico aggiorna la mappa. Sono visualizzati i punti GPS effettivamente registrati e gli indicatori di partenza e arrivo. Il comando Inquadra percorso ripristina l'inquadratura; il passaggio fra dimensioni dello schermo riadatta la mappa. La cartografia OpenStreetMap richiede una connessione e, se irraggiungibile, compare un avviso mantenendo la traccia disponibile.

Per verificare la registrazione sul proprio veicolo: autorizzare il permesso posizione Tesla, lasciare il server attivo, percorrere un breve tragitto e parcheggiare; aprire Percorsi e selezionare il viaggio. Non vengono ricostruiti i viaggi precedenti all'attivazione. Una sospensione del server o dati Tesla mancanti possono produrre percorsi parziali. Le stime dei costi mantengono le tariffe storiche dei viaggi.

Verifiche: build frontend/PWA completata; 33 test backend superati; prove browser con dati simulati per selezione della mappa, filtri, salvataggi, limiti di corrente 10–20 A e layout a 320, 390, 768 e 1360 px. La cartografia esterna non è stata verificata nell'ambiente di prova. Nessuna modifica manuale al database richiesta per l'aggiornamento.


## Home, profilo Tesla e comandi remoti

La nuova scheda Home è la pagina iniziale e precede Ricarica, Percorsi e Costi. Il nome e la foto dell'account, se restituiti da Tesla, personalizzano la barra superiore e il saluto. Se la foto non è disponibile viene usata l'iniziale; un errore del profilo non impedisce di usare le altre funzioni. Nome ed email sono consultabili nel pannello espandibile del profilo.

La Home mostra uno schema dell'auto dall'alto, stato delle serrature e delle sei aperture (quattro portiere e due bagagliai), autonomia, odometro, temperature, pressioni pneumatici in bar, climatizzazione, Sentinella, limite ricarica e software. Si usano i dati realmente ricevuti: un campo assente non viene interpretato come chiuso o spento. L'orario dei dati dell'auto proviene dal timestamp Tesla e i dati oltre tre minuti sono indicati come da aggiornare. La sagoma è schematica e non una foto del veicolo. Le pressioni sono gli ultimi valori rilevati dai sensori.

I comandi disponibili sono blocco/sblocco serrature, azionamento bagagliaio anteriore/posteriore, avvio/arresto clima e apertura/chiusura sportello di ricarica. Sbloccare le serrature non apre fisicamente le portiere. Sblocco e bagagliai richiedono conferma nell'interfaccia; il bagagliaio posteriore può muoversi in apertura o chiusura secondo lo stato del veicolo. L'app mostra conferma soltanto se Tesla risponde result=true; lo stato dell'auto viene riletto dopo il comando senza simulare cambiamenti. Il polling periodico continua normalmente.

Autorizzazioni: user_data per il profilo, vehicle_device_data per i dati, vehicle_cmds e/o vehicle_charging_cmds per i comandi. Sono già richiesti dal login di questa applicazione. In caso di permessi mancanti usare Aggiorna autorizzazioni Tesla nel pannello profilo. Per Model 3/Y moderne sono necessarie la chiave virtuale dell'app installata sul veicolo e TESLA_PRIVATE_KEY configurata sul server, come per il controllo corrente esistente. Non sono state introdotte nuove variabili ambiente o modifiche manuali al database. I file temporanei delle chiavi sono individuali, con permessi 600, e vengono rimossi anche in caso di errore.

Verifiche: 43 test backend superati, build frontend/PWA completata, Home controllata in browser a 320/390/768/1360 px. Le prove con risposte simulate comprendono profilo e foto, mancanza permessi profilo, dati sconosciuti, conferma/annullamento sblocco, comandi confermati/rifiutati, aggiornamento stato e limiti ricarica 10–20 A. Percorsi e Costi verificati nuovamente. I nuovi comandi vanno verificati sul veicolo reale dopo l'aggiornamento; nessun comando è stato inviato alla vettura durante queste prove.


## Energia mancante, meteo, quote e consultazione mobile

I viaggi senza capacità utile calibrata conservano SOC iniziale/finale ma non possono convertirlo correttamente in kWh. L'interfaccia ora mostra il motivo e indica Energia in attesa, evitando di confondere il dato assente con un consumo pari a zero. Per avviare la stima automatica il server deve osservare una ricarica con aumento di almeno 20 punti percentuali e ricevere dati regolari fino alla fine. Questa capacità è una stima dalle ricariche, non una misura certificata; i brevi viaggi risentono dell'arrotondamento del SOC.

Quando una capacità diventa disponibile, i viaggi conclusi di quel veicolo con energia mancante, capacità assente e SOC iniziale/finale noti vengono recuperati automaticamente alla consultazione di Percorsi o Costi. La fonte è indicata come stima retrospettiva. Le tariffe originali del viaggio, le distanze e le stime già presenti restano invariate. Non vengono inventati consumi da medie di modello. L'attuale integrazione usa vehicle_data; i segnali EnergyRemaining e LifetimeEnergyUsed appartengono al flusso Fleet Telemetry, che questa versione non configura né riceve. Non viene scaricato un totale storico Tesla in kWh per viaggio.

Il pannello Meteo e terreno recupera automaticamente dati anche per i viaggi già salvati con GPS, quando vengono aperti. Usa la data e l'ora UTC del primo punto GPS e dati orari Open-Meteo: temperatura, vento, direzione e precipitazioni del modello. I viaggi recenti usano Forecast con il giorno specifico; quelli più vecchi l'archivio. Questi dati sono un riferimento del modello alla partenza, non misurazioni per ogni tratto.

Quote, salita/discesa e profilo altimetrico usano il terreno Copernicus DEM GLO-90 tramite Open-Meteo, fino a 100 punti GPS. Il calcolo non collega i dislivelli attraverso interruzioni della traccia, e filtra oscillazioni sotto 3 metri. Ponti, gallerie, piccoli rilievi e campionamento possono differire dalla strada reale. Con un solo punto non viene stimato un totale di salita/discesa. Le attribuzioni ai fornitori sono presenti nell'interfaccia.

Le richieste opzionali avvengono in background, con massimo tre elaborazioni contemporanee, timeout, salvataggio nella nuova tabella telemetry_trip_context e retry dei servizi falliti dopo 30 minuti. Non rallentano la raccolta Tesla. Nessuna chiave Open-Meteo è necessaria per l'uso personale non commerciale. Nessun intervento SQL manuale: la tabella viene creata all'avvio.

Su mobile il selettore e i pulsanti precedente/successivo sono accanto alla mappa e rimangono raggiungibili durante lo scorrimento del dettaglio. Lo storico è espandibile con scorrimento interno; durante il caricamento del viaggio successivo la mappa precedente resta presente e viene attenuata, evitando il collasso della pagina.

Verifica di questa versione: 51 test backend superati e build PWA completata. Prove browser con due viaggi e rete simulata confermano posizione di scorrimento invariata durante la selezione ritardata, precedente/successivo, meteo/quote, spiegazioni energia e assenza di overflow a 320/390/768/1360 px. I servizi Open-Meteo non erano raggiungibili dall'ambiente di test: il collegamento esterno va confermato sul server installato.


## Correzione recupero meteo e quote

Le richieste Open-Meteo hanno timeout di connessione di 10 secondi e di lettura di 15 secondi. Errori di rete/timeout e HTTP 5xx ricevono un secondo tentativo automatico; HTTP 4xx e limiti 429 non vengono ritentati subito. L'interfaccia distingue timeout, errore di rete, rifiuto HTTP 403, limite HTTP 429, data/parametri non validi e dati mancanti, senza mostrare gli URL contenenti coordinate.

Il pulsante Riprova meteo e quote permette di riavviare l'elaborazione dei soli dati mancanti dopo almeno 30 secondi dal fallimento, conservando quelli già salvati. Le vecchie risposte con errore generico vengono ritentate automaticamente senza attendere tutta la cache di 30 minuti. I viaggi, i prezzi e la configurazione DATABASE_URL restano invariati. Nessuna modifica manuale al database è richiesta.

Verifiche: 56 test backend superati, build PWA completata, pulsante di retry e consultazione mobile verificati in browser con errori simulati. Sono state inoltre ottenute risposte reali valide da entrambi i servizi Open-Meteo per un punto di prova a Latina e l'ora del 3 ottobre 2026. La disponibilità dal proprio server resta dipendente dalla rete e dai limiti del fornitore. L'avviso Energia in attesa continua a dipendere dalla calibrazione batteria, non dal meteo.


## Correzione caricamento cartografia e stabilità mobile

La mappa Leaflet viene conservata quando cambia il viaggio: si aggiornano traccia e inquadratura senza ricreare il livello OpenStreetMap. Le immagini vengono richieste a spostamento concluso e non durante ogni fotogramma dello zoom, con un buffer ridotto. La cache HTTP del browser e le attribuzioni OpenStreetMap restano attive. Nessun proxy o download anticipato di aree.

Se un caricamento contiene immagini fallite viene fatto un solo nuovo tentativo dopo 8 secondi per la sessione della mappa, senza cicli continui. Riprova mappa è disponibile anche manualmente. L'avviso viene rimosso dopo un caricamento riuscito. La disponibilità del fornitore esterno non è garantita; la schermata di rete ricevuta non contiene uno stato HTTP e non consente di attribuire il problema a CORS, blocchi o rete con certezza.

Il dettaglio conserva l'altezza raggiunta per evitare salti di scorrimento mentre meteo e profilo altimetrico vengono sostituiti al cambio viaggio; si adatta nuovamente alla larghezza dello schermo. Verificati in browser con risposte simulate errore cartografia, riprova e recupero, riuso della stessa mappa, nessuna nuova richiesta immagini per due viaggi con identica geometria, retry del meteo e stabilità mobile.

## Home semplificata, posizione e storico ricariche

La Home riunisce schema auto, autonomia e posizione in un pannello unico. Il selettore veicolo è compatto nella Home; quattro comandi frequenti sono immediatamente disponibili, gli altri sotto Altri comandi. Portiere, pneumatici e profilo restano consultabili in sezioni espandibili. Le conferme di sblocco e bagagliai e i limiti di corrente 10–20 A sono conservati.

La posizione viene salvata nella nuova tabella telemetry_vehicle_location dai dati Tesla ricevuti dalla raccolta esistente, senza nuove richieste o comandi di risveglio. Il timestamp usa gps_as_of se disponibile, altrimenti drive_state.timestamp. Coordinate assenti, non valide o precedenti non cancellano l'ultima posizione. La Home mostra mappa, data, coordinate e Raggiungi l'auto (Google Maps). Dopo tre minuti la posizione è indicata come ultima posizione e può essere cambiata. La lettura locale autenticata funziona anche quando Tesla non risponde. È necessario il permesso di posizione Tesla; una posizione storica non è una promessa di posizione attuale.

Ricarica include barre giornaliere dei kWh aggiunti osservati, con periodi 7/30/90 giorni e un anno, selezione del giorno e aggiornamento locale ogni minuto. La raccolta usa charge_state.charge_energy_added, contatore Tesla di energia aggiunta alla batteria, non un contatore domestico o una misura della bolletta. Lo storico completo parte dall'installazione di questa versione: non vengono inventate ricariche passate. Ogni sessione usa il primo contatore osservato come riferimento; energia aggiunta prima di quel campione non viene inclusa. Reset del contatore o assenze di oltre tre minuti interrompono la sessione e segnalano dati parziali. Campioni duplicati e precedenti non vengono contati. Gli incrementi che attraversano mezzanotte sono ripartiti in proporzione al tempo e indicati come stima; i giorni seguono Europe/Rome. Una barra a zero indica nessuna energia registrata, non la certezza che non ci siano state ricariche.

Il secondo grafico mostra le osservazioni di capacità già disponibili, incluse quelle precedenti a questo aggiornamento. La capacità resta una stima da energia e SOC osservati su una ricarica con aumento di almeno 20 punti fino alla conclusione. Il riferimento iniziale è la mediana delle prime tre letture valide; una variazione compare dopo almeno tre letture successive, usando la mediana delle ultime dieci successive al riferimento. Il confronto non include gli stessi campioni nei due gruppi. Non viene mostrato un SOH certificato né una degradazione rispetto alla batteria da nuova: temperatura, arrotondamento e condizioni di carica influenzano la stima.

Tutti i nuovi dati sono in tabelle telemetry_* aggiuntive create automaticamente. Nessuna tabella esistente viene eliminata o svuotata. Per conservare i dati installare sullo stesso servizio e mantenere DATABASE_URL e il database PostgreSQL esistenti; il disco temporaneo del servizio non sostituisce un database persistente.

## Limiti Open-Meteo HTTP 429

La schermata ricevuta conferma HTTP 429 per meteo e quote. Dopo un 429 viene salvata una pausa comune a tutti i percorsi nella nuova telemetry_weather_provider_state: viene rispettato Retry-After (secondi o data HTTP), o una pausa di 30 minuti se manca. Il pulsante Riprova non supera questa pausa. Lo stato persiste ai riavvii. Le chiamate opzionali sono serializzate, con cache persistente delle risposte per sei ore per Forecast e 30 giorni per archivio/quote; richieste meteo della stessa giornata e area approssimata a 0,01° possono condividere i dati. I dati riusciti del singolo viaggio restano salvati.

Per i nuovi viaggi, se climate_state.outside_temp e il suo timestamp sono disponibili entro tre minuti dal primo campione di guida, la temperatura esterna viene salvata in telemetry_trip_ambient. Quando il modello meteo non risponde compare come Temperatura Tesla, senza vento o precipitazioni inventati. Il modello viene nuovamente cercato dopo la pausa. Le temperature dei viaggi passati non vengono ricostruite dalla temperatura attuale.

Queste modifiche riducono le richieste e gestiscono correttamente il blocco, ma non possono rimuovere un limite imposto dal fornitore. Un IP condiviso dell'hosting può concorrere al limite, senza che la sola schermata lo dimostri. Se il servizio gratuito continua a rispondere 429 è supportata la variabile facoltativa OPEN_METEO_API_KEY sul server, con una chiave cliente Open-Meteo valida. In quel caso vengono usati customer-api.open-meteo.com e customer-archive-api.open-meteo.com; la chiave non viene inviata al browser. L'accesso cliente richiede il servizio previsto da Open-Meteo e non viene attivato o acquistato dall'app.

Verifica: 69 test backend superati, build PWA completata e prove browser con rete simulata a 320/390/768/1360 px. Verificati ricariche multiple, copertura incompleta, mezzanotte italiana, duplicati, riavvio, separazione veicoli, confronto capacità, autenticazione, cache, blocco 429, temperatura Tesla, posizione, link navigazione, conferme, grafici e stati vuoti. Le prove non attestano che la quota del server Render dell'utente sia tornata disponibile.

## Ritocco Home: mappa compatta e sezioni espandibili

La mappa della Home è alta 165 px su desktop e 145 px su telefono, mentre quella dei percorsi conserva le proprie dimensioni. Le sezioni Altri comandi, Portiere e bagagliai, Pneumatici e profilo hanno icone, descrizioni e un indicatore + che ruota quando sono aperte. Restano elementi details/summary nativi, utilizzabili da tastiera con il focus visibile.

L'intestazione della Home mostra di nuovo VEICOLO ATTIVO, il modello e il selettore veicolo. Il modello proviene da vehicle_config.car_type di Tesla; vehicle_config viene incluso nelle richieste già esistenti, anche nel ramo senza GPS. Se Tesla non lo comunica viene mostrato Tesla, senza dedurlo o inventarlo dal telaio. L'eventuale nome personale viene mostrato separatamente. Stile Home rifinito con superfici scure più neutre, accenti blu, bordi discreti e pulsanti arrotondati. Nessuna modifica allo schema database.

Verificati build PWA, 69 test backend e prove browser: modello con nome veicolo assente, intestazione visibile, apertura/chiusura delle sezioni anche da tastiera, altezza mappa e assenza di overflow a 320/390/768/1360 px, conferme comandi, storico ricariche e blocco 429.

## Obiettivo risparmio 22.000 €

La nuova tab Ebreo Status visualizza una barra da 0 a 22.000 euro. Usa direttamente saving della stessa API autenticata utilizzata da Costi con periodo all (Tutti), per il veicolo selezionato, con aggiornamento ogni 15 secondi mentre la tab è aperta. Non esiste un accumulatore separato che possa duplicare i risparmi o divergere dai costi.

Il confronto sottrae il costo elettrico stimato dal diesel equivalente solo sui percorsi con entrambi i dati e le relative tariffe storiche. Un risparmio assente resta in attesa, non viene trattato come un costo elettrico nullo. I percorsi esclusi entreranno nel calcolo quando i dati mancanti saranno disponibili, secondo il recupero già previsto in Costi. Sono mostrati totale, percentuale, importo restante e traguardi 5.500/11.000/16.500 euro. Una differenza negativa viene conservata nel totale, con barra a zero; sopra 22.000 euro la barra resta al 100% e il totale effettivo continua a essere mostrato. La stima può diminuire al variare dei nuovi percorsi. Non comprende acquisto, manutenzione, assicurazione né perdite di ricarica.

Navigazione adattata a cinque tab anche su telefono. Build PWA e prove browser con dati simulati: valore mancante, zero, 50%, negativo, superamento obiettivo, collegamento a Costi e assenza di overflow a 320/390/768/1360 px. Nessuna modifica allo schema database o alle tariffe.

## Stima iniziale dei 32.517 km e tema blu/oro

Ebreo Status include ora una stima iniziale separata dai nuovi viaggi. Parametri richiesti: 32.517 km, 0,24 €/kWh e 2,189 €/L. Poiché il consumo elettrico medio storico non è stato fornito, viene usata esplicitamente l'ipotesi provvisoria di 16 kWh/100 km; il consumo diesel di confronto iniziale è 15,5 km/L. Questi due consumi sono visibili e modificabili nella pagina. Non sono dati misurati o ricavati dal VIN.

Con questi parametri l'elettrico storico è stimato in 1.248,65 €, il diesel equivalente in 4.592,24 € e la differenza iniziale in 3.343,59 €, pari a circa il 15,2% di 22.000 €. Il totale della tab non coincide più con Costi → Tutti: aggiunge la stima iniziale ai soli viaggi nuovi, indicati separatamente. I prezzi iniziali restano le medie richieste, non vengono sostituiti dai prezzi attuali.

La nuova telemetry_savings_baseline viene creata automaticamente, preservando le altre tabelle. La stima è assegnata al primo veicolo consultato in Ebreo Status e non viene copiata sugli altri veicoli dell'account. Il riferimento temporale è il 3 ottobre 2026 alle 20:20:50 Europe/Rome (18:20:50 UTC), quando è stato indicato il contachilometri. I viaggi che iniziano prima del riferimento, anche se conclusi dopo, non vengono aggiunti alla stima: la copertura del tratto che attraversa il riferimento non può essere divisa con certezza. I viaggi successivi entrano solo quando confrontabili, con la stessa energia e le stesse tariffe storiche di Costi. La stima persiste ai riavvii e gli aggiornamenti dei consumi non riscrivono i dati dei viaggi.

Tema blu/oro con Stella di David nella tab e nell'intestazione, menorah a sette bracci che segue il progresso e font David Libre per i testi della pagina. Le cifre principali mantengono un carattere leggibile. I font sono inclusi nel progetto e nella cache PWA, senza chiamate esterne durante l'uso; licenza e copyright sono in frontend/public/fonts/OFL.txt. Le icone sono SVG originali. Gli elementi grafici non influiscono sui calcoli.

Verifica: 75 test backend superati e build PWA completata. Prove browser con risposte simulate: dati assenti, saldo zero/negativo, percentuale intermedia, obiettivo superato, simboli, caricamento del font, campi dei consumi e larghezze 320/390/768/1360 px. Nessuna eliminazione del database esistente.
