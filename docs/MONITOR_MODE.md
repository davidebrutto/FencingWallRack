# Modalita MONITOR

Dal menu OLED scegliere `MODE`, entrare in modifica con una pressione lunga di K3,
selezionare `MONITOR` e salvare con K2. Il FENCEWALL si riavvia.

In questa modalita le uscite HDMI sono **estese**, non clonate: su ogni monitor
collegato si apre un browser senza barre, sulla stessa pagina `/monitor`.
Se e collegato solo il primo monitor, viene aperta una sola finestra.

Il sistema legge automaticamente con `xrandr` risoluzione e posizione di ogni
monitor. Non serve scegliere 16:9 o 4:3 dall'OLED: la grafica viene adattata
proporzionalmente allo spazio disponibile e centrata su fondo nero, senza
deformazioni. I due monitor possono avere risoluzioni e proporzioni diverse.

Le modalita `LEDWALL` e `SOTTOPEDANA` mantengono le loro impostazioni HDMI e
le loro finestre precedenti. Il valore `KIOSK_MIRROR_DISPLAYS=1` non forza il
clone quando e selezionato `MONITOR`.

In caso di rilevamento errato delle uscite, le opzioni facoltative in
`/etc/default/fencingwallrack-kiosk` sono:

```text
KIOSK_MONITOR_PRIMARY_OUTPUT=HDMI-1
KIOSK_MONITOR_SECONDARY_OUTPUT=HDMI-2
```

I nomi effettivi si leggono con `DISPLAY=:0 xrandr --query`. La configurazione
di base non richiede modifiche a questo file.
