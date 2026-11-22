# SwitchModderSHOP Neon — Gestione ticket

L'amministratore può registrare e aggiornare richieste da GitHub Actions,
senza aprire o modificare manualmente il JSON.

## Pannello amministrativo

**[Apri Gestisci richieste Neon](https://github.com/and48-spec/SwitchModderSHOP-Catalog/actions/workflows/update-request-status.yml)**

1. Apri il link e premi **Run workflow**.
2. Copia dal messaggio Telegram il codice completo dopo `Codice: #`
   (32 caratteri esadecimali).
3. Seleziona lo stato:
   - `sent` — ricevuta/inviata
   - `in_review` — presa in carico
   - `approved` — approvata
   - `rejected` — rigettata
4. Facoltativamente inserisci una nota pubblica (massimo 160 caratteri).
5. Conferma **Run workflow**.

Il workflow registra o aggiorna il ticket in
[`statuses.json`](statuses.json) e crea il commit automaticamente.
Se il ticket non esiste ancora, viene aggiunto senza alcuna procedura extra.

## Privacy e funzionamento

Il file JSON è **pubblico**: contiene solo codici casuali,
stati e eventuali note pubbliche. **Non inserire dati personali nelle note.**

La console conserva i dati delle richieste nella propria microSD.
Quando si aggiorna lo storico, legge il JSON pubblico e applica
esclusivamente gli stati dei codici presenti sul dispositivo.

La conferma `sent` sulla console non prova la consegna Telegram.
Per ricevere automaticamente le richieste senza passaggi
amministrativi servirebbe un bot o un servizio web autenticato.
