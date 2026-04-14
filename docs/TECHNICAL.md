## Documentazione Tecnica

### Persistenza stato

Lo stato applicativo è salvato su SQLite:

- tabella `app_state` (record `id=1`): stato corrente
- tabella `app_state_versions`: versioni storiche (fino a 300)
- tabella `ai_weights_audit`: audit log pesi AI

Path DB:

- `APP_DB_PATH` (se presente) altrimenti
- `/data/app_data.db` se la directory `/data` esiste (consigliato su Railway con Volume) altrimenti
- `backend/app_data.db`

### API principali

- `GET /api/state` – recupero stato completo
- `POST /api/state` – salvataggio stato completo
  - include guard anti-overwrite (rifiuta `products=[]`/`suppliers=[]` se sul server esistono già)
- `POST /api/order` – creazione richiesta ordine (inserisce in Inbox + invio email alert)
- `POST /api/ai/order-parse` – parsing locale con fuzzy matching e suggerimenti per righe non riconosciute
- `POST /api/admin/page-settings` – aggiorna `settings` (include validazione e audit per `aiWeights`)
- `POST /api/admin/suppliers` – aggiorna fornitori
- `POST /api/admin/reset-db` – reset completo (solo admin)
- `GET /api/diag` – diagnostica (db path, persistenza, config email)
- `POST /api/admin/test-email` – invio email di test
- `GET /api/admin/versions` – elenco versioni
- `POST /api/admin/restore-version` – ripristino versione
- `GET /api/admin/ai-audit` – audit log pesi AI

### Email alert

L’email include sempre un link admin:

- `/?admin=1`

Canali:

- SMTP se `SMTP_USER` e `SMTP_PASS` presenti
- Formspree come fallback (default `https://formspree.io/f/xykbonje`)

Base URL:

- `PUBLIC_APP_URL` se impostata, altrimenti `X-Forwarded-*` / host della request.

### Selezione fornitore (AI weights)

La selezione automatica del fornitore usa:

- peso Prezzo (%)
- peso Porto Franco + Servizio (%)

Componenti del punteggio “Porto Franco + Servizio”:

- avanzamento porto franco (`current/min`)
- lead time (`leadDays`, default 2)
- affidabilità (`reliability`, default 0.85)

Il fornitore con punteggio più basso viene proposto come migliore.

