# Prova Wi-Fi via Bluetooth (non ancora per produzione)

Questa prova **non modifica** il servizio kiosk, il menu OLED o la configurazione Ethernet. Il programma si avvia a mano da VNC su **un solo FENCEWALL** e si ferma dopo 5 minuti o con `Ctrl+C`. Per il telefono, usare **nRF Connect for Mobile** (iOS/Android). Non e ancora una schermata guidata per l'utente finale.

## Prima della prova

La versione stabile e identificata dal tag locale `stable-pre-bluetooth-1.1.9` sul Mac di sviluppo. Il prototipo aggiunge solo i file in questa cartella; non e installato ne avviato automaticamente con `UPDATE` OLED. Eseguire un eventuale aggiornamento del codice solo sul FENCEWALL scelto per il test. Conservare l'accesso VNC/Ethernet mentre si prova il Wi-Fi.

Sul FENCEWALL di prova, aprire un terminale VNC:

```sh
cd /home/fencewall/FencingWallRack
sudo apt update
sudo apt install -y bluez python3-dbus python3-gi
bluetoothctl show
nmcli device status
```

Verificare che ci siano un controller Bluetooth e `wlan0`. Poi avviare:

```sh
cd /home/fencewall/FencingWallRack/tools/ble_wifi_trial
sudo /usr/bin/python3 provision.py
```

Nel terminale compare un PIN casuale di sei cifre. Sul telefono, aprire nRF Connect, cercare **FW-WIFI** e connettersi. Nel servizio che inizia con `26c40000`, scrivere in UTF-8/testo:

1. Caratteristica finale `0001`: SSID della rete Wi-Fi.
2. Caratteristica finale `0002`: password WPA2 (8-63 byte).
3. Caratteristica finale `0003`: PIN mostrato nel terminale, per confermare.
4. Leggere la caratteristica finale `0004`: `READY`, `CONNECTING`, `CONNECTED` o `FAILED`.

Le scritture richiedono una connessione BLE cifrata; il telefono potrebbe chiedere l'abbinamento. Se l'abbinamento non parte, da un **secondo terminale VNC** usare `bluetoothctl`, poi `agent NoInputNoOutput` e `default-agent`, lasciando aperto quel terminale per la durata della prova. Questo e un esperimento con pairing Just Works e PIN applicativo: usare solo in un ambiente controllato, non come funzione di produzione.

Se nRF Connect indica che una scrittura e troppo lunga, attivare il long write nell'app. Questo prototipo accetta una sola scrittura completa per caratteristica, non frammenti separati.

## Verifica

```sh
nmcli -f NAME,TYPE,DEVICE connection show --active
ip -4 addr show dev wlan0
ip -4 addr show dev eth0
```

`eth0` deve restare invariata. Il profilo Wi-Fi di prova si chiama `FENCEWALL-BLE-TEST`, ha `autoconnect=no` e non prende la route predefinita: quindi non verra riattivato automaticamente dopo un riavvio e non sostituisce il percorso Internet Ethernet. Se il Wi-Fi fallisce, il programma resta disponibile fino allo scadere dei 5 minuti, ma il profilo di prova puo restare salvato.

## Rollback

Nel terminale del programma premere `Ctrl+C` (oppure attendere i 5 minuti). Poi, **solo sul FENCEWALL di prova**:

```sh
sudo nmcli connection delete id FENCEWALL-BLE-TEST
nmcli -f NAME,TYPE,DEVICE connection show --active
```

Il comando elimina il solo profilo creato da questa prova; non tocca la rete Ethernet o altri profili Wi-Fi. Se il programma non e stato installato come servizio, non c'e altro da disattivare. I pacchetti `bluez`, `python3-dbus` e `python3-gi` possono rimanere installati: non cambiano l'avvio del kiosk. Non usare `git reset --hard` sul FENCEWALL.
