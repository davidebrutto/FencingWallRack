# FENCEWALL - Handover tecnico per Codex

Ultimo aggiornamento: 16/08/2026

Questo file serve per riprendere il progetto FENCEWALL da un altro Mac/PC o da una nuova chat Codex, senza dipendere dalla cronologia completa della conversazione originale.

Quando si apre il progetto con Codex su un altro computer, il primo messaggio consigliato e':

```text
Leggi docs/FENCEWALL_HANDOVER_TECNICO.md e aiutami su questo progetto. Prima di modificare file, controlla git status e spiegami cosa toccherai.
```

## 1. Identita' del progetto

FENCEWALL e' un sistema per visualizzare dati di gara di scherma su ledwall e sottopedana.

Il sistema principale gira su FENCEWALL, riceve dati da seriale, li interpreta e aggiorna in tempo reale pagine Chromium kiosk tramite WebSocket.

Componenti principali:

- Applicazione Node.js: `server.js`
- Pagine Nunjucks/HTML: `templates/`
- CSS e asset: `static/`
- Configurazione kiosk systemd: `tools/systemd/`
- Configurazione display OLED: `tools/oled_network/`
- Portale media PHP: `remote-portal/`
- Documentazione utente: `docs/FenceWall_Manuale_Utente.docx` e `docs/FenceWall_Manuale_Utente.pdf`
- Procedura SD e setup FENCEWALL: `docs/SD_CLONING_AND_RASPBERRY_SETUP.md`
- Rollback grafica: `docs/GRAPHICS_ROLLBACK.md`

Repository ufficiale:

```text
https://github.com/davidebrutto/FencingWallRack.git
```

Branch principale:

```text
main
```

## 2. Cosa deve sapere un nuovo Codex

Il progetto e' stato sviluppato con molte iterazioni pratiche direttamente sui FENCEWALL. Prima di intervenire bisogna sempre controllare il contesto reale dei file.

Regole operative importanti:

- Non modificare file a caso fuori dal progetto.
- Non cancellare modifiche locali senza chiedere.
- Prima di modificare, eseguire sempre `git status --short`.
- Se `.DS_Store` risulta modificato, ignorarlo salvo richiesta esplicita.
- I file runtime come database, score e stati locali non devono bloccare gli update.
- Le modifiche definitive devono finire su GitHub, perche' i FENCEWALL aggiornano da li'.

Comando di controllo iniziale:

```bash
cd ~/FencingWallRack
git status --short
git branch --show-current
git remote -v
```

Su Mac di sviluppo, se il progetto e' su disco esterno, il path usato spesso e':

```text
/Volumes/progetti/FencingWallRack/FencingWallRack
```

Su FENCEWALL, il path standard e':

```text
/home/fencewall/FencingWallRack
```

## 3. Come aprire Codex da un altro Mac o PC

Codex e' dentro l'app desktop ChatGPT. La cronologia Codex e' separata dalla cronologia ChatGPT e puo' non apparire uguale tra dispositivi o workspace. Per questo la fonte affidabile deve essere il repository GitHub piu' questo file.

Procedura consigliata:

1. Installare l'app desktop ChatGPT sul nuovo Mac/PC.
2. Accedere con lo stesso account OpenAI/ChatGPT usato per il progetto.
3. Dal menu in alto a sinistra selezionare `Codex`.
4. Clonare il repository in una cartella locale.
5. Aprire in Codex la cartella clonata.
6. Scrivere a Codex di leggere questo file.

Esempio su Mac:

```bash
cd ~/Documents
git clone https://github.com/davidebrutto/FencingWallRack.git
cd FencingWallRack
```

Poi in Codex aprire la cartella:

```text
~/Documents/FencingWallRack
```

Messaggio da mandare a Codex:

```text
Leggi docs/FENCEWALL_HANDOVER_TECNICO.md e aiutami su questo progetto. Siamo in trasferta, quindi dammi sempre comandi chiari e non fare modifiche distruttive.
```

## 4. Cosa copiare se non si vuole dipendere solo da GitHub

Prima della trasferta conviene avere anche una copia fisica su chiavetta o disco:

- cartella completa del progetto;
- manuale PDF;
- file `docs/FENCEWALL_HANDOVER_TECNICO.md`;
- eventuali credenziali/token GitHub in un posto sicuro, non dentro il repository;
- eventuali credenziali del portale in un posto sicuro, non dentro il repository.

Attenzione: non salvare password o token dentro file versionati.

## 5. Setup rapido su un nuovo Mac di supporto

Installare strumenti base:

```bash
xcode-select --install
```

Installare Node.js LTS se manca. Con Homebrew:

```bash
brew install node git
```

Clonare il progetto:

```bash
cd ~/Documents
git clone https://github.com/davidebrutto/FencingWallRack.git
cd FencingWallRack
npm install
```

Avvio locale senza seriale reale, solo per verificare che il server parta:

```bash
HOST=127.0.0.1 PORT=5000 npm start
```

Avvio locale con seriale su Mac, adattare la porta:

