# Clonazione SD e configurazione nuovi Raspberry FENCEWALL

Questa procedura serve per replicare la SD card master di FencingWallRack su piu Raspberry e prepararli per lavorare nella stessa rete senza conflitti.

Obiettivo:
- clonare la SD master da macOS;
- creare 6 SD identiche;
- personalizzare ogni Raspberry con hostname e rete diversi;
- mantenere il boot pulito, senza schermate firmware, scritte di sistema o procedure Raspberry di configurazione;
- verificare i servizi `fencingwallrack-kiosk` e `fencingwallrack-oled-network`.

> Nota importante: alcune impostazioni sono sulla SD, altre sono nella EEPROM del singolo Raspberry Pi 5. La EEPROM NON viene clonata con la SD. Per questo la sezione sul boot firmware va ripetuta su ogni Raspberry nuovo.

## 0. Metodo consigliato se le SD clonate non partono

Se le SD copiate non partono con errori tipo `p2 size extends beyond EOD`, non insistere con la clonazione bit-a-bit. Significa quasi sempre che le SD di destinazione sono leggermente piu piccole della SD originale.

Metodo consigliato:

1. Installa Raspberry Pi OS pulito su ogni SD con Raspberry Pi Imager.
2. Avvia ogni Raspberry.
3. Clona il progetto da GitHub.
4. Lancia lo script `tools/install-raspberry.sh`.
5. Fai la procedura EEPROM per nascondere la schermata rosa/bianca.

Sistema operativo consigliato:

- Debian GNU/Linux 13 `trixie` / Raspberry Pi OS equivalente 64-bit con Desktop.
- Architettura `aarch64`.
- Sessione grafica `x11` con `openbox` e `lxsession -s rpd-x -e LXDE`.
- Crea l'utente `fencewall` direttamente da Raspberry Pi Imager.
- Abilita SSH se vuoi configurare da remoto.
- Imposta locale/timezone Italia se richiesto.

Il Raspberry master usato durante lo sviluppo aveva questi valori:

```text
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
VERSION_ID="13"
VERSION_CODENAME=trixie
DEBIAN_VERSION_FULL=13.5
arch=aarch64
session=x11
openbox --config-file /home/fencewall/.config/openbox/rpd-rc.xml
/usr/bin/lxsession -s rpd-x -e LXDE
```

Comandi da eseguire sul Raspberry appena installato:

```bash
sudo apt update
sudo apt install -y git
cd /home/fencewall
git clone https://github.com/davidebrutto/FencingWallRack.git
cd /home/fencewall/FencingWallRack
sudo bash tools/install-raspberry.sh FENCEWALL-001
sudo reboot
```

Per gli altri Raspberry cambia solo il nome:

```bash
sudo bash tools/install-raspberry.sh FENCEWALL-002
sudo bash tools/install-raspberry.sh FENCEWALL-003
sudo bash tools/install-raspberry.sh FENCEWALL-004
sudo bash tools/install-raspberry.sh FENCEWALL-005
sudo bash tools/install-raspberry.sh FENCEWALL-006
```

Dopo il primo reboot, su ogni Raspberry fai anche la procedura EEPROM descritta nella sezione `7.5`, per togliere la schermata bianca/rosa del Raspberry Pi 5.

Lo script installatore configura automaticamente:

- pacchetti di sistema;
- Node.js/npm;
- Chromium;
- dipendenze Node del progetto;
- ambiente Python OLED;
- servizi systemd;
- SPI/I2C per display OLED;
- boot silenzioso Linux;
- splash Plymouth FENCEWALL;
- machine-id e chiavi SSH uniche;
- hostname, se passato come argomento;
- clone della seconda uscita HDMI tramite kiosk service.

Nota: la procedura EEPROM non viene automatizzata dallo script per sicurezza, perche scrive nella EEPROM fisica del Raspberry Pi 5.

## 1. Prima di clonare la SD master

Sul Raspberry master, prima di spegnerlo e clonarlo:

```bash
cd /home/fencewall/FencingWallRack
git status
```

Se ci sono modifiche locali che non vuoi tenere sulla SD master:

```bash
git stash push --include-untracked -m "backup-before-sd-clone"
git pull --ff-only
```

Verifica servizi:

