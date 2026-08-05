# FenceWall Media Portal

Webapp PHP/MySQL per Aruba Business/Plesk.

## Installazione Rapida

1. Carica tutto il contenuto di questa cartella nella document root del dominio, ad esempio `httpdocs`.
2. Copia `config.example.php` in `config.php`.
3. Compila `config.php` con database, `base_url` e `asset_token`.
4. Apri `https://fencewall.sportlabweb.it/install.php`.
5. Crea il primo utente admin.
6. Elimina `install.php` dal server.

## Endpoint Per Raspberry

Video pausa:

```text
https://fencewall.sportlabweb.it/api/pause-videos/manifest.php?token=TOKEN
```

Foto atleti:

```text
https://fencewall.sportlabweb.it/api/athlete-photos/manifest.php?token=TOKEN
```

## Configurazione Raspberry

Nel file `/etc/default/fencingwallrack-kiosk`:

```bash
REMOTE_ASSET_BASE_URL=https://fencewall.sportlabweb.it
REMOTE_VIDEO_MANIFEST_PATH=/api/pause-videos/manifest.php?token=TOKEN
REMOTE_PHOTO_MANIFEST_PATH=/api/athlete-photos/manifest.php?token=TOKEN
REMOTE_ASSET_TIMEOUT_MS=15000
```

`TOKEN` deve corrispondere a `asset_token` in `config.php`.

## Bandiere Forzate Per Atleta

Nella sezione `Foto` ogni atleta puo usare:

- `BANDIERA STANDARD`: il Raspberry mostra la bandiera calcolata dalla nazione ricevuta dal protocollo USB.
- una bandiera scelta dall'elenco: il Raspberry forza quella bandiera solo per quell'atleta.

L'elenco viene letto da:

```text
storage/flags
```

Questa cartella deve essere caricata sul server insieme al portale. I nomi mostrati nell'elenco sono i nomi dei file senza estensione, ordinati alfabeticamente.

Il database usa la colonna `photos.flag_override`. Se il portale viene aggiornato su un database gia esistente, la colonna viene creata automaticamente aprendo la sezione Foto o il manifest foto, se l'utente MySQL ha permesso `ALTER TABLE`.