```bash
SERIAL_PORT=/dev/cu.usbserial-B0043XM7 SERIAL_BAUD=38400 HOST=127.0.0.1 PORT=5000 npm start
```

Aprire:

```text
http://127.0.0.1:5000
```

## 6. Setup e update su FENCEWALL

Path standard:

```bash
cd /home/fencewall/FencingWallRack
```

Aggiornamento normale:

```bash
git pull
npm install
sudo systemctl restart fencingwallrack-kiosk.service
sudo systemctl restart fencingwallrack-oled-network.service
```

Controllo servizi:

```bash
systemctl status fencingwallrack-kiosk.service --no-pager -l
systemctl status fencingwallrack-oled-network.service --no-pager -l
```

Log kiosk:

```bash
journalctl -u fencingwallrack-kiosk.service -f
```

Log OLED:

```bash
journalctl -u fencingwallrack-oled-network.service -f
```

Se Chromium segnala profili bloccati dopo clonazione SD:

```bash
pkill chromium || true
rm -f ~/.config/chrome-profile-1/Singleton*
rm -f ~/.config/chrome-profile-2/Singleton*
rm -f ~/.config/chrome-underfloor-left-a/Singleton*
rm -f ~/.config/chrome-underfloor-left-b/Singleton*
rm -f ~/.config/chrome-underfloor-right-a/Singleton*
rm -f ~/.config/chrome-underfloor-right-b/Singleton*
sudo systemctl restart fencingwallrack-kiosk.service
```

## 7. Menu OLED attuale

La schermata iniziale mostra logo e nome FENCEWALL.

Dal joystick centrale si entra nel menu. Le voci principali sono:

- `NETWORK`: configurazione IP cavo Ethernet.
- `MODE`: scelta `LEDWALL` o `SOTTOPEDANA`.
- `SPOT`: minuti di inattivita' prima della pubblicita'.
- `AVATAR ATLETA`: abilita/disabilita placeholder atleta.
- `MANUALE`: mostra QRCode per il manuale online.
- `VERSIONE`: mostra versione firmware e informazioni tecniche.
- `UPDATE`: scarica aggiornamenti dal server GitHub e installa dipendenze richieste.
- `REBOOT`: riavvia FENCEWALL.
- `POWER OFF`: spegne correttamente FENCEWALL.

Comandi fisici:

- Pulsante verde: indietro fino al logo.
- Pulsante bianco: salva/conferma.
- Pulsante rosso: usato dove previsto dal menu.
- Joystick: navigazione e ingresso menu.

## 8. Configurazione kiosk

File di configurazione su FENCEWALL:

```text
/etc/default/fencingwallrack-kiosk
```

Esempio nel repository:

```text
tools/systemd/fencingwallrack-kiosk.env.example
```

Variabili importanti:

```text
APP_DIR=/home/fencewall/FencingWallRack
KIOSK_DISPLAY_PROFILE=ledwall
KIOSK_SET_WALLPAPER=1
KIOSK_DISABLE_POWER_SAVE=1
KIOSK_MIRROR_DISPLAYS=1
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=38400
SERIAL_MODE=soh_eot
HOST=0.0.0.0
PORT=5000
SPOT_INACTIVITY_MINUTES=5
ATHLETE_PLACEHOLDER_ENABLED=1
```

Profili:

- `ledwall`: uscita frontale e posteriore.
- `sottopedana`: uscita sinistra e destra sottopedana.

L'OLED modifica alcune impostazioni dentro questo file.

## 9. Configurazione OLED

File di configurazione su FENCEWALL:

```text
/etc/default/fencingwallrack-oled-network
```

Esempio nel repository:

```text
tools/oled_network/fencingwallrack-oled-network.env.example
```

Variabili importanti:

```text
NET_IFACE=eth0
OLED_FLIP_180=1
OLED_INPUT_FLIP_180=1
OLED_LOGO_PATH=/home/fencewall/FencingWallRack/tools/oled_network/logo.png
OLED_MANUAL_URL=https://fencewall.sportlabweb.it/manuale
OLED_UPDATE_APT_PACKAGES=ffmpeg
```

## 10. Portale media

Dominio:

```text
https://fencewall.sportlabweb.it
```

Funzioni principali:

- gestione video pubblicitari;
- gestione foto atleti;
- gestione override bandiera per singolo atleta;
- manifest per download automatico su FENCEWALL;
- manuale online.

Cartella nel repository:

```text
remote-portal/
```

Manuale PDF usato dal portale:

```text
remote-portal/assets/manuale-fencewall.pdf
```

Route manuale:

```text
https://fencewall.sportlabweb.it/manuale
```

## 11. Dati seriali e parsing

Il sistema legge dati seriali a 38400 baud.

Messaggi principali usati:

- luci: `[SOH][DC4]R...G...W...w...[EOT]`
- timer: `[SOH][DC3]R/N/B/J[STX]MM:SS.DC[EOT]`
- dati competitori: `[SOH][DC3]D[STX]XX:YY...`
- nomi/nazioni: messaggi opzionali del protocollo;
- passivita': `[SOH][DC3]UF[STX]m:ss[STX]PCard_Right[STX]PCard_Left[EOT]`