```bash
systemctl status fencingwallrack-kiosk.service --no-pager
systemctl status fencingwallrack-oled-network.service --no-pager
```

Spegni correttamente:

```bash
sudo shutdown -h now
```

Quando il Raspberry e spento, rimuovi la SD.

## 2. Clonare la SD su macOS Sequoia

Inserisci la SD master nel Mac e identifica il disco:

```bash
diskutil list
```

Cerca il disco della SD, ad esempio `/dev/disk4`.

Attenzione: nei comandi seguenti sostituisci sempre `diskN` con il disco corretto. Se sbagli disco puoi sovrascrivere dati del Mac.

Smonta la SD:

```bash
diskutil unmountDisk /dev/diskN
```

Crea l'immagine della SD master:

```bash
sudo dd if=/dev/rdiskN of=~/Desktop/fencewall-master.img bs=4m status=progress
sync
diskutil eject /dev/diskN
```

Per scrivere l'immagine su una nuova SD, inserisci la nuova SD e identifica di nuovo il disco:

```bash
diskutil list
```

Smonta la nuova SD:

```bash
diskutil unmountDisk /dev/diskN
```

Scrivi l'immagine:

```bash
sudo dd if=~/Desktop/fencewall-master.img of=/dev/rdiskN bs=4m status=progress
sync
diskutil eject /dev/diskN
```

Ripeti questa scrittura per tutte le SD.

Consiglio: usa SD uguali o piu grandi della SD master.

## 3. Primo avvio di ogni Raspberry clonato

Inserisci la SD clonata nel Raspberry nuovo e avvia.

Appena possibile, apri un terminale locale o SSH.

Verifica il nome corrente:

```bash
hostname
```

## 4. Cambiare hostname per vedere nomi diversi in rete

Scegli un nome univoco per ogni Raspberry, ad esempio:

- `FENCEWALL-001`
- `FENCEWALL-002`
- `FENCEWALL-003`
- `FENCEWALL-004`
- `FENCEWALL-005`
- `FENCEWALL-006`

Esegui questi comandi sostituendo il nome:

```bash
NEW_HOST=FENCEWALL-002
sudo hostnamectl set-hostname "$NEW_HOST"
if grep -q '^127\.0\.1\.1' /etc/hosts; then
  sudo sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NEW_HOST/" /etc/hosts
else
  echo -e "127.0.1.1\t$NEW_HOST" | sudo tee -a /etc/hosts
fi
```

Verifica:

```bash
hostnamectl
cat /etc/hosts | grep 127.0.1.1
```

## 5. Rigenerare identificativi unici della macchina

Dopo una clonazione, piu Raspberry hanno lo stesso `machine-id`. Meglio rigenerarlo su ogni Raspberry clonato.

```bash
sudo truncate -s 0 /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id
sudo systemd-machine-id-setup
sudo ln -sf /etc/machine-id /var/lib/dbus/machine-id
```

Rigenera anche le chiavi SSH, cosi ogni Raspberry ha una identita diversa:

```bash
sudo rm -f /etc/ssh/ssh_host_*
sudo dpkg-reconfigure openssh-server
sudo systemctl restart ssh
```

## 6. Impostare IP, subnet e gateway

Usa il display OLED:

1. Premi il joystick centrale per entrare nel menu.
2. Vai su `NETWORK`.
3. Tieni premuto `K3` per entrare in edit.
4. Imposta IP, subnet mask e gateway della scheda ethernet.
5. Premi `K2` per salvare.

Consiglio: assegna IP diversi a ogni macchina, ad esempio:

- `FENCEWALL-001`: `192.168.1.101`
- `FENCEWALL-002`: `192.168.1.102`
- `FENCEWALL-003`: `192.168.1.103`
- `FENCEWALL-004`: `192.168.1.104`
- `FENCEWALL-005`: `192.168.1.105`
- `FENCEWALL-006`: `192.168.1.106`

## 7. Boot pulito: nascondere scritte e schermate Raspberry

Questa parte e fondamentale sui Raspberry Pi 5 nuovi.

### 7.1 Verificare cmdline Linux

Il file corretto su Raspberry Pi OS Bookworm e:

```bash
sudo nano /boot/firmware/cmdline.txt
```

Deve essere una sola riga. Mantieni i parametri gia presenti, ma assicurati che ci siano questi:

