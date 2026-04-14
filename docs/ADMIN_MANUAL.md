## Manuale Amministratore (Sea Signora)

### 1) Carrello (vista Reparto)

Gli utenti di reparto accedono tramite QR code.

- Aggiungi prodotti dal catalogo con ricerca e autocompletamento.
- Imposta quantità e UM (pz/kg/g/l/ml).
- Premi **Aggiungi al Carrello**.
- Per cancellare tutto: **Svuota Carrello** → conferma → messaggio di conferma.
- Premi **Invia Ordine** per inviare l’ordine all’amministrazione.

Note:

- È possibile inserire note manuali nel campo “NOTE”.
- Se un prodotto non è nel catalogo, scriverlo nelle note: l’admin potrà aggiungerlo.

### 2) Inbox e Approva Ordine

In **Inbox** trovi gli ordini in arrivo.

- Durante l’approvazione, se una riga non viene riconosciuta, appare una finestra con:
  - suggerimenti di prodotti simili
  - possibilità di aggiungere un nuovo prodotto al catalogo
  - possibilità di ignorare la riga
- Al termine dell’analisi, si apre la **Revisione Ordine**:
  - modifica quantità e UM
  - seleziona manualmente il fornitore per ogni riga
  - aggiunge righe manuali (prodotto + quantità + UM + fornitore) con conferma

### 3) Storico Ordini

In **Analytics** → **Storico Ordini**:

- filtra per reparto, mese, intervallo date e referente
- espandi una riga con **Apri** per vedere i dettagli completi (prodotti, quantità, fornitori e prezzi)
- esporta:
  - **Export Excel (CSV)** per analisi su Excel/Google Sheets
  - **Export PDF** (stampa) per archiviazione

Eliminazione:

- da Storico è possibile eliminare un ordine (azione admin, con conferma).

### 4) AI Fornitori (pesi)

In **Impostazioni → AI Fornitori** puoi configurare i pesi:

- Prezzo (%) – default 80
- Porto Franco + Servizio (%) – default 20

Regole:

- la somma deve essere sempre 100%
- quando salvi, la selezione del fornitore viene aggiornata immediatamente per i nuovi ordini

Audit:

- nella stessa sezione trovi l’elenco modifiche (prima/dopo).

### 5) Recupero dati e sicurezza modifiche

Il sistema protegge catalogo e fornitori da salvataggi “vuoti” accidentali.

In caso di bisogno, esiste uno storico interno di versioni lato server (contattare lo sviluppatore per ripristino).

### 6) Fornitori (anagrafica)

In **Impostazioni → Fornitori** puoi:

- aggiungere fornitori con inserimento manuale (nome + categorie obbligatorie)
- modificare anagrafica (contatti, categorie, termini pagamento/consegna, porto franco)
- vedere il log modifiche fornitori

Le modifiche vengono salvate automaticamente.

### 7) Import prodotti via QR

In **Impostazioni → QR Reparti** trovi anche i QR “Importazione Prodotti”.

- il reparto scansiona il QR e compila il form “Nuovo Prodotto”
- l’admin riceve una notifica
- l’admin approva/rifiuta da **Impostazioni → Importazione → Prodotti Inseriti via QR**
