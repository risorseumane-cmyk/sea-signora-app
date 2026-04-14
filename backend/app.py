import json
import os
import sqlite3
import smtplib
import urllib.parse
import urllib.request
import difflib
import re
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# --- CONFIGURAZIONE ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH_ENV = os.getenv("APP_DB_PATH", "").strip()
if DB_PATH_ENV:
    DB_PATH = Path(DB_PATH_ENV)
else:
    data_dir = Path("/data")
    if data_dir.exists():
        DB_PATH = data_dir / "app_data.db"
    else:
        DB_PATH = BASE_DIR / "app_data.db"
FRONTEND_FILE = BASE_DIR.parent / "index.html"

# Chiavi e Configurazione (GEMINI RIMOSSO - Motore Locale Attivo)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@seasignorarest.com")
SMTP_TO = os.getenv("SMTP_TO", "amministrazione@seasignorarest.com")
FORMSPREE_ENDPOINT = os.getenv("FORMSPREE_ENDPOINT", "https://formspree.io/f/xykbonje")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- DATABASE ---
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY, state TEXT)")
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM app_state")
        count = cur.fetchone()[0]

        default_settings = {
            "brandName": "Sea Signora",
            "color": "#EF7818",
            "homeTitle": "Corporate Home",
            "homeSubtitle": "Benvenuto. Il database è sincronizzato in tempo reale su Railway.",
            "homeVisuals": True,
            "homeCardsEnabled": True,
            "homeCards": {"inbox": "Ordini Inbox", "saving": "Saving Ottimizzato", "catalog": "Master Data"}
        }

        if count == 0:
            default_state = {
                "seedVersion": "brand_v1",
                "seededAt": datetime.now().isoformat(),
                "settings": default_settings,
                "products": [
                    {"id": 1, "name": "Aragosta Viva", "cat": "Ittico", "prices": {"METRO": 45.00, "Ittica": 42.50}},
                    {"id": 2, "name": "Gin Tonic Premium", "cat": "Spirits", "prices": {"Beverage": 12.00, "METRO": 13.50}},
                    {"id": 3, "name": "Pane Brioche", "cat": "Forno", "prices": {"Fornaio": 2.50, "METRO": 3.00}}
                ],
                "suppliers": [
                    {"name": "METRO", "min": 250, "current": 0},
                    {"name": "Ittica", "min": 150, "current": 0},
                    {"name": "Beverage", "min": 300, "current": 0},
                    {"name": "Fornaio", "min": 50, "current": 0}
                ],
                "reparti": ["Cucina", "Sala", "Bar", "Wine"],
                "inbox": [],
                "archive": []
            }
            conn.execute("INSERT INTO app_state (id, state) VALUES (1, ?)", (json.dumps(default_state),))
            conn.commit()
        else:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row:
                # Tabella popolata ma manca la riga id=1: ricrea in modo sicuro
                default_state = {
                    "seedVersion": "brand_v1",
                    "seededAt": datetime.now().isoformat(),
                    "settings": default_settings,
                    "products": [],
                    "suppliers": [],
                    "reparti": ["Cucina", "Sala", "Bar", "Wine"],
                    "inbox": [],
                    "archive": []
                }
                conn.execute("INSERT INTO app_state (id, state) VALUES (1, ?)", (json.dumps(default_state),))
                conn.commit()
                return

            state = json.loads(row["state"])
            state.setdefault("seedVersion", "brand_v1")
            state.setdefault("seededAt", datetime.now().isoformat())

            settings = state.get("settings") or {}
            # Migrazione legacy: settings.brand -> settings.brandName
            if "brandName" not in settings and "brand" in settings and isinstance(settings["brand"], str):
                settings["brandName"] = settings["brand"]

            # Default non distruttivi (mantiene i valori già impostati)
            for k, v in default_settings.items():
                if k == "homeCards":
                    current_cards = settings.get("homeCards") or {}
                    merged_cards = {**default_settings["homeCards"], **current_cards}
                    settings["homeCards"] = merged_cards
                else:
                    settings.setdefault(k, v)

            state["settings"] = settings
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.commit()

init_db()