```text
quiet splash loglevel=0 systemd.show_status=false rd.udev.log_level=3 vt.global_cursor_default=0 logo.nologo plymouth.ignore-serial-consoles
```

Se presente, rimuovi:

```text
console=tty1
```

Non andare a capo dentro `cmdline.txt`.

### 7.2 Verificare config.txt

Apri:

```bash
sudo nano /boot/firmware/config.txt
```

Sotto `[all]` deve esserci:

```text
disable_splash=1
```

### 7.3 Verificare Plymouth

La SD clonata dovrebbe gia avere il tema FencingWallRack. Verifica:

```bash
sudo plymouth-set-default-theme
```

Se non e impostato, imposta il tema:

```bash
sudo plymouth-set-default-theme -R fencingwallrack
```

### 7.4 Disattivare cloud-init e userconfig

Sulla SD master dovrebbero gia essere disattivati. Su ogni Raspberry clonato puoi verificare:

```bash
systemctl list-unit-files | grep -E 'cloud|userconfig|first-boot'
```

Se vedi servizi cloud/userconfig non mascherati, esegui:

```bash
sudo systemctl mask cloud-init.service cloud-init-local.service cloud-init-main.service cloud-init-network.service cloud-config.service cloud-final.service cloud-init-hotplugd.service cloud-init-hotplugd.socket cloud-config.target cloud-init.target userconfig.service
```

### 7.5 Disattivare la schermata bianca/rosa “Configure this Raspberry Pi”

Questa schermata arriva dal bootloader EEPROM del Raspberry Pi 5, quindi va configurata su ogni Raspberry fisico. Non basta clonare la SD.

Apri la configurazione EEPROM:

```bash
sudo -E rpi-eeprom-config --edit
```

Aggiungi o modifica queste righe:

```text
NET_INSTALL_ENABLED=0
NET_INSTALL_AT_POWER_ON=0
```

Se la schermata firmware compare ancora, aggiungi anche:

```text
DISABLE_HDMI=1
```

Nota: `DISABLE_HDMI=1` disattiva l'output HDMI del bootloader, non quello di Linux. Serve proprio a evitare la schermata firmware prima del caricamento del sistema operativo.

Salva, esci e riavvia:

```bash
sudo reboot
```

Se vuoi controllare il risultato:

```bash
rpi-eeprom-config | grep -E 'NET_INSTALL|DISABLE_HDMI'
```

## 8. Verificare i servizi FENCEWALL

Dopo il reboot:

```bash
systemctl status fencingwallrack-kiosk.service --no-pager -l
systemctl status fencingwallrack-oled-network.service --no-pager -l
```

Se serve riavviare:

```bash
sudo systemctl restart fencingwallrack-kiosk.service
sudo systemctl restart fencingwallrack-oled-network.service
```

Verifica che il server risponda:

```bash
curl -fsS http://127.0.0.1:5000 >/dev/null && echo OK
```

## 9. Verificare configurazione kiosk

Controlla:

```bash
cat /etc/default/fencingwallrack-kiosk
```

Valori importanti:

```text
APP_DIR=/home/fencewall/FencingWallRack
KIOSK_URL=http://127.0.0.1:5000
HOST=0.0.0.0
PORT=5000
SERIAL_PORT=/dev/ttyUSB0
SERIAL_BAUD=38400
KIOSK_DISPLAY_PROFILE=ledwall
KIOSK_LEDWALL_WALLPAPER=/home/fencewall/FencingWallRack/static/desktop-ledwall.png
KIOSK_UNDERFLOOR_WALLPAPER=/home/fencewall/FencingWallRack/static/desktop-sottopedana.png
```

Per cambiare `ledwall` / `sottopedana`, usa il display OLED alla voce `MODE`.

### 9.1 Clonare la seconda uscita HDMI

Il progetto gestisce il clone della seconda uscita HDMI direttamente nello script del servizio kiosk. Quindi questa modifica puo arrivare via GitHub con `UPDATE` dal display.

Comportamento predefinito:

```text
KIOSK_MIRROR_DISPLAYS=1
```

Con `1`, se il Raspberry vede due uscite video collegate, la seconda viene messa in clone della prima tramite `xrandr`. In questo modo il monitor di controllo mostra la stessa immagine mandata al ledwall.

Per verificare i nomi delle uscite video:

