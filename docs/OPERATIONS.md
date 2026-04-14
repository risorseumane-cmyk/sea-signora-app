## Email alert (admin link)

L’email di alert include sempre un link diretto per l’accesso admin:

- URL: `/?admin=1`

La base URL viene determinata così:

- `PUBLIC_APP_URL` (se presente) oppure
- `X-Forwarded-Proto` + `X-Forwarded-Host` (Railway/proxy) oppure
- `request.scheme + request.host`

Endpoint utili:

- `GET /api/diag` (include stato config email + db path)
- `POST /api/admin/test-email` (invio email di test)

Canali di invio:

- SMTP (se `SMTP_USER` e `SMTP_PASS` presenti)
- Formspree come fallback (default: `https://formspree.io/f/xykbonje`, personalizzabile con `FORMSPREE_ENDPOINT`)

Variabili d’ambiente consigliate:

- `PUBLIC_APP_URL` (es. `https://sea-signora-app.up.railway.app`)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TO`
- `FORMSPREE_ENDPOINT`

## Parsing ordini (quantità + unità)

Il parsing supporta quantità e unità anche senza spazio:

- `500g`, `500 g`, `0,5kg`, `2pz`, `250ml`, `1.5l`

Unità supportate:

- Peso: `g`, `hg`, `kg`
- Volume: `ml`, `cl`, `l`
- Pezzi: `pz`

Conversioni automatiche:

- se il prodotto ha UM `kg` e arriva `500g` → `0.5 kg`
- se il prodotto ha UM `l` e arriva `250ml` → `0.25 l`

## Suggerimenti (fuzzy)

Quando una riga non viene riconosciuta, il backend restituisce:

- `unmatched[]` con `line` e `suggestions[]`

Nel frontend (Inbox → Approva) viene mostrata la modale di chiarimento che permette:

- selezione del prodotto corretto tra suggerimenti
- aggiunta di un nuovo prodotto al catalogo
- ignorare la riga

## Persistenza DB

Il DB usa:

- `APP_DB_PATH` se presente, altrimenti
- `/data/app_data.db` se la directory `/data` esiste, altrimenti
- `backend/app_data.db`

Consigliato: abilitare un Volume su Railway montato in `/data`.