# --- UTILITIES ---
def send_email_alert(dept, staff, text):
    subject = f"NUOVO ORDINE: {dept} da {staff}"
    body = f"Reparto: {dept}\nStaff: {staff}\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nOrdine:\n{text}"
    
    # SMTP
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM or SMTP_USER
            msg['To'] = SMTP_TO
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return {"sent": True, "channel": "smtp", "to": SMTP_TO, "error": None}
        except Exception as e:
            err = str(e)
            print(f"SMTP Error: {err}")
            smtp_error = err
    else:
        smtp_error = "SMTP credentials missing"
            
    # Formspree Fallback
    if FORMSPREE_ENDPOINT:
        try:
            payload = {
                "_subject": subject,
                "message": body,
                "email": SMTP_FROM or SMTP_USER or "noreply@seasignorarest.com",
            }
            data = urllib.parse.urlencode(payload).encode()
            req = urllib.request.Request(
                FORMSPREE_ENDPOINT,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "User-Agent": "SeaSignora/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                _ = resp.read()
            return {"sent": True, "channel": "formspree", "to": SMTP_TO, "error": None}
        except Exception as e:
            err = str(e)
            print(f"Formspree Error: {err}")
            return {"sent": False, "channel": "formspree", "to": SMTP_TO, "error": err}
            
    return {"sent": False, "channel": "smtp", "to": SMTP_TO, "error": smtp_error}

def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.strip().lower()
    aliases = {
        "g": "g",
        "gr": "g",
        "grammo": "g",
        "grammi": "g",
        "hg": "hg",
        "etto": "hg",
        "kg": "kg",
        "kilo": "kg",
        "l": "l",
        "lt": "l",
        "litro": "l",
        "litri": "l",
        "ml": "ml",
        "cl": "cl",
        "pz": "pz",
        "pezzo": "pz",
        "pezzi": "pz",
    }
    return aliases.get(u, u)

def convert_qty(qty: float, unit_in: str | None, unit_target: str | None) -> float:
    u_in = normalize_unit(unit_in)
    u_t = normalize_unit(unit_target)
    if not u_in or not u_t or u_in == u_t:
        return qty

    # Weight
    if u_in in {"g", "hg", "kg"} and u_t in {"g", "hg", "kg"}:
        # Convert to grams
        grams = qty
        if u_in == "kg":
            grams = qty * 1000
        elif u_in == "hg":
            grams = qty * 100
        # Convert grams to target
        if u_t == "g":
            return grams
        if u_t == "hg":
            return grams / 100
        if u_t == "kg":
            return grams / 1000

    # Volume
    if u_in in {"ml", "cl", "l"} and u_t in {"ml", "cl", "l"}:
        ml = qty
        if u_in == "l":
            ml = qty * 1000
        elif u_in == "cl":
            ml = qty * 10
        if u_t == "ml":
            return ml
        if u_t == "cl":
            return ml / 10
        if u_t == "l":
            return ml / 1000

    return qty

def extract_qty_and_unit(raw_line: str) -> tuple[float, str | None, str]:
    line = raw_line.strip().lower()
    # Pattern handles "500g", "500 g", "0,5kg", "2pz"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|grammi|grammo|hg|etto|l|lt|litri|litro|ml|cl|pz|pezzi|pezzo)\b", line)
    if m:
        qty = float(m.group(1).replace(",", "."))
        unit = normalize_unit(m.group(2))
        cleaned = (line[:m.start()] + " " + line[m.end():]).strip()
        return qty, unit, cleaned

    # Fallback: take first number only
    m2 = re.search(r"(\d+(?:[.,]\d+)?)", line)
    if m2:
        qty = float(m2.group(1).replace(",", "."))
        cleaned = (line[:m2.start()] + " " + line[m2.end():]).strip()
        return qty, None, cleaned

    return 1.0, None, line

def local_smart_parse(text, products):
    """Motore di parsing locale 'Smart Matcher' (senza chiavi API)."""
    items = []
    lines = text.split('\n')
    product_names = [p['name'] for p in products]
    
    # Parole comuni da ignorare nel match del nome
    stop_words = {'di', 'da', 'il', 'la', 'un', 'una', 'con', 'per', 'kg', 'g', 'gr', 'grammi', 'hg', 'etto', 'l', 'lt', 'litri', 'ml', 'cl', 'casse', 'cassa', 'pz', 'pezzi', 'pezzo'}

    for line in lines:
        raw = line.strip()
        if not raw:
            continue

        qty_in, unit_in, cleaned = extract_qty_and_unit(raw)
        words = cleaned.split()

        clean_words = [w for w in words if w not in stop_words]
        clean_line = " ".join(clean_words).strip()
        
        if not clean_line:
            continue

        # Match fuzzy sul nome prodotto
        matches = difflib.get_close_matches(clean_line, [n.lower() for n in product_names], n=1, cutoff=0.25)
        if matches:
            match_name = matches[0]
            p_orig = next(p for p in products if p['name'].lower() == match_name)
            target_um = normalize_unit(p_orig.get("um"))
            if not target_um and unit_in:
                if unit_in in {"g", "hg", "kg"}:
                    target_um = "kg"
                elif unit_in in {"ml", "cl", "l"}:
                    target_um = "l"
                elif unit_in in {"pz"}:
                    target_um = "pz"
            qty = convert_qty(qty_in, unit_in, target_um)
            items.append({
                "productId": p_orig['id'],
                "name": p_orig['name'],
                "qty": qty,
                "um": target_um or p_orig.get("um") or "pz",
                "inputQty": qty_in,
                "inputUm": unit_in,
                "cat": p_orig.get('cat', '')
            })
    return {"items": items}

# --- API ROUTES ---
@app.get("/api/state")
def get_state():
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        if row:
            return jsonify({"ok": True, "state": json.loads(row['state'])})
    return jsonify({"ok": False, "error": "No state found"}), 404

@app.post("/api/state")
def post_state():
    try:
        data = request.get_json()
        if not data or 'state' not in data:
            return jsonify({"ok": False, "error": "Invalid state"}), 400
        with get_conn() as conn:
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(data['state']),))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Save error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/order")
def create_order():
    try:
        data = request.get_json()
        dept = data.get("dept")
        staff = data.get("staff")
        text = data.get("text")
        
        if not dept or not staff or not text:
            return jsonify({"ok": False, "error": "Missing fields"}), 400
            
        with get_conn() as conn:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row: return jsonify({"ok": False, "error": "Database not initialized"}), 500
            state = json.loads(row['state'])
            
            new_req = {
                "id": int(datetime.now().timestamp()),
                "dept": dept,
                "staff": staff,
                "text": text,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            state["inbox"].insert(0, new_req)
            
            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.commit()
            
        # Notifica via mail (non blocca la risposta se fallisce o è lenta)
        email = send_email_alert(dept, staff, text)
        
        return jsonify({"ok": True, "notified": bool(email.get("sent")), "email": email})
    except Exception as e:
        print(f"Order error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/ai/order-parse")
def ai_parse():
    p = request.get_json()
    try:
        parsed = local_smart_parse(p.get('text', ''), p.get('catalog', []))
        return jsonify({"ok": True, "parsed": parsed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/ai/help")
def ai_help():
    data = request.get_json()
    q = data.get("question", "").lower()
    if "prezzo" in q or "cost" in q: 
        ans = "Sono Irina, assistente della compagnia. I prezzi migliori sono evidenziati nel Master Data e nella Heatmap (Prodotti vs Fornitori). Puoi aggiornare i prezzi nella sezione 'Aggiorna Fatture'."
    elif "ordine" in q or "reparto" in q: 
        ans = "Sono Irina, assistente della compagnia. Puoi gestire gli ordini in arrivo nella sezione Inbox. I reparti ordinano tramite QR code dedicato."
    elif "heatmap" in q:
        ans = "Sono Irina, assistente della compagnia. La Heatmap confronta Prodotti e Fornitori e mette in evidenza il miglior prezzo. Filtra per categoria per lavorare più velocemente."
    elif "trend" in q or "grafic" in q:
        ans = "Sono Irina, assistente della compagnia. Nei report trovi lo storico ordini per reparto e il trend (mensile e trimestrale) con curva morbida."
    else: 
        ans = "Sono Irina, assistente della compagnia. Posso aiutarti a gestire il catalogo, monitorare gli ordini e analizzare i fornitori."
    return jsonify({"ok": True, "answer": ans})

@app.get("/api/diag")
def diagnostics():
    diag = {
        "db": "unknown",
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "engine": "Local Smart Matcher (OK)",
        "email": {
            "smtp_host": SMTP_HOST,
            "smtp_port": SMTP_PORT,
            "smtp_user_present": bool(SMTP_USER),
            "smtp_pass_present": bool(SMTP_PASS),
            "smtp_from": SMTP_FROM,
            "smtp_to": SMTP_TO,
            "formspree_present": bool(FORMSPREE_ENDPOINT),
        },
    }
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM app_state")
            diag["db"] = f"OK (rows: {cur.fetchone()[0]})"
    except Exception as e:
        diag["db"] = f"Error: {str(e)}"
    return jsonify(diag)

@app.post("/api/admin/test-email")
def test_email():
    data = request.get_json(silent=True) or {}
    to_override = data.get("to")
    global SMTP_TO
    original_to = SMTP_TO
    if isinstance(to_override, str) and "@" in to_override:
        SMTP_TO = to_override.strip()
    try:
        result = send_email_alert("TEST", "Irina", "Questo è un test di invio email alert.")
        return jsonify({"ok": True, "result": result})
    finally:
        SMTP_TO = original_to

@app.post("/api/admin/reset-db")
def reset_db():
    with get_conn() as conn:
        conn.execute("DELETE FROM app_state")
        conn.commit()
    init_db()
    return jsonify({"ok": True})

@app.post("/api/admin/page-settings")
def update_settings():
    data = request.get_json()
    settings = data.get("settings")
    if not settings: return jsonify({"ok": False, "error": "Missing settings"}), 400
    
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row['state'])
        state["settings"] = settings
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/suppliers")
def update_suppliers():
    data = request.get_json()
    suppliers = data.get("suppliers")
    if not suppliers: return jsonify({"ok": False, "error": "Missing suppliers"}), 400
    
    with get_conn() as conn:
        row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
        state = json.loads(row['state'])
        state["suppliers"] = suppliers
        conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
        conn.commit()
    return jsonify({"ok": True})

@app.post("/api/admin/migrate")
def migrate_state():
    try:
        default_settings = {
            "brandName": "Sea Signora",
            "color": "#EF7818",
            "homeTitle": "Corporate Home",
            "homeSubtitle": "Benvenuto. Il database è sincronizzato in tempo reale su Railway.",
            "homeVisuals": True,
            "homeCardsEnabled": True,
            "homeCards": {"inbox": "Ordini Inbox", "saving": "Saving Ottimizzato", "catalog": "Master Data"}
        }

        with get_conn() as conn:
            row = conn.execute("SELECT state FROM app_state WHERE id = 1").fetchone()
            if not row:
                return jsonify({"ok": False, "error": "No state found"}), 404
            state = json.loads(row["state"])
            state.setdefault("seedVersion", "brand_v1")
            state.setdefault("seededAt", datetime.now().isoformat())

            settings = state.get("settings") or {}
            if "brandName" not in settings and "brand" in settings and isinstance(settings["brand"], str):
                settings["brandName"] = settings["brand"]
            for k, v in default_settings.items():
                if k == "homeCards":
                    current_cards = settings.get("homeCards") or {}
                    settings["homeCards"] = {**default_settings["homeCards"], **current_cards}
                else:
                    settings.setdefault(k, v)
            state["settings"] = settings

            conn.execute("UPDATE app_state SET state = ? WHERE id = 1", (json.dumps(state),))
            conn.commit()

        return jsonify({"ok": True, "seedVersion": state.get("seedVersion")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# --- SERVING FRONTEND ---
@app.route("/")
def index():
    return send_from_directory(FRONTEND_FILE.parent, "index.html")

@app.get("/assets/<path:filename>")
def assets(filename):
    assets_dir = FRONTEND_FILE.parent / "assets"
    return send_from_directory(assets_dir, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