Il parsing lavora a frame delimitati da SOH/EOT, non su righe fisse.

Il timer cambia colore:

- `R`: verde;
- `N`: rosso;
- `B` o `J`: giallo.

La pubblicita' parte se:

- non arriva nessun dato seriale per circa 10 secondi;
- oppure il timer rimane invariato per il numero di minuti configurato in `SPOT`.

Il ritorno dal video al tabellone avviene quando cambiano dati importanti, tra cui timer, nome atleta, inversione nomi/posizioni e periodo.

## 12. Asset locali importanti

Cartelle principali:

```text
static/flags/
static/pause-video/
static/athlete-photos/
static/desktop-ledwall.png
static/desktop-sottopedana.png
```

Placeholder atleta:

```text
static/athlete-placeholder-dx.png
static/athlete-placeholder-sx.png
```

Bandiere speciali gestite:

```text
static/flags/ain.svg
static/flags/olympic_flag.svg
```

`AIN` usa `ain.svg`.

`EOR` usa `olympic_flag.svg`.

## 13. Video pubblicitari

I video pubblicitari vengono scaricati dal portale e possono essere ottimizzati localmente con `ffmpeg`.

Il menu OLED `UPDATE` installa anche pacchetti richiesti come `ffmpeg`, se configurato.

Per verificare ffmpeg:

```bash
ffmpeg -version
```

Per evitare spegnimento schermo:

```bash
DISPLAY=:0 xset q
```

Il risultato corretto deve includere:

```text
timeout:  0    cycle:  0
DPMS is Disabled
```

## 14. Problemi Git frequenti

Se `git pull` segnala file locali modificati e vuoi prendere la versione GitHub, prima capire quali file sono coinvolti:

```bash
cd /home/fencewall/FencingWallRack
git status --short
```

Mai usare comandi distruttivi senza sapere cosa si perde.

Se il problema riguarda solo file runtime locali, di solito vanno esclusi o rimossi dalla working tree solo se sicuro. Chiedere a Codex prima.

Se il problema e' `.DS_Store`, normalmente non e' rilevante.

## 15. Procedura consigliata in trasferta

Prima di partire:

1. Verificare che tutte le modifiche siano su GitHub.
2. Portare un secondo Mac/PC con ChatGPT Desktop e accesso Codex.
3. Portare copia locale del progetto su chiavetta.
4. Portare credenziali GitHub/token in luogo sicuro.
5. Portare cavo rete e adattatori necessari.
6. Verificare che ogni FENCEWALL mostri la versione corretta dal menu OLED `VERSIONE`.
7. Verificare che ogni FENCEWALL possa eseguire `UPDATE`.
8. Verificare il manuale via QRCode dal menu OLED `MANUALE`.

Su ogni FENCEWALL installato:

1. Collegare rete internet.
2. Accendere FENCEWALL.
3. Controllare da OLED `VERSIONE`.
4. Se serve, eseguire `UPDATE`.
5. Se richiesto, eseguire `REBOOT`.
6. Configurare `NETWORK` se l'impianto richiede IP statico.
7. Configurare `MODE` in base al cablaggio: `LEDWALL` o `SOTTOPEDANA`.
8. Configurare `SPOT`.
9. Verificare seriale e visualizzazione dati.

## 16. Comandi utili sul posto

IP del FENCEWALL:

```bash
ip addr show eth0
```

Verifica server locale:

```bash
curl -I http://127.0.0.1:5000
```

Verifica pagine principali:

```bash
curl -fsS http://127.0.0.1:5000 >/dev/null && echo OK front
curl -fsS http://127.0.0.1:5000/rear >/dev/null && echo OK rear
curl -fsS http://127.0.0.1:5000/underfloor-left-a >/dev/null && echo OK left-a
curl -fsS http://127.0.0.1:5000/underfloor-left-b >/dev/null && echo OK left-b
curl -fsS http://127.0.0.1:5000/underfloor-right-a >/dev/null && echo OK right-a
curl -fsS http://127.0.0.1:5000/underfloor-right-b >/dev/null && echo OK right-b
```

Restart servizi:

```bash
sudo systemctl restart fencingwallrack-kiosk.service
sudo systemctl restart fencingwallrack-oled-network.service
```

Stato servizi:

```bash
systemctl status fencingwallrack-kiosk.service --no-pager -l
systemctl status fencingwallrack-oled-network.service --no-pager -l
```

Spegnimento sicuro da terminale:

```bash
sudo poweroff
```

Riavvio da terminale:

```bash
sudo reboot
```

## 17. Se Codex nuovo non conosce la storia

Incollare questo prompt:

```text
Questo progetto e' FENCEWALL. Leggi docs/FENCEWALL_HANDOVER_TECNICO.md, poi controlla git status. Non fare reset o cancellazioni senza chiedere. Quando proponi comandi per FENCEWALL, dammeli in blocchi pronti da incollare. Quando modifichi file, verifica con test o controlli sintattici.
```

Poi descrivere il problema specifico.

