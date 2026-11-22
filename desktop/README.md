# SwitchModderSHOP Catalog Manager (Windows)

Strumento grafico autonomo per modificare il catalogo gestito da
[SwitchModderSHOP-Catalog](https://github.com/and48-spec/SwitchModderSHOP-Catalog).

## Avvio

Scaricare l'artifact Windows dalla workflow **Build Windows Catalog Manager**
oppure compilare l'eseguibile con PyInstaller. Il programma non necessita di
Python installato quando eseguito come EXE.

Per avvio da sorgente: Python 3.12+ e comando
`python desktop/catalog_manager.py`.

## Funzionalità

- Ricerca dei giochi del catalogo originale e dei titoli aggiunti.
- Inserimento e modifica di giochi e metadati senza alterare l'upstream.
- DLC, aggiornamenti, traduzioni e altri contenuti associati per Title ID.
- Verifica di Title ID (16 caratteri esadecimali) e duplicati.
- Salvataggi locali con backup timestamp nella cartella utente.
- Pubblicazione di entrambi i file dati in un unico commit GitHub, con controllo
  dei conflitti contro la versione caricata.
- La pubblicazione scatena automaticamente **Update catalog**; il merge,
  l'integrità del catalogo e i backup della cronologia restano affidati al
  repository e a GitHub Actions.

## Accesso GitHub

Per **leggere** non serve token perché il repository è pubblico.
Per **pubblicare** creare un fine-grained PAT con accesso al solo repository
`and48-spec/SwitchModderSHOP-Catalog` e permesso
**Contents: Read and write**. Non serve il permesso Actions: Write; la
sincronizzazione è avviata da GitHub sul commit dei file dati.

Il token viene inserito nella casella dell'app per la sessione corrente.
**Non viene salvato** in file di configurazione, backup o log.

## File gestiti

- `data/custom_games.json` — personalizzazioni e giochi nuovi.
- `data/addons.json` — DLC, traduzioni, aggiornamenti, altri.
- `generated/catalog.json` — solo lettura, versione consolidata.

I backup locali vengono salvati in
`%LOCALAPPDATA%/SwitchModderSHOP/CatalogManager/backups/`.

## Limiti attuali

- Un gioco upstream non si elimina tramite questa interfaccia: è possibile
  aggiungere/modificare metadati locali e rimuovere un override. Per nascondere
  un gioco originale serve un meccanismo di esclusioni lato generatore.
- `generated/addons.json` non viene ancora letto dalla UI NRO.
  I record inseriti rimangono nel catalogo online ma non compariranno nella
  console finché non viene realizzata l'integrazione add-on lato Switch.
- L'app gestisce metadati e collegamenti: non scarica né ospita giochi o DLC.
  Inserire soltanto link a contenuti autorizzati.
- L'EXE viene compilato automaticamente su GitHub Actions; compilazione riuscita
  non equivale a test funzionale su una macchina Windows reale.
