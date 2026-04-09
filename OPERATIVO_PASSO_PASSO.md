# Sea Signora - Avvio Operativo (passo passo)

Questa guida e' pensata per te, senza conoscenze tecniche.

## 1) Cosa hai gia pronto

- App frontend: `index.html`
- Server storage: `backend/app.py`
- Database: SQLite (file automatico `backend/app_data.db`)

## 2) Prima installazione (una sola volta)

Apri il Terminale e copia/incolla questi comandi:

```bash
cd "/Users/raffaele/Desktop/backend"
python3 -m pip install -r requirements.txt
```

## 3) Impostare chiave server (semplice)

Nel Terminale:

```bash
cd "/Users/raffaele/Desktop/backend"
cp .env.example .env
```

Apri il file `.env` e cambia:

`SEASIGNORA_API_KEY=metti-una-chiave-segreta-lunga`

con una chiave tua, ad esempio:

`SEASIGNORA_API_KEY=seasignora-2026-super-chiave-privata`

## 4) Avviare il server

Nel Terminale:

```bash
cd "/Users/raffaele/Desktop/backend"
export SEASIGNORA_API_KEY="seasignora-2026-super-chiave-privata"
python3 app.py
```

Se tutto ok, vedrai che il server parte su `http://localhost:8080`.

## 5) Aprire app e collegarla allo storage centrale

1. Apri nel browser: `http://localhost:8080`
2. Vai in `Impostazioni` -> `Personalizza Layout` -> sezione `Storage Centrale (Dipendenti)`
3. Inserisci:
   - URL Server: `http://localhost:8080`
   - API Key Server: la stessa chiave messa prima
4. Clicca `Invia al Server` (carica dati iniziali)
5. Da quel momento, usa:
   - `Invia al Server` per salvare stato centralizzato
   - `Scarica dal Server` per aggiornare tutti i dispositivi

## 6) Uso dipendenti (in rete locale)

Se i dipendenti sono sulla stessa rete Wi-Fi:

1. Scopri IP del tuo Mac (esempio `192.168.1.45`)
2. Fagli aprire: `http://192.168.1.45:8080`
3. Nell'app, metti:
   - URL Server: `http://192.168.1.45:8080`
   - API Key: la stessa

## 7) Importante (produzione internet)

Per accesso da fuori ristorante serve deploy cloud (Render/Railway/VPS + dominio + HTTPS).
Se vuoi, nel prossimo step lo faccio io e ti do SOLO i click da fare.
