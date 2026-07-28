# Graphics Rollback - baseline 2026-07-28

Questo punto salva la grafica funzionante prima della nuova revisione completa di ledwall e sottopedana.

## CSS originali ancora intatti

I file originali non vengono modificati durante la nuova lavorazione:

- `static/mystyle.css`
- `static/rear.css`
- `static/underfloor.css`

Le pagine ora usano i CSS di lavoro:

- `static/mystyle-next.css`
- `static/rear-next.css`
- `static/underfloor-next.css`

## Copia archivio

Una copia dei CSS al momento del salvataggio si trova in:

`static/css-backups/graphics-baseline-20260728/`

## Tornare subito alla grafica precedente

Per tornare alla grafica precedente senza cancellare i CSS nuovi, ripristinare i link nei template:

In `templates/base.html`:

```html
{{url_for('static', filename='mystyle.css')}}
{{url_for('static', filename='rear.css')}}
```

In `templates/underfloor.html`:

```html
{{url_for('static', filename='underfloor.css')}}
```

Poi riavviare il servizio sul Raspberry:

```bash
sudo systemctl restart fencingwallrack-kiosk.service
```

## Ripartire dal backup dentro i CSS nuovi

Se invece vuoi mantenere i template collegati ai file `*-next.css`, ma riportare il contenuto alla grafica salvata:

```bash
cd /home/fencewall/FencingWallRack
cp static/css-backups/graphics-baseline-20260728/mystyle.css static/mystyle-next.css
cp static/css-backups/graphics-baseline-20260728/rear.css static/rear-next.css
cp static/css-backups/graphics-baseline-20260728/underfloor.css static/underfloor-next.css
sudo systemctl restart fencingwallrack-kiosk.service
```