```bash
DISPLAY=:0 XAUTHORITY=/home/fencewall/.Xauthority xrandr --query
```

Se vuoi forzare quale HDMI e principale e quale deve essere clonata, aggiungi in `/etc/default/fencingwallrack-kiosk`:

```text
KIOSK_MIRROR_DISPLAYS=1
KIOSK_MIRROR_PRIMARY_OUTPUT=HDMI-1
KIOSK_MIRROR_SECONDARY_OUTPUT=HDMI-2
```

I nomi possono essere diversi, ad esempio `HDMI-1`, `HDMI-2`, `HDMI-A-1`, `HDMI-A-2`. Usa quelli mostrati da `xrandr --query`.

Se serve forzare una risoluzione comune:

```text
KIOSK_MIRROR_MODE=1920x1080
```

Se su una macchina vuoi lasciare i monitor estesi e non clonati:

```text
KIOSK_MIRROR_DISPLAYS=0
```

Dopo una modifica:

```bash
sudo systemctl restart fencingwallrack-kiosk.service
```

## 10. Usare UPDATE e REBOOT dal display

Dal display OLED:

- `UPDATE`: esegue aggiornamento GitHub.
- Se ci sono modifiche locali, vengono salvate in uno stash chiamato `oled-update-backup-...`.
- Se vengono aggiornati file, il display propone `K2 reboot`.
- `REBOOT`: riavvia FENCEWALL dopo conferma con `K2`.

Se l'update da display dovesse bloccarsi, usa da terminale:

```bash
cd /home/fencewall/FencingWallRack
git status
git stash push --include-untracked -m "manual-backup-before-update"
git pull --ff-only
sudo systemctl restart fencingwallrack-oled-network.service
```

## 11. Checklist finale per ogni Raspberry

Per ogni macchina verifica:

- Hostname diverso dagli altri.
- IP ethernet diverso dagli altri.
- `machine-id` rigenerato.
- Chiavi SSH rigenerate.
- Boot senza schermata bianca/rosa Raspberry.
- Boot senza testo Linux visibile.
- Servizio kiosk attivo.
- Servizio OLED attivo.
- Pagina raggiungibile da rete: `http://IP_DEL_RASPBERRY:5000`.
- Modalita `LEDWALL` e `SOTTOPEDANA` selezionabili dal display.
- Seconda uscita HDMI in clone della prima, se usi un monitor di controllo.
- Voce `UPDATE` funzionante dal display.
- Voce `REBOOT` funzionante dal display.

## 11.1 Troubleshooting installazione pulita

### Errore grafico: `Failed to start session`

Se dopo l'installazione pulita compare la schermata login e, inserendo la password, appare:

```text
Failed to start session
```

il sistema operativo si e avviato, ma manca o non e configurata correttamente la sessione desktop X11/LXDE usata da FENCEWALL.

Entra da SSH oppure passa a console testuale con `Ctrl+Alt+F2`, fai login come `fencewall` e lancia:

```bash
sudo apt update
sudo apt install -y lightdm xserver-xorg lxsession lxde-core openbox lxpanel pcmanfm x11-xserver-utils x11-utils wmctrl chromium-browser
sudo apt install -y raspberrypi-ui-mods || true
SESSION=$(for s in LXDE-pi rpd-x LXDE openbox; do [ -f "/usr/share/xsessions/$s.desktop" ] && echo "$s" && break; done)
SESSION=${SESSION:-LXDE-pi}
printf '[Desktop]
Session=%s
' "$SESSION" > ~/.dmrc
sudo chown fencewall:fencewall ~/.dmrc
sudo rm -f /var/lib/AccountsService/users/fencewall
sudo mkdir -p /etc/lightdm/lightdm.conf.d
printf '[Seat:*]
autologin-user=fencewall
autologin-user-timeout=0
user-session=%s
autologin-session=%s
greeter-session=lightdm-greeter
' "$SESSION" "$SESSION" | sudo tee /etc/lightdm/lightdm.conf.d/50-fencewall-autologin.conf
sudo sed -i -E \
  -e "s|^greeter-session=.*|greeter-session=lightdm-greeter|" \
  -e "s|^user-session=.*|user-session=$SESSION|" \
  -e "s|^autologin-user=.*|autologin-user=fencewall|" \
  -e "s|^#?autologin-user-timeout=.*|autologin-user-timeout=0|" \
  -e "s|^autologin-session=.*|autologin-session=$SESSION|" \
  /etc/lightdm/lightdm.conf
sudo systemctl set-default graphical.target
sudo systemctl enable lightdm.service
sudo systemctl restart lightdm.service
```

Se non riparte la grafica, riavvia:

```bash
sudo reboot
```

Lo script `tools/install-raspberry.sh` ora esegue automaticamente questa configurazione e non usa piu `raspi-config do_boot_behaviour B4`, per evitare che `.dmrc` venga riscritto su sessioni non presenti come `rpd-labwc`.

## 12. Troubleshooting clonazione SD

### 12.1 Errore: `mmcblk0: p2 size extends beyond EOD` / `PARTUUID ... does not exist`

Se all'avvio compare una schermata con messaggi simili a:

```text
mmcblk0: p2 size ... extends beyond EOD, truncated
Gave up waiting for root file system device
ALERT! PARTUUID=... does not exist. Dropping to a shell!
```

non e un problema dell'applicazione FENCEWALL. E quasi sempre un problema della clonazione SD.

Cause piu probabili:

- La SD di destinazione e leggermente piu piccola della SD master, anche se nominalmente ha la stessa capacita.
- La scrittura con `dd` non e arrivata a fine copia.
- La SD di destinazione e difettosa o non viene letta correttamente dal Raspberry.
- E stata scelta la periferica sbagliata durante la scrittura.

Soluzione consigliata:

1. Usa una SD di destinazione piu grande della master, ad esempio master da 32GB e copie su SD da 64GB.
2. Ricrea la copia con `dd`.
3. Attendi sempre il completamento di `dd`, poi esegui `sync` prima di estrarre la SD.

Su macOS puoi confrontare le dimensioni reali delle SD con:

```bash
diskutil list
```

Oppure, per vedere i byte esatti del disco:

```bash
diskutil info /dev/diskN | grep -E 'Disk Size|Device Block Size|Total Size'
```

Se vuoi mantenere SD tutte della stessa capacita nominale, compra un lotto dello stesso modello ma considera che due SD da 32GB possono avere dimensioni reali leggermente diverse. Per clonazioni affidabili, la SD destinazione deve essere uguale o piu grande in byte rispetto alla SD master.

Se la SD e gia stata scritta e mostra questo errore, non conviene tentare riparazioni sul Raspberry: rifai la SD partendo dall'immagine master e da una scheda piu grande o sicuramente non piu piccola.

### 12.2 Errore Chromium dopo clonazione: profilo in uso su un altro Raspberry

Se il servizio kiosk non parte e nel log compare un messaggio simile a:

```text
The profile appears to be in use by another Chromium process (...) on another computer (FENCEWALL-001)
Chromium has locked the profile so that it doesn't get corrupted
```

significa che la SD clonata ha copiato anche i lock temporanei dei profili Chromium del Raspberry master. Non e un problema della SD e non e un problema dell'applicazione.

Soluzione immediata sul Raspberry clonato:

```bash
sudo systemctl stop fencingwallrack-kiosk.service

find /home/fencewall/.config \
  \( -name 'SingletonLock' -o -name 'SingletonSocket' -o -name 'SingletonCookie' -o -name 'Singleton*' \) \
  -print -delete

sudo chown -R fencewall:fencewall /home/fencewall/.config/chrome-profile-1 \
  /home/fencewall/.config/chrome-profile-2 \
  /home/fencewall/.config/chrome-underfloor-left-a \
  /home/fencewall/.config/chrome-underfloor-left-b \
  /home/fencewall/.config/chrome-underfloor-right-a \
  /home/fencewall/.config/chrome-underfloor-right-b 2>/dev/null || true

sudo systemctl start fencingwallrack-kiosk.service
sudo systemctl status fencingwallrack-kiosk.service --no-pager -l
```

Se Chromium fosse ancora realmente aperto:

```bash
pkill -u fencewall -f chromium
sudo systemctl restart fencingwallrack-kiosk.service
```

Lo script `tools/systemd/run-kiosk-stack.sh` elimina automaticamente questi lock temporanei prima di avviare Chromium, quindi dopo un aggiornamento GitHub il problema non dovrebbe ripresentarsi sui prossimi cloni.
